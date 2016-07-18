# Copyright (c) 2016 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.md or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging
import sys

from antlr4 import *
from pkgutil import get_data
from os import makedirs
from os.path import basename, join

from .grammar_analyzer import analyze_grammars
from .islands import IslandManager
from .parser_builder import build_grammars
from ..hdd_tree import HDDRule, HDDToken, HDDTree

logger = logging.getLogger(__name__)


def create_hdd_tree(input_stream, grammar, start_rule, antlr, work_dir, *, replacements=None, island_desc=None):
    """
    Build a tree that the HDD algorithm can work with.

    :param input_stream: ANTLR stream (FileStream or InputStream) representing the input.
    :param grammar: List of the grammars describing the inputs format.
    :param start_rule: The name of the start rule of the parser.
    :param antlr: Path to the ANTLR4 tool (Java jar binary).
    :param work_dir: Working directory.
    :param replacements: Dictionary containing the minimal replacements of the target grammar's rules.
    :param island_desc: List of IslandDescriptor objects.
    :return: The root of the created HDD tree.
    """
    lexer_class, parser_class, listener_class = prepare_parsing(grammar, antlr, work_dir, 'target',
                                                                replacements=replacements, island_desc=island_desc)
    return build_hdd_tree(input_stream, lexer_class, parser_class, listener_class, start_rule)


class HDDStar(HDDRule):
    """
    Special rule type in the HDD tree to support optional quantifiers.
    """
    def __init__(self):
        HDDRule.__init__(self, '', '')


def inject_optional_actions(grammar, positions, target_file):
    """
    Update the original parser grammar by injecting actions to the start and
    end of every optional parts.

    :param grammar: Path to the grammar to be updated.
    :param positions: List of position containing start and end locations.
    :param target_file: Path of the updated grammar.
    """
    with open(grammar, 'rb') as f:
        lines = f.read().splitlines(keepends=True)

    prefix = b' ({self.enter_optional()} '
    postfix = b' {self.exit_optional()})'

    for ln in positions:
        offset = 0
        for i, position in enumerate(sorted(positions[ln], key=lambda x: x[1])):
            if position[0] == 's':
                lines[ln - 1] = lines[ln - 1][0:position[1] + offset] + prefix + lines[ln - 1][position[1] + offset:]
                offset += len(prefix)
            elif position[0] == 'e':
                lines[ln - 1] = lines[ln - 1][0:position[1] + offset] + postfix + lines[ln - 1][position[1] + offset:]
                offset += len(postfix)

    with open(target_file, 'wb') as f:
        f.write(b''.join(lines))


def build_antlr_grammars(antlr, work_dir):
    """
    Build parsers to parse ANTLR4 grammars.

    :param antlr: Path to the ANTLR4 tool (Java jar binary).
    :param work_dir: Working directory.
    :return: References to the ANTLR4 lexer and parser classes.
    """
    antlr4_workdir = join(work_dir, 'antlr4')
    makedirs(antlr4_workdir, exist_ok=True)
    sys.path.append(antlr4_workdir)

    # Copy the resources needed to interpret the input grammars.
    for resource in ['LexerAdaptor.py', 'ANTLRv4Lexer.g4', 'ANTLRv4Parser.g4', 'LexBasic.g4']:
        with open(join(antlr4_workdir, resource), 'wb') as f:
            f.write(get_data(__package__, join('resources', resource)))

    antlr_lexer_class, antlr_parser_class, _ = build_grammars([join(antlr4_workdir, 'ANTLRv4Lexer.g4'),
                                                               join(antlr4_workdir, 'ANTLRv4Parser.g4'),
                                                               join(antlr4_workdir, 'LexBasic.g4')],
                                                              antlr4_workdir,
                                                              antlr)
    logger.debug('ANTLR4 grammars processed...')

    return antlr_lexer_class, antlr_parser_class


