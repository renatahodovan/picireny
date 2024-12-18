# Copyright (c) 2016-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging
import re

from sys import maxunicode

logger = logging.getLogger(__name__)


# Parser Elements

class ANTLRElement:
    def __init__(self, *, optional=False, repl=None, sep=''):
        """
        Constructor of the base tree node type.

        :param optional: Boolean indicating whether the current node is optional
            or not.
        :param repl: Known replacement if any.
        """
        self.children = []
        self.replacement = repl if not optional else ''
        self.sep = sep

    def all_replacements_defined(self):
        """
        Replacements are defined if the node has at least one child and all of
        the children have a replacement set.
        """
        return self.children and all(x.replacement is not None for x in self.children)

    def has_defined_replacement(self):
        """
        Checks if any of the children has a defined replacement. Needed by
        alternations since the replacement of a recursive rule wouldn't be
        possible to determine if waiting for all the children set.
        """
        return self.children and any(x.replacement is not None for x in self.children)

    def calc_replacement(self):
        """
        The minimal replacement of a parser rule is the concatenation of its
        children's minimal replacement.

        :return: Boolean denoting if a new replacement was found or not.
        """
        if self.all_replacements_defined():
            new_repl = self.sep.join(x.replacement for x in self.children if x.replacement)
            if self.replacement is None or len(new_repl) < len(self.replacement) or (len(new_repl) == len(self.replacement) and new_repl < self.replacement):
                self.replacement = new_repl
                return True
        return False


class ANTLRRule(ANTLRElement):
    """
    Representation of a parser rule. The replacement string determined here will
    be used in the reduce phase. This replacement can be set by the user or
    generated automatically. If it's set by the user then it won't be changed
    ever (even if it isn't minimal).
    """
    def __init__(self, name, *, repl=None):
        super().__init__(repl=repl)
        self.name = name
        self.const_replacement = repl is not None

    def calc_replacement(self):
        if self.const_replacement:
            return False
        return super().calc_replacement()


class ANTLRRef(ANTLRElement):
    def __init__(self, ref, *, optional=False):
        super().__init__(optional=optional)
        self.ref = ref


class ANTLRAlternative(ANTLRElement):
    def __init__(self, *, repl=None):
        super().__init__(repl=repl, sep=' ')


class ANTLRAlternation(ANTLRElement):
    def calc_replacement(self):
        """
        The minimal replacement of an alternation is it's shortest child.

        :return: Boolean denoting if a new replacement was found or not.
        """
        if self.has_defined_replacement():
            new_repl = min((c.replacement for c in self.children if c.replacement is not None), key=len)
            if self.replacement is None or len(new_repl) < len(self.replacement) or (len(new_repl) == len(self.replacement) and new_repl < self.replacement):
                self.replacement = new_repl
                return True
        return False


# Lexer Elements

class ANTLRLexerElement(ANTLRElement):
    def __init__(self, *, optional=False, repl=None):
        super().__init__(optional=optional, repl=repl)
        self.start_intervals = None

    def starters_defined(self):
        return self.children and all(x.start_intervals is not None for x in self.children)

    def calc_starters(self):
        if self.start_intervals is None and self.starters_defined():
            self.start_intervals = sum((x.start_intervals for x in self.children), [])
            return True
        return False

    @staticmethod
    def resolve_escapes(src):
        """
        Remove escaping from escape sequences in src. E.g., lexer rules may
        contain such expressions like: [\t] where \t is evaluated as '\' + 't'
        instead of a tabulator. This function executes the reversed
        transformation.

        :param src: The string that may have escaped escape sequences.
        """
        return src.encode('utf-8').decode('unicode_escape')


class ANTLRLexerRule(ANTLRLexerElement):
    """
    Representation of a lexer rule. The replacement string determined here will
    be used in the reduce phase. This replacement can be set by the user or
    generated automatically. If it's set by the user then it won't be changed
    ever (even if it's not minimal).
    """
    def __init__(self, name, *, repl=None):
        super().__init__(repl=repl)
        self.name = name
        self.const_replacement = repl is not None

    def calc_replacement(self):
        if self.const_replacement:
            return False
        return super().calc_replacement()


class ANTLRLexerElements(ANTLRLexerElement):
    def calc_starters(self):
        if self.children and self.children[0].start_intervals and self.start_intervals is None:
            self.start_intervals = self.children[0].start_intervals
            return True
        return False


