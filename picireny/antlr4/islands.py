# Copyright (c) 2016 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import re


class IslandDescriptor(object):
    """
    Describes island grammars within an input.

    The instructions to process the island grammars are defined by the user
    through a JSON dictionary.
    The dictionary must have 2 mandatory fields, and can optionally have 3
    additional fields:

    * rule: The name of the lexer rule in the host grammar containing the island.
    * grammars: List of grammars describing the island format.
    * pattern: Regular expression to be matched to the text of a HDDToken.
               Matching tokens will be replaced by subtrees. The matching
               named groups are parsed by the provided grammars using the
               group names as start rules. Intermediate substrings not matched
               by any group are represented by HDDTokens.
    * replacements: Dictionary containing pre-defined minimal replacements of the
                    target grammar's rules (if any).
    * island_desc: List of island descriptors for further islands within this
                   format. The tree can be arbitrarily deep.

    Example:
    {
        "rule": "STYLE_BODY",
        "grammars": ["/path/to/css/grammar.g4"],
        "pattern": "(?P<stylesheet>.*)</style>"
    }
    """

    def __init__(self, rule, grammars, *, pattern=None, replacements=None, island_desc=None):
        self.rule = rule
        self.grammars = grammars
        pattern = pattern if pattern else '(?P<{rule}>^.*$)'.format(rule=rule[0].lower() + rule[1:])
        self.pattern = re.compile(pattern, re.S)

        self.replacements = replacements if replacements is not None else {}
        self.island_desc = island_desc

    @staticmethod
    def json_load_object_hook(data):
        if 'rule' in data and 'grammars' in data:
            return IslandDescriptor(rule=data['rule'],
                                    grammars=data['grammars'],
                                    pattern=data.get('pattern', None),
                                    replacements=data.get('replacements', None),
                                    island_desc=data.get('island_desc', None))
        return data
