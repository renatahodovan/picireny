# Copyright (c) 2016 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.md or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging

from antlr4 import *

from ..hdd_tree import HDDTree, HDDToken

logger = logging.getLogger(__name__)


class IslandDescriptor(object):
    """Utility class to help the creation of island descriptors with a single expression."""

    def __init__(self, rule, grammars, start_rule, *, replacements=None, island_desc=None, process=None):
        self.rule = rule
        self.grammars = grammars
        self.start_rule = start_rule

        self.replacements = replacements if replacements is not None else {}
        self.island_desc = island_desc
        if process is not None:
            self.process = process

    def process(self, text):
        return [(True, text)]


class IslandManager(object):
    """
    It makes possible to use island grammars while parsing the input.

    The instructions to process the island grammars are defined by the user
    through an object.
    The object is must have 1 method and 3 fields, and can optionally have two
    additional fields:

    * rule: The name of the lexer rule in the base grammar containing the island.
    * grammars: List of grammars describing the island format.
    * start_rule: The start rule of the island grammar.
    * replacements: Dictionary containing pre-defined minimal replacements of the
                    target grammar's rules (if any).
    * island_desc: List of island descriptors for further islands within this
                   format. The tree can be arbitrarily deep.
    * process: A method accepting a string as parameter and splitting it up
               if needed to further pieces. It has to return a list of pairs where
               the first element of every pair is either True or False to denote
               wheter the piece of text in the second element of the pair is actually
               an island or just a constant token.

    An example island descriptor object can be instantiated with the help of the
    IslandDescriptor class (although it is not mandatory to use that class as long
    as the object has the expected members):

    IslandDescriptor('STYLE_BODY', ['/path/to/css/grammar.g4'], 'stylesheet'
                     process=lambda self, text: [(True, text.split('</style>')[0]), (False, '</style>')])

    Note: Should a more complex process function be needed then single-expression
    object creation might not be possible as writing multi-statement lambdas is
    tricky in Python.
    """

    def __init__(self, island_desc, antlr, work_dir):
        """
        :param island_desc: An island descriptor object, or a list of them.
        :param antlr: Path of the ANTLR jar.
        :param work_dir: Output directory for the various islands.
        """
        self.antlr = antlr
        self.islands = dict()

        from .hdd_tree_builder import prepare_parsing
        for island in list(island_desc):
            island.lexer, island.parser, island.listener = prepare_parsing(grammar=island.grammars,
                                                                           antlr=antlr,
                                                                           base_dir=work_dir,
                                                                           sub_dir=island.rule,
                                                                           replacements=(island.replacements if hasattr(island, 'replacements') else {}),
                                                                           island_desc=(island.island_desc if hasattr(island, 'island_desc') else None))
            self.islands[island.rule] = island

    def is_island(self, name):
        """
        Decides whether a rule contains an island or not.

        :param name: Name of the rule to decide about.
        :return: True or False.
        """
        return name in self.islands

    def process_node(self, name, terminal):
        """
        Process terminal with an island grammar.

        :param name: Name of the rule to be processed as an island.
        :param terminal: Token that contains the island.
        :return: Subtree representing the terminal.
        """
        from .hdd_tree_builder import build_hdd_tree
        island = self.islands.get(name)
        result, offset = [], 0
        for i, (chunk_island, chunk_src) in enumerate(island.process(terminal.symbol.text)):
            if not chunk_island:
                result.append(HDDToken(name='%s_%d' % (name, i),
                                       replace=chunk_src,
                                       start=HDDTree.Position(terminal.symbol.line, terminal.symbol.start + offset),
                                       end=HDDTree.Position(terminal.symbol.line, terminal.symbol.stop + offset),
                                       text=chunk_src))
                offset += len(chunk_src)
            else:
                result.append(build_hdd_tree(input_stream=InputStream(chunk_src),
                                             lexer_class=island.lexer,
                                             parser_class=island.parser,
                                             listener_class=island.listener,
                                             start_rule=island.start_rule))
                offset += len(chunk_src)

        return result