# Override ConsoleErrorListener to suppress parse issues in non-verbose mode.
class ConsoleListener(error.ErrorListener.ConsoleErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        logger.debug('line %d:%d %s' % (line, column, msg))

error.ErrorListener.ConsoleErrorListener.INSTANCE = ConsoleListener()


def prepare_parsing(grammar, antlr, base_dir, sub_dir, *, replacements=None, island_desc=None):
    """
    Performs initiative steps needed to parse the input test case (like create directory structures,
    builds grammars, sets PATH, etc...)

    :param grammar: List of the grammars describing the inputs format.
    :param antlr: Path to the ANTLR4 tool (Java jar binary).
    :param base_dir: Root directory grammar files.
    :param sub_dir: Name of directory in base_dir to store the current grammar files.
    :param replacements: Dictionary containing the minimal replacements of the target grammar's rules.
    :param island_desc: List of IslandDescriptor objects.
    :return: The HDD tree representing the test case.
    """

    antlr_lexer_class, antlr_parser_class = build_antlr_grammars(antlr, base_dir)
    replacements, action_positions = analyze_grammars(antlr_lexer_class, antlr_parser_class, grammar, replacements)
    logger.debug('Replacements are calculated...')

    grammar_workdir = join(base_dir, sub_dir)
    makedirs(grammar_workdir, exist_ok=True)
    sys.path.append(grammar_workdir)

    # Inject actions into the target grammars to help localizing part of the test case that are optional.
    for i, g in enumerate(grammar):
        grammar[i] = join(grammar_workdir, basename(g))
        inject_optional_actions(g, action_positions[g], grammar[i])

    target_lexer_class, target_parser_class, target_listener_class = build_grammars(grammar, grammar_workdir, antlr)
    logger.debug('Target grammars are processed...')

    islands = island_desc and IslandManager(island_desc, antlr, base_dir)
    logger.debug('Islands are processed...')

    class ExtendedTargetParser(target_parser_class):
        """
        ExtendedTargetParser is a subclass of the original parser implementation.
        It can trigger state changes that are needed to identify parts of the input
        that are not needed to keep it syntactically correct.
        """
        def enter_optional(self):
            self.trigger_listener('enter_optional')

        def exit_optional(self):
            self.trigger_listener('exit_optional')

        def enterRecursionRule(self, localctx: ParserRuleContext, state: int, ruleIndex: int, precedence: int):
            target_parser_class.enterRecursionRule(self, localctx, state, ruleIndex, precedence)
            self.trigger_listener('recursion_enter')

        def pushNewRecursionContext(self, localctx: ParserRuleContext, state: int, ruleIndex: int):
            target_parser_class.pushNewRecursionContext(self, localctx, state, ruleIndex)
            self.trigger_listener('recursion_push')

        def unrollRecursionContexts(self, parentCtx: ParserRuleContext):
            target_parser_class.unrollRecursionContexts(self, parentCtx)
            self.trigger_listener('recursion_unroll')

        def trigger_listener(self, event):
            for listener in self.getParseListeners():
                if hasattr(listener, event):
                    getattr(listener, event)()

        def syntax_error_warning(self):
            if self._syntaxErrors:
                logger.warn('%s finished with %d syntax errors. This may decrease reduce quality.' %
                            (target_parser_class.__name__, self._syntaxErrors))

    class ExtendedTargetListener(target_listener_class):
        """
        ExtendedTargetListener is a subclass of the original listener implementation.
        It can trigger state changes that are needed to identify parts of the input
        that are not needed to keep it syntactically correct.
        """
        def __init__(self, parser):
            self.parser = parser
            self.current_node = None
            self.root = None

        def recursion_enter(self):
            assert isinstance(self.current_node, HDDRule)
            node = HDDRule(self.current_node.name, self.current_node.replace)
            self.current_node.add_child(node)
            self.current_node.recursive_rule = True
            self.current_node = node

        def recursion_push(self):
            assert len(self.current_node.parent.children) > 0

            first_child = self.current_node.parent.children[0]
            self.current_node.parent.remove_child(first_child)
            self.current_node.add_child(first_child)

        def recursion_unroll(self):
            assert self.current_node.recursive_rule
            assert len(self.current_node.children) == 1 and self.current_node.name == self.current_node.children[0].name
            children_to_lift = self.current_node.children[0].children
            self.current_node.children = []
            self.current_node.add_children(children_to_lift)
            self.current_node.start = self.current_node.children[0].start
            self.current_node.end = self.current_node.children[-1].end
            self.current_node = self.current_node.parent

        def enterEveryRule(self, ctx:ParserRuleContext):
            name = self.parser.ruleNames[ctx.getRuleIndex()]
            node = HDDRule(name, replacements[name])
            if not self.root:
                self.root = node
            else:
                assert self.current_node
                self.current_node.add_child(node)
            self.current_node = node

        def exitEveryRule(self, ctx:ParserRuleContext):
            # If the input contains syntax error, then the last optional block was may not closed.
            while isinstance(self.current_node, HDDStar):
                self.exit_optional()

            assert self.current_node.name == self.parser.ruleNames[ctx.getRuleIndex()],\
                '%s (%s) != %s' % (self.current_node.name, repr(self.current_node), self.parser.ruleNames[ctx.getRuleIndex()])

            start, _ = self.tokenBoundaries(ctx.start)
            _, end = self.tokenBoundaries(ctx.stop if ctx.stop else ctx.start)
            self.current_node.start = start
            self.current_node.end = end

            if self.current_node.parent:
                self.current_node = self.current_node.parent

        def tokenBoundaries(self, token):
            line_breaks = token.text.count('\n')
            return HDDTree.Position(token.line, token.column), \
                   HDDTree.Position(token.line + line_breaks,
                                    token.column + len(token.text) if not line_breaks else
                                    len(token.text) - token.text.rfind('\n'))

        def visitTerminal(self, ctx:TerminalNode):
            name, text = (self.parser.symbolicNames[ctx.symbol.type], ctx.symbol.text) if ctx.symbol.type != Token.EOF else ('EOF', '')

            if not (islands and islands.is_island(name)):
                start, end = self.tokenBoundaries(ctx.symbol)
                node = HDDToken(name,
                                replacements[name] if name in replacements else ctx.symbol.text,
                                start=start,
                                end=end,
                                text=text)
                self.current_node.add_child(node)
            else:
                self.current_node.add_children(islands.process_node(name, ctx))

        def enter_optional(self):
            star_node = HDDStar()
            self.current_node.add_child(star_node)
            self.current_node = star_node

        def exit_optional(self):
            assert self.current_node.parent, 'Star node has no parent.'
            assert self.current_node.children, 'Star node has no children.'

            self.current_node.start = self.current_node.children[0].start
            self.current_node.end = self.current_node.children[-1].end
            self.current_node = self.current_node.parent

        def print_tree(self):
            if self.root and logger.isEnabledFor(logging.DEBUG):
                logger.debug(self.root.tree_str(current=self.current_node))

    return target_lexer_class, ExtendedTargetParser, ExtendedTargetListener


def build_hdd_tree(input_stream, lexer_class, parser_class, listener_class, start_rule):
    """
    Parse the input with the provided ANTLR classes.

    :param input_stream: ANTLR stream (FileStream or InputStream) representing the input.
    :param lexer_class: Reference to the lexer class.
    :param parser_class: Reference to the parser class.
    :param listener_class: Reference to the listener class.
    :param start_rule: The name of the start rule of the parser.
    :return: The root of the created HDD tree.
    """
    target_parser = parser_class(CommonTokenStream(lexer_class(input_stream)))
    parser_listener = listener_class(target_parser)
    target_parser.addParseListener(parser_listener)

    logger.debug('Parse input with %s rule' % start_rule)
    getattr(target_parser, start_rule)()
    target_parser.syntax_error_warning()
    logger.debug('Parse done.')

    assert parser_listener.root == parser_listener.current_node
    return parser_listener.root