class ANTLRLexerAlternation(ANTLRLexerElement):
    def calc_replacement(self):
        # The replacement is the known shortest replacement of the children.
        if self.has_defined_replacement():
            new_repl = min((c.replacement for c in self.children if c.replacement is not None), key=len)
            if self.replacement is None or len(new_repl) < len(self.replacement) or (len(new_repl) == len(self.replacement) and new_repl < self.replacement):
                self.replacement = new_repl
                return True
        return False


class ANTLRTokenRef(ANTLRLexerElement):
    def __init__(self, ref):
        super().__init__()
        self.ref = ref


class ANTLRCharacterRange(ANTLRLexerElement):
    def __init__(self, start, end):
        super().__init__()
        # Converting unicode code points to integers.
        start = int(start.split('\\u')[1], 16) if start.startswith('\\u') else ord(start)
        end = int(end.split('\\u')[1], 16) if end.startswith('\\u') else ord(end)
        self.start_intervals = [(start, end)]
        self.replacement = chr(start)


class ANTLRDotElement(ANTLRLexerElement):
    def __init__(self, *, optional=False):
        super().__init__(optional=optional)
        # Hard-wiring ASCII character range here does not have any limitation (neither effect).
        # Basically it should not be used anyway, since the replacement is
        # constantly set to 'a' and negating 'any character' would not make sense.
        self.start_intervals = [(0, 255)]
        if self.replacement is None:
            self.replacement = 'a'


class ANTLRString(ANTLRLexerElement):
    def __init__(self, src):
        super().__init__()
        src = self.resolve_escapes(src)
        self.start_intervals = [(ord(src[0]), ord(src[0]))]
        self.replacement = src


class ANTLRSetElement(ANTLRLexerElement):
    def __init__(self, content=None, *, optional=False):
        super().__init__(optional=optional)
        if content and self.replacement is None:
            if content.startswith(('"', '\'')):
                self.start_intervals = [(ord(content[1]), ord(content[1]))] if len(content) > 2 else []
                self.replacement = chr(self.start_intervals[0][0])
            elif content.startswith('['):
                self.start_intervals = self.process_charset(content[1:-1])
                self.replacement = chr(self.start_intervals[0][0])

    @classmethod
    def process_charset(cls, src):
        """
        Extract represented character intervals from character sets.

        :param src: The string representation of the character set (w/o
            brackets).
        """
        intervals = [(ord(m.group(1)), ord(m.group(2))) for m in re.finditer(r'(\w)\-(\w)', src)]
        positions = [(m.start(1), m.end(2)) for m in re.finditer(r'(\w)\-(\w)', src)]

        # Character sets can contain multiple sets and single characters (e.g., [-ab-defg-ijkl]).
        # Select the single characters based on the position of sets.
        if not positions:
            intervals.extend((ord(x), ord(x)) for x in cls.resolve_escapes(src))
        else:
            characters = []
            for i, pos in enumerate(positions):
                # Characters before the first range.
                if i == 0 and pos[0] > 0:
                    characters.extend(cls.resolve_escapes(src[0: pos[0]]))
                # Characters between ranges.
                if i < len(positions) - 1:
                    if positions[i][1] + 1 < positions[i + 1][0]:
                        characters.extend(cls.resolve_escapes(src[positions[i][1] + 1: positions[i + 1][0]]))
                # Characters after ranges.
                else:
                    if pos[1] < len(src) - 1:
                        characters.extend(cls.resolve_escapes(src[pos[1] + 1:]))
            intervals.extend((ord(x), ord(x)) for x in characters)

        return intervals

    def calc_starters(self):
        if self.start_intervals is None and self.children and self.children[0].start_intervals:
            self.start_intervals = self.children[0].start_intervals
            return True
        return False


class ANTLRNotSet(ANTLRLexerElement):
    def calc_starters(self):
        # Known limitation (TODO?): it does not handle multiple negation.
        if self.starters_defined() and self.start_intervals is None:
            intervals = [y for x in self.children for y in x.start_intervals]
            # Sort list of tuples by the first element.
            intervals.sort(key=lambda x: x[0])
            # The number (char) before the first interval's lower limit or after
            # the last interval's upper limit is suitable for negation.
            if intervals[0][0] > 0:
                neighbour_char = intervals[0][0] - 1
            elif intervals[-1][-1] < maxunicode:
                neighbour_char = intervals[-1][-1] + 1
            else:
                assert False, 'Cannot negate the whole unicode range.'
            self.start_intervals = [(neighbour_char, neighbour_char)]
            return True
        return False

    def calc_replacement(self):
        if self.start_intervals and self.replacement is None:
            self.replacement = chr(self.start_intervals[0][0])
            return True
        return False
