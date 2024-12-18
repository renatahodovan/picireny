# Copyright (c) 2016-2023 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging
import re
import shutil
import sys

from glob import glob
from os import makedirs, pathsep
from os.path import basename, join
from pkgutil import get_data
from string import Template
from subprocess import CalledProcessError, PIPE, run, STDOUT

import xson

from antlr4 import CommonTokenStream, error, InputStream, Token
from antlr4.Token import CommonToken

from .grammar_analyzer import analyze_grammars
from .parser_builder import build_grammars
from ..hdd_tree import HDDRule, HDDToken, Position
from ..transform import remove_empty_nodes


logger = logging.getLogger(__name__)


class HDDQuantifier(HDDRule):
    """
    Special rule type in the HDD tree to support optional quantifiers.
    """
    def __init__(self, *, start=None, end=None):
        super().__init__('', start=start, end=end)


class HDDHiddenToken(HDDToken):
    """
    Special token type that represents tokens from hidden channels.
    """


class HDDErrorToken(HDDToken):
    """
    Special token type that represents unmatched tokens. The minimal replacement
    of such nodes is an empty string.
    """
    def __init__(self, text, *, start=None, end=None):
        super().__init__('', text, start=start, end=end)


# Override ConsoleErrorListener to suppress parse issues in non-verbose mode.
class ConsoleListener(error.ErrorListener.ConsoleErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        logger.debug('line %d:%d %s', line, column, msg)


error.ErrorListener.ConsoleErrorListener.INSTANCE = ConsoleListener()


def create_hdd_tree(src, *,
                    input_format, start,
                    antlr, lang='python',
                    hidden_tokens=False,
                    work_dir):
    """
    Build a tree that the HDD algorithm can work with.

    :param src: Input source.
    :param input_format: Dictionary describing the input format.
    :param start: Name of the start rule in [grammarname:]rulename format.
    :param antlr: Path to the ANTLR4 tool (Java jar binary).
    :param lang: The target language of the parser.
    :param hidden_tokens: Build hidden tokens of the input format into the HDD
        tree.
    :param work_dir: Working directory.
    :return: The root of the created HDD tree.
    """

    def inject_optional_actions(grammar, positions, target_file):
        """
        Update the original parser grammar by injecting actions to the start and
        end of every quantified part.

        :param grammar: Path to the grammar to be updated.
        :param positions: Start and end locations of quantified elements.
        :param target_file: Path to the updated grammar.
        """
        with open(grammar, 'rb') as f:
            lines = f.read().splitlines(True)

        languages = {
            'python': {
                'prefix': b'({self.enter_optional()} ',
                'postfix': b' {self.exit_optional()})'
            },
            'java': {
                'prefix': b'({ try { getClass().getMethod("enter_optional").invoke(this); } catch (Exception e) { assert false; }} ',
                'postfix': b' { try { getClass().getMethod("exit_optional").invoke(this); } catch (Exception e) { assert false; }})'
            }
        }

        for ln in positions:
            offset = 0
            for position in sorted(positions[ln], key=lambda x: x[1]):
                if position[0] == 's':
                    lines[ln - 1] = lines[ln - 1][0:position[1] + offset] + languages[lang]['prefix'] + lines[ln - 1][position[1] + offset:]
                    offset += len(languages[lang]['prefix'])
                elif position[0] == 'e':
                    lines[ln - 1] = lines[ln - 1][0:position[1] + offset] + languages[lang]['postfix'] + lines[ln - 1][position[1] + offset:]
                    offset += len(languages[lang]['postfix'])

        with open(target_file, 'wb') as f:
            f.write(b''.join(lines))

    def java_classpath(current_workdir):
        return pathsep.join([antlr, current_workdir])

    def compile_java_sources(lexer, parser, listener, current_workdir):
        executor = Template(get_data(__package__, 'resources/ExtendedTargetParser.java').decode('utf-8'))
        with open(join(current_workdir, f'Extended{parser}.java'), 'w') as f:
            f.write(executor.substitute({'lexer_class': lexer,
                                         'parser_class': parser,
                                         'listener_class': listener}))
        try:
            run(('javac', '-classpath', java_classpath(current_workdir)) + tuple(basename(j) for j in glob(join(current_workdir, '*.java'))),
                stdout=PIPE, stderr=STDOUT, cwd=current_workdir, check=True)
        except CalledProcessError as e:
            logger.error('Java compile failed!\n%s\n', e.output)
            raise

    def prepare_parsing(grammar_name):
        """
        Performs initiative steps needed to parse the input test case (like
        create directory structures, builds grammars, sets PATH, etc...)

        :param grammar_name: Name of the grammar to use for parsing.
        """
        grammar = input_format[grammar_name]
        resources = [fn for fn in grammar['files'] if not fn.endswith('.g4')]
        grammar['files'] = [fn for fn in grammar['files'] if fn.endswith('.g4')]

        replacements, action_positions = analyze_grammars(grammar['files'], grammar['replacements'])
        logger.debug('Replacements are calculated...')

        current_workdir = join(work_dir, grammar_name) if grammar_name else work_dir
        makedirs(current_workdir, exist_ok=True)
        if current_workdir not in sys.path:
            sys.path.append(current_workdir)

        # Inject actions into the target grammars to help localizing part of the test case that are optional.
        for i, g in enumerate(grammar['files']):
            grammar['files'][i] = join(current_workdir, basename(g))
            inject_optional_actions(g, action_positions[g], grammar['files'][i])

        for r in resources:
            shutil.copy(r, current_workdir)

        target_lexer_class, target_parser_class, target_listener_class = build_grammars(tuple(grammar['files']), current_workdir, antlr, lang)
        logger.debug('Target grammars are processed...')

        if lang == 'java':
            compile_java_sources(target_lexer_class, target_parser_class, target_listener_class, current_workdir)
            input_format[grammar_name].update(lexer=target_lexer_class, parser=target_parser_class, listener=target_listener_class, replacements=replacements)
            return

        class ExtendedTargetLexer(target_lexer_class):
            """
            ExtendedTargetLexer is a subclass of the original lexer
            implementation. It can recognize skipped tokens and instead of
            eliminating them from the parser they can be redirected to the
            dedicated PICIRENY_CHANNEL for later use.
            """

            PICIRENY_CHANNEL = -3

            # Skipped tokens cannot be accessed from the parser but we still need them to
            # unparse test cases correctly. Sending these tokens to a dedicated channel won't
            # alter the parse but makes these tokens available.
            def skip(self):
                self._channel = self.PICIRENY_CHANNEL

        class ExtendedTargetParser(target_parser_class):
            """
            ExtendedTargetParser is a subclass of the original parser
            implementation. It can trigger state changes that are needed to
            identify parts of the input that are not needed to keep it
            syntactically correct.
            """
            def enter_optional(self):
                self.trigger_listener('enter_optional')

            def exit_optional(self):
                self.trigger_listener('exit_optional')

            def enterRecursionRule(self, localctx, state, ruleIndex, precedence):
                super().enterRecursionRule(localctx, state, ruleIndex, precedence)
                self.trigger_listener('recursion_enter')

            def pushNewRecursionContext(self, localctx, state, ruleIndex):
                super().pushNewRecursionContext(localctx, state, ruleIndex)
                self.trigger_listener('recursion_push')

            def unrollRecursionContexts(self, parentCtx):
                super().unrollRecursionContexts(parentCtx)
                self.trigger_listener('recursion_unroll')

            def trigger_listener(self, event):
                for listener in self.getParseListeners():
                    if hasattr(listener, event):
                        getattr(listener, event)()

            def syntax_error_warning(self):
                if self.getNumberOfSyntaxErrors() > 0:
                    logger.warning('%s finished with %d syntax errors. This may decrease reduce quality.',
                                   target_parser_class.__name__, self.getNumberOfSyntaxErrors())

        class ExtendedTargetListener(target_listener_class):
            """
            ExtendedTargetListener is a subclass of the original listener
            implementation. It can trigger state changes that are needed to
            identify parts of the input that are not needed to keep it
            syntactically correct.
            """
            def __init__(self, parser):
                self.parser = parser
                self.current_node = None
                self.root = None
                self.seen_terminal = False
                self.island_nodes = []

            def recursion_enter(self):
                assert isinstance(self.current_node, HDDRule)
                node = HDDRule(self.current_node.name)
                self.current_node.add_child(node)
                self.current_node.recursive_rule = True
                self.current_node = node

            def recursion_push(self):
                assert self.current_node.parent.children

                first_child = self.current_node.parent.children[0]
                self.current_node.parent.remove_child(first_child)
                self.current_node.add_child(first_child)

            def recursion_unroll(self):
                assert self.current_node.recursive_rule
                assert len(self.current_node.children) == 1 and self.current_node.name == self.current_node.children[0].name
                children_to_lift = self.current_node.children[0].children
                parent = self.current_node.parent
                if children_to_lift:
                    self.current_node.children = []
                    self.current_node.add_children(children_to_lift)
                else:
                    parent.remove_child(self.current_node)
                self.current_node = parent

            def enterEveryRule(self, ctx):
                name = self.parser.ruleNames[ctx.getRuleIndex()]
                node = HDDRule(name)
                if not self.root:
                    self.root = node
                else:
                    assert self.current_node
                    self.current_node.add_child(node)
                self.current_node = node

            def exitEveryRule(self, ctx):
                # If the input contains syntax error, then the last optional block was may not closed.
                while isinstance(self.current_node, HDDQuantifier):
                    self.exit_optional()

                assert self.current_node.name == self.parser.ruleNames[ctx.getRuleIndex()], \
                    f'{self.current_node.name} ({self.current_node!r}) != {self.parser.ruleNames[ctx.getRuleIndex()]}'

                if self.current_node.parent:
                    self.current_node = self.current_node.parent

            def tokenBoundaries(self, token):
                start = Position(token.line, token.column)
                return start, start.after(token.text)

            def addToken(self, node, child):
                if not self.seen_terminal:
                    hidden_tokens = self.parser.getTokenStream().getHiddenTokensToLeft(node.symbol.tokenIndex, -1) or []
                    for token in hidden_tokens:
                        start, end = self.tokenBoundaries(token)
                        self.current_node.add_child(HDDHiddenToken(self.parser.symbolicNames[token.type], token.text,
                                                                   start=start, end=end))
                self.seen_terminal = True

                self.current_node.add_child(child)

                hidden_tokens = self.parser.getTokenStream().getHiddenTokensToRight(node.symbol.tokenIndex, -1) or []
                for token in hidden_tokens:
                    start, end = self.tokenBoundaries(token)
                    self.current_node.add_child(HDDHiddenToken(self.parser.symbolicNames[token.type], token.text,
                                                               start=start, end=end))

            def visitTerminal(self, node):
                token = node.symbol
                name, text = (self.parser.symbolicNames[token.type], token.text) if token.type != Token.EOF else ('EOF', '')
                start, end = self.tokenBoundaries(token)

                child = HDDToken(name, text, start=start, end=end)
                self.addToken(node, child)
                if name in grammar['islands']:
                    self.island_nodes.append(child)

            def visitErrorNode(self, node):
                if hasattr(node, 'symbol'):
                    token = node.symbol
                    start, end = self.tokenBoundaries(token)
                    self.addToken(node, HDDErrorToken(token.text, start=start, end=end))

            def enter_optional(self):
                quant_node = HDDQuantifier()
                self.current_node.add_child(quant_node)
                self.current_node = quant_node

            def exit_optional(self):
                assert self.current_node.parent, 'Quantifier node has no parent.'
                assert self.current_node.children, 'Quantifier node has no children.'

                self.current_node = self.current_node.parent

        input_format[grammar_name].update(lexer=ExtendedTargetLexer, parser=ExtendedTargetParser, listener=ExtendedTargetListener, replacements=replacements)

    class ExtendedErrorListener(error.ErrorListener.ErrorListener):

        def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
            t = CommonToken(source=(recognizer, recognizer._input),
                            type=Token.INVALID_TYPE,
                            channel=Token.DEFAULT_CHANNEL,
                            start=recognizer._tokenStartCharIndex,
                            stop=recognizer._tokenStartCharIndex)
            t.line = recognizer._tokenStartLine
            t.column = recognizer._tokenStartColumn
            recognizer._type = Token.MIN_USER_TOKEN_TYPE
            recognizer.emitToken(t)

    def build_hdd_tree(src, grammar_name, start_rule):
        """
        Parse the input with the provided ANTLR classes.

        :param src: Input source.
        :param grammar_name: Name of the grammar to use for parsing.
        :param start_rule: The name of the start rule of the parser.
        :return: The root of the created HDD tree.
        """

        grammar = input_format[grammar_name]
        island_nodes = []

        def set_replacement(node):
            if isinstance(node, (HDDQuantifier, HDDErrorToken)):
                node.replace = ''
            elif isinstance(node, HDDRule):
                node.replace = grammar['replacements'][node.name]
            else:
                node.replace = grammar['replacements'].get(node.name, node.text)

            if isinstance(node, HDDRule):
                for child in node.children:
                    set_replacement(child)

        logger.debug('Parse input with %s rule', start_rule)
        if lang != 'python':

            def hdd_tree_from_dict(node_dict):
                # Convert interval dictionaries to Position objects.
                if 'start' in node_dict:
                    node_dict['start'] = Position(**node_dict['start'])
                if 'end' in node_dict:
                    node_dict['end'] = Position(**node_dict['end'])

                name = node_dict.get('name', None)
                children = node_dict.pop('children', None)
                cls = globals()[node_dict.pop('type')]
                node = cls(**node_dict)

                if children:
                    for child in children:
                        node.add_child(hdd_tree_from_dict(child))
                elif name:
                    if name in grammar['islands']:
                        island_nodes.append(node)
                return node

            try:
                current_workdir = join(work_dir, grammar_name) if grammar_name else work_dir
                proc = run(('java', '-classpath', java_classpath(current_workdir), f'Extended{grammar["parser"]}', start_rule),
                           input=src, stdout=PIPE, stderr=PIPE, universal_newlines=True, cwd=current_workdir, check=True)
                if proc.stderr:
                    logger.debug(proc.stderr)
                result = xson.loads(proc.stdout)
                tree_root = hdd_tree_from_dict(result)
            except CalledProcessError as e:
                logger.error('Java parser failed!\n%s\n%s', e.stdout, e.stderr)
                raise
        else:
            lexer = grammar['lexer'](InputStream(src))
            lexer.addErrorListener(ExtendedErrorListener())
            target_parser = grammar['parser'](CommonTokenStream(lexer))
            parser_listener = grammar['listener'](target_parser)
            target_parser.addParseListener(parser_listener)

            getattr(target_parser, start_rule)()
            target_parser.syntax_error_warning()
            island_nodes = parser_listener.island_nodes
            assert parser_listener.root == parser_listener.current_node
            tree_root = parser_listener.root

        # Traverse the HDD tree and set minimal replacements for nodes.
        set_replacement(tree_root)
        process_island_nodes(island_nodes, grammar['islands'])
        logger.debug('Parse done.')
        return tree_root

    def process_island_nodes(island_nodes, island_format):
        for node in island_nodes:
            if not isinstance(island_format[node.name], tuple):
                rewritten, mapping = rename_regex_groups(island_format[node.name])
                for new_name, old_name in mapping.items():
                    grammar_name, rule_name = split_grammar_rule_name(old_name)
                    mapping[new_name] = (grammar_name, rule_name)
                    if 'lexer' not in input_format[grammar_name]:
                        prepare_parsing(grammar_name)
                island_format[node.name] = (re.compile(rewritten, re.S), mapping)

            new_node = HDDRule(node.name, replace=node.replace)
            new_node.add_children(build_island_subtree(node, *island_format[node.name]))
            node.replace_with(new_node)

    def build_island_subtree(node, pattern, mapping):
        """
        Process terminal with an island grammar.

        :param node: HDDToken object containing island language.
        :return: List of HDDTree nodes representing the `children` of node.
        """
        last_processed = 0
        content = node.text
        children = []

        # Intervals describes a non-overlapping splitting of the content according to the pattern.
        intervals = []
        for m in re.finditer(pattern, content):
            intervals.extend((g, m.start(g), m.end(g)) for g in list(pattern.groupindex.keys()) if m.start(g) != m.end(g))
        intervals.sort(key=lambda x: (x[1], x[2]))

        def shift_positions(node, start):
            if node.start:
                node.start.shift(start)
            if node.end:
                node.end.shift(start)

            if isinstance(node, HDDRule):
                for child in node.children:
                    shift_positions(child, start)

        for interval in intervals:
            # Create simple HDDToken of the substring proceeding a subgroup.
            if last_processed < interval[1]:
                token_start = node.start.after(content[0:last_processed])
                token_text = content[last_processed:interval[1]]
                children.append(HDDToken('', token_text,
                                         start=token_start,
                                         end=token_start.after(token_text),
                                         replace=token_text))

            # Process an island and save its subtree.
            island_start = node.start.after(content[0:interval[1]])
            island_root = build_hdd_tree(src=content[interval[1]:interval[2]],
                                         grammar_name=mapping[interval[0]][0],
                                         start_rule=mapping[interval[0]][1])
            shift_positions(island_root, island_start)
            children.append(island_root)

            last_processed = interval[2]

        # Create simple HDDToken of the substring following the last subgroup if any.
        if last_processed < len(content):
            token_start = node.start.after(content[0:last_processed])
            token_text = content[last_processed:]
            children.append(HDDToken('', token_text,
                                     start=token_start,
                                     end=token_start.after(token_text),
                                     replace=token_text))
        return children

    def calculate_rule_boundaries(node):
        if isinstance(node, HDDRule):
            for child in node.children:
                calculate_rule_boundaries(child)

            node.start = node.children[0].start
            node.end = node.children[-1].end

        return node

    def remove_hidden_tokens(node):
        if isinstance(node, HDDRule):
            non_hidden_children = []

            for child in node.children:
                if not isinstance(child, HDDHiddenToken):
                    remove_hidden_tokens(child)
                    non_hidden_children.append(child)

            node.children[:] = non_hidden_children

        return node

    _NAMED_GRP_PATTERN = re.compile(r'(?<!\\)(\(\?P<[^>]*>)')   # "(?P<NAME>" not prefixed by a "\"
    _NAMED_GRP_PREFIX = '(?P<'
    _NAMED_GRP_SUFFIX = '>'
    _NAMED_REF_PATTERN = re.compile(r'(?<!\\)(\(\?P=[^)]*\))')  # "(?P=NAME)" not prefixed by a "\"
    _NAMED_REF_PREFIX = '(?P='
    _NAMED_REF_SUFFIX = ')'

    def rename_regex_groups(pattern):
        """
        Rewrite capture group names in a regex pattern to ensure that the names
        are valid Python identifiers (as expected by the ``re`` module). This
        enables more sophisticated capture group names than allowed by default.

        :param str pattern: the original regex pattern with potentially extended
            syntax for capture group names.
        :return: the rewritten regex pattern and a mapping from the newly
            introduced capture group names (which are guaranteed to by valid
            Python identifiers) to the names used in the original pattern.
        :rtype: tuple(str, dict(str, str))

        .. note::

           The function expects ``pattern`` to be syntactically valid. Its
           behavior is undefined for erroneous input.
        """

        grp_rewritten = ''
        mapping = {}
        rmapping = {}
        cnt = 1
        for item in _NAMED_GRP_PATTERN.split(pattern):
            if _NAMED_GRP_PATTERN.match(item):
                old_name = item[len(_NAMED_GRP_PREFIX):-len(_NAMED_GRP_SUFFIX)]
                new_name = 'G' + str(cnt)
                cnt += 1

                mapping[new_name] = old_name
                rmapping[old_name] = new_name

                item = _NAMED_GRP_PREFIX + new_name + _NAMED_GRP_SUFFIX

            grp_rewritten += item

        ref_rewritten = ''
        for item in _NAMED_REF_PATTERN.split(grp_rewritten):
            if _NAMED_REF_PATTERN.match(item):
                old_name = item[len(_NAMED_REF_PREFIX):-len(_NAMED_REF_SUFFIX)]
                new_name = rmapping.get(old_name, old_name)

                item = _NAMED_REF_PREFIX + new_name + _NAMED_REF_SUFFIX

            ref_rewritten += item

        return ref_rewritten, mapping

    def split_grammar_rule_name(name):
        """
        Determine the grammar and the rule parts in a potentially
        grammar-prefixed rule name. The syntax for the prefixed format is
        "[grammar:]rule", where "[]" denote optionality and the default for a
        missing grammar part is the empty string.

        :param str name: a potentially grammar-prefixed rule name.
        :return: a 2-tuple of the grammar and the rule name parts.
        :rtype: tuple(str, str)
        """

        names = name.split(':', 1)
        if len(names) < 2:
            names.insert(0, '')
        return names[0], names[1]

    start_grammar, start_rule = split_grammar_rule_name(start)
    prepare_parsing(start_grammar)
    tree = build_hdd_tree(src=src,
                          grammar_name=start_grammar,
                          start_rule=start_rule)
    if not hidden_tokens:
        tree = remove_hidden_tokens(tree)
    tree = remove_empty_nodes(tree)
    tree = calculate_rule_boundaries(tree)
    return tree
