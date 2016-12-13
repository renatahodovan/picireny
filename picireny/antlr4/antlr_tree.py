# Copyright (c) 2016 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging
import re

logger = logging.getLogger(__name__)


# Paser Elements

class ANTLRElement(object):
    def __init__(self, *, optional=False, repl=None):
        """
        Constructor of the base tree node type.

        :param optional: Boolean indicating whether the current node is optional or not.
        :param repl: Known replacement if any.
        """
        self.children = []
        self.replacement = repl if not optional else ''

    def all_replacements_defined(self):
        """
        Replacements are defined if the node has at least one child and all of the children
        have a replacement set.
        """
        return self.children and all(x.replacement is not None for x in self.children)

    def has_defined_replacement(self):
        """
        Checks if any of the children has a defined replacement.
        Needed by alternations since the replacement of a recursive rule wouldn't be possible to
        determine if waiting for all the children set.
        """
        return self.children and any(x.replacement is not None for x in self.children)

    def calc_replacement(self):
        """
        The minimal replacement of a parser rule is the concatenation of its children's minimal replacement.

        :return: Boolean denoting if a new replacement was found or not.
        """
        if self.all_replacements_defined():
            new_repl = ''.join([x.replacement for x in self.children])
            if self.replacement is None or len(new_repl) < len(self.replacement):
                self.replacement = new_repl
                return True
        return False


class ANTLRRule(ANTLRElement):
    """
    Representation of a parser rule. The replacement string determined here
    will be used in the reduce phase. This replacement can be set by the user
    or generated automatically. If it's set by the user then it won't be changed
    ever (even if it isn't minimal).
    """
    def __init__(self, name, repl):
        ANTLRElement.__init__(self, repl=repl)
        self.name = name
        self.const_replacement = repl is not None

    def calc_replacement(self):
        if self.const_replacement:
            return False
        return ANTLRElement.calc_replacement(self)


class ANTLRRef(ANTLRElement):
    def __init__(self, ref, *, optional=False):
        ANTLRElement.__init__(self, optional=optional)
        self.ref = ref


class ANTLRAlternation(ANTLRElement):
    def calc_replacement(self):
        """
        The minimal replacement of an alternation is it's shortest child.

        :return: Boolean denoting if a new replacement was found or not.
        """
        if self.has_defined_replacement():
            new_repl = min(list(filter(lambda i: i is not None, [c.replacement for c in self.children])), key=len, default=False)
            if self.replacement is None or len(new_repl) < len(self.replacement):
                self.replacement = new_repl
                return True
        return False


# Lexer Elements

class ANTLRLexerElement(ANTLRElement):
    def __init__(self, *, optional=False, repl=None):
        ANTLRElement.__init__(self, optional=optional, repl=repl)
        self.start_intervals = None

    def starters_defined(self):
        return self.children and all(x.start_intervals is not None for x in self.children)

    def calc_starters(self):
        if self.start_intervals is None and self.starters_defined():
            self.start_intervals = sum((x.start_intervals for x in self.children), [])
            return True
        return False


class ANTLRLexerRule(ANTLRLexerElement):
    """
    Representation of a lexer rule. The replacement string determined here
    will be used in the reduce phase. This replacement can be set by the user
    or generated automatically. If it's set by the user then it won't be changed
    ever (even if it's not minimal).
    """
    def __init__(self, name, repl):
        ANTLRLexerElement.__init__(self, repl=repl)
        self.name = name
        self.const_replacement = repl is not None

    def calc_replacement(self):
        if self.const_replacement:
            return False
        return ANTLRElement.calc_replacement(self)


class ANTLRLexerElements(ANTLRLexerElement):
    def calc_starters(self):
        if self.children[0].start_intervals and self.start_intervals is None:
            self.start_intervals = self.children[0].start_intervals
            return True
        return False


class ANTLRLexerAlternation(ANTLRLexerElement):
    def calc_replacement(self):
        # The replacement is the known shortest replacement of the children.
        if self.has_defined_replacement():
            new_repl = min(list(filter(lambda i: i is not None, [c.replacement for c in self.children])), key=len, default=False)
            if self.replacement is None or len(new_repl) < len(self.replacement):
                self.replacement = new_repl
                return True
        return False


class ANTLRTokenRef(ANTLRLexerElement):
    def __init__(self, ref):
        ANTLRLexerElement.__init__(self)
        self.ref = ref


class ANTLRCharacterRange(ANTLRLexerElement):
    def __init__(self, start, end):
        ANTLRLexerElement.__init__(self)
        # Converting unicode code points to integers.
        start = int(start.split('\\u')[1], 16) if start.startswith('\\u') else ord(start)
        end = int(end.split('\\u')[1], 16) if end.startswith('\\u') else ord(end)
        self.start_intervals = [(start, end)]
        self.replacement = chr(start)


class ANTLRDotElement(ANTLRLexerElement):
    def __init__(self, *, optional=False):
        ANTLRLexerElement.__init__(self, optional=optional)
        # Hard-wiring ASCII character range here does not have any limitation (neither effect).
        # Basically it should not be used anyway, since the replacement is
        # constantly set to 'a' and negating 'any character' would not make sense.
        self.start_intervals = [(0, 255)]
        if self.replacement is None:
            self.replacement = 'a'


class ANTLRString(ANTLRLexerElement):
    def __init__(self, src):
        ANTLRLexerElement.__init__(self)
        src = ANTLRSetElement.resolve_escapes(src)
        self.start_intervals = [(ord(src[0]), ord(src[0]))]
        self.replacement = src


class ANTLRSetElement(ANTLRLexerElement):
    def __init__(self, *, content=None, optional=False):
        ANTLRLexerElement.__init__(self, optional=optional)
        if content and self.replacement is None:
            if content.startswith(('"', '\'')):
                self.start_intervals = [(ord(content[1]), ord(content[1]))] if len(content) > 2 else []
                self.replacement = chr(self.start_intervals[0][0])
            elif content.startswith('['):
                self.start_intervals = ANTLRSetElement.process_charset(content[1:-1])
                self.replacement = chr(self.start_intervals[0][0])

    @staticmethod
    def process_charset(src):
        """
        Extract represented character intervals from chararcter sets.

        :param src: The string representation of the character set (w/o brackets).
        """
        intervals = [(ord(m.group(1)), ord(m.group(2))) for m in re.finditer('(\w)\-(\w)', src)]
        positions = [(m.start(1), m.end(2)) for m in re.finditer('(\w)\-(\w)', src)]
        return intervals + ANTLRSetElement.extract_single_chars(src, positions)

    @staticmethod
    def extract_single_chars(src, positions):
        """
        Character sets can contain multiple sets and single characters. (e.g. [-ab-defg-ijkl])
        This function selects the single characters based on the position of sets.

        :param src: The string representation of the character set (w/o brackets).
        :param positions: Position intervals in src where character intervals are placed.
        """
        if not positions:
            return [(ord(x), ord(x)) for x in list(ANTLRSetElement.resolve_escapes(src))]
        characters = []
        for i, pos in enumerate(positions):
            # Characters before the first range.
            if i == 0 and pos[0] > 0:
                characters.extend(list(ANTLRSetElement.resolve_escapes(src[0: pos[0]])))
            # Characters between ranges.
            if i < len(positions) - 1:
                if positions[i][1] + 1 < positions[i + 1][0]:
                    characters.extend(list(ANTLRSetElement.resolve_escapes(src[positions[i][1] + 1: positions[i + 1][0]])))
            # Characters after ranges.
            else:
                if pos[1] < len(src) - 1:
                    characters.extend(list(ANTLRSetElement.resolve_escapes(src[pos[1] + 1:])))
        return [(ord(x), ord(x)) for x in characters]

    @staticmethod
    def resolve_escapes(src):
        """
        Remove escaping from escape sequences in src. E.g. lexer rules may contain such
        expressions like: [\t] where \t is evaluated as '\' + 't' instead of a tabulator.
        This function executes the reversed transformation.

        :param src: The string that may have escaped escape sequences.
        """
        return bytes(src, 'utf-8').decode('unicode_escape')

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
            # The number (char) before the first interval's lower limit is suitable for negation.
            self.start_intervals = [(intervals[0][0] - 1, intervals[0][0] - 1)]
            return True
        return False

    def calc_replacement(self):
        if self.start_intervals and self.replacement is None:
            self.replacement = chr(self.start_intervals[0][0])
            return True
        return False
