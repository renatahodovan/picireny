# Copyright (c) 2016-2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import json
import logging
import re
import sys

from os import makedirs, pathsep
from os.path import basename, isdir, join
from pkgutil import get_data
from string import Template
from subprocess import CalledProcessError, PIPE, Popen

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
    def __init__(self, start=None, end=None):
        HDDRule.__init__(self, '', start=start, end=end)


class HDDHiddenToken(HDDToken):
    """
    Special token type that represents tokens from hidden channels.
    """
    pass


class HDDErrorToken(HDDToken):
    """
    Special token type that represents unmatched tokens. The minimal replacement
    of such nodes is an empty string.
    """
    def __init__(self, text, start, end):
        HDDToken.__init__(self, '', text, start=start, end=end)


# Override ConsoleErrorListener to suppress parse issues in non-verbose mode.
class ConsoleListener(error.ErrorListener.ConsoleErrorListener):
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        logger.debug('line %d:%d %s', line, column, msg)


error.ErrorListener.ConsoleErrorListener.INSTANCE = ConsoleListener()


def create_hdd_tree(input_stream, input_format, start, antlr, work_dir, hidden_tokens=False, lang='python'):
    """
    Build a tree that the HDD algorithm can work with.

    :param input_stream: ANTLR stream (FileStream or InputStream) representing
        the input.
    :param input_format: Dictionary describing the input format.
    :param start: Name of the start rule in [grammarname:]rulename format.
    :param antlr: Path to the ANTLR4 tool (Java jar binary).
    :param work_dir: Working directory.
    :param hidden_tokens: Build hidden tokens of the input format into the HDD
        tree.
    :param lang: The target language of the parser.
    :return: The root of the created HDD tree.
    """

    grammar_workdir = join(work_dir, 'target')

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

    def build_antlr_grammars():
        """
        Build parsers to parse ANTLR4 grammars.

        :return: References to the ANTLR4 lexer and parser classes.
        """
        antlr4_workdir = join(work_dir, 'antlr4')
        if not isdir(antlr4_workdir):
            makedirs(antlr4_workdir)
        if antlr4_workdir not in sys.path:
            sys.path.append(antlr4_workdir)

        # Copy the resources needed to interpret the input grammars.
        for resource in ['LexerAdaptor.py', 'ANTLRv4Lexer.g4', 'ANTLRv4Parser.g4', 'LexBasic.g4']:
            with open(join(antlr4_workdir, resource), 'wb') as f:
                f.write(get_data(__package__, join('resources', resource)))

        antlr_lexer_class, antlr_parser_class, _ = build_grammars((join(antlr4_workdir, 'ANTLRv4Lexer.g4'),
                                                                   join(antlr4_workdir, 'ANTLRv4Parser.g4'),
                                                                   join(antlr4_workdir, 'LexBasic.g4')),
                                                                  antlr4_workdir,
                                                                  antlr)
        logger.debug('ANTLR4 grammars processed...')
        return antlr_lexer_class, antlr_parser_class

    def java_classpath(current_workdir):
        return pathsep.join([antlr, current_workdir])

    def compile_java_sources(lexer, parser, listener, current_workdir):
        executor = Template(get_data(__package__, join('resources', 'ExtendedTargetParser.java')).decode('utf-8'))
        with open(join(current_workdir, 'Extended{parser}.java'.format(parser=parser)), 'w') as f:
            f.write(executor.substitute(dict(lexer_class=lexer,
                                             parser_class=parser,
                                             listener_class=listener)))
        cmd = 'javac -classpath {classpath} *.java'.format(classpath=java_classpath(current_workdir))
        proc = Popen(cmd, shell=True, cwd=current_workdir, stdout=PIPE, stderr=PIPE)
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            logger.error('Java compile failed!\n%s\n%s\n', stdout, stderr)
            raise CalledProcessError(returncode=proc.returncode, cmd=cmd, output=stdout + stderr)

    def prepare_parsing(grammar_name):
        """
        Performs initiative steps needed to parse the input test case (like
        create directory structures, builds grammars, sets PATH, etc...)

        :param grammar_name: Name of the grammar to use for parsing.
        """
        grammar = input_format[grammar_name]
        antlr_lexer_class, antlr_parser_class = build_antlr_grammars()
        replacements, action_positions = analyze_grammars(antlr_lexer_class, antlr_parser_class, grammar['files'], grammar['replacements'])
        logger.debug('Replacements are calculated...')

        current_workdir = join(grammar_workdir, grammar_name) if grammar_name else grammar_workdir
        if not isdir(current_workdir):
            makedirs(current_workdir)
        if current_workdir not in sys.path:
            sys.path.append(current_workdir)

        # Inject actions into the target grammars to help localizing part of the test case that are optional.
        for i, g in enumerate(grammar['files']):
            grammar['files'][i] = join(current_workdir, basename(g))
            inject_optional_actions(g, action_positions[g], grammar['files'][i])

        target_lexer_class, target_parser_class, target_listener_class = build_grammars(tuple(grammar['files']), current_workdir, antlr, lang)
        logger.debug('Target grammars are processed...')

        if lang == 'java':
            compile_java_sources(target_lexer_class, target_parser_class, target_listener_class, current_workdir)
            input_format[grammar_name].update({'lexer': target_lexer_class, 'parser': target_parser_class, 'listener': target_listener_class, 'replacements': replacements})
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
                target_parser_class.enterRecursionRule(self, localctx, state, ruleIndex, precedence)
                self.trigger_listener('recursion_enter')

            def pushNewRecursionContext(self, localctx, state, ruleIndex):
                target_parser_class.pushNewRecursionContext(self, localctx, state, ruleIndex)
                self.trigger_listener('recursion_push')

            def unrollRecursionContexts(self, parentCtx):
                target_parser_class.unrollRecursionContexts(self, parentCtx)
                self.trigger_listener('recursion_unroll')

            def trigger_listener(self, event):
                for listener in self.getParseListeners():
                    if hasattr(listener, event):
                        getattr(listener, event)()

            def syntax_error_warning(self):
                if self._syntaxErrors:
                    logger.warning('%s finished with %d syntax errors. This may decrease reduce quality.',
                                   target_parser_class.__name__, self._syntaxErrors)

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
                    '%s (%s) != %s' % (self.current_node.name, repr(self.current_node), self.parser.ruleNames[ctx.getRuleIndex()])

                if self.current_node.parent:
                    self.current_node = self.current_node.parent

            def tokenBoundaries(self, token):
                line_breaks = token.text.count('\n')
                return Position(token.line, token.column), \
                    Position(token.line + line_breaks,
                             token.column + len(token.text) if not line_breaks else len(token.text) - token.text.rfind('\n'))

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

            def print_tree(self):
                if self.root and logger.isEnabledFor(logging.DEBUG):
                    logger.debug(self.root.tree_str(current=self.current_node))

        input_format[grammar_name].update({'lexer': ExtendedTargetLexer, 'parser': ExtendedTargetParser, 'listener': ExtendedTargetListener, 'replacements': replacements})

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

    def build_hdd_tree(input_stream, grammar_name, start_rule):
        """
        Parse the input with the provided ANTLR classes.

        :param input_stream: ANTLR stream (FileStream or InputStream)
            representing the input.
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

        logger.debug('Parse input with %s rule', start_rule)
        if lang != 'python':

            def hdd_tree_from_json(node_dict):
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
                        node.add_child(hdd_tree_from_json(child))
                elif name:
                    if name in grammar['islands']:
                        island_nodes.append(node)
                return node

            current_workdir = join(grammar_workdir, grammar_name) if grammar_name else grammar_workdir
            cmd = 'java -classpath {classpath} Extended{parser} {start_rule}'.format(classpath=java_classpath(current_workdir),
                                                                                     parser=grammar['parser'],
                                                                                     start_rule=start_rule)
            proc = Popen(cmd, cwd=current_workdir, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, universal_newlines=True)
            stdout, stderr = proc.communicate(input=input_stream.strdata)
            if proc.returncode != 0:
                logger.error('Java parser failed!\n%s\n%s', stdout, stderr)
                raise CalledProcessError(returncode=proc.returncode, cmd=cmd, output=stdout + stderr)
            result = json.loads(stdout)
            tree_root = hdd_tree_from_json(result)
        else:
            lexer = grammar['lexer'](input_stream)
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
        tree_root.traverse(set_replacement)
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

        for interval in intervals:
            # Create simple HDDToken of the substring proceeding a subgroup.
            if last_processed < interval[1]:
                next_token_text = content[last_processed:interval[1]]
                prefix = content[0:last_processed]
                children.append(HDDToken(name='',
                                         text=next_token_text,
                                         start=Position(node.start.line + content[0:last_processed].count('\n'),
                                                        len(prefix) - prefix.rfind('\n')),
                                         end=Position(node.start.line + next_token_text.count('\n'),
                                                      len(next_token_text) - next_token_text.rfind('\n')),
                                         replace=next_token_text))

            # Process an island and save its subtree.
            children.append(build_hdd_tree(input_stream=InputStream(content[interval[1]:interval[2]]),
                                           grammar_name=mapping[interval[0]][0],
                                           start_rule=mapping[interval[0]][1]))
            last_processed = interval[2]

        # Create simple HDDToken of the substring following the last subgroup if any.
        if last_processed < len(content):
            next_token_text = content[last_processed:]
            prefix = content[0:last_processed]
            children.append(HDDToken(name='',
                                     text=next_token_text,
                                     start=Position(node.start.line + content[0:last_processed].count('\n'),
                                                    len(prefix) - prefix.rfind('\n')),
                                     end=Position(node.start.line + next_token_text.count('\n'),
                                                  len(next_token_text) - next_token_text.rfind('\n')),
                                     replace=next_token_text))
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
        mapping = dict()
        rmapping = dict()
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
    tree = build_hdd_tree(input_stream=input_stream,
                          grammar_name=start_grammar,
                          start_rule=start_rule)
    if not hidden_tokens:
        tree = remove_hidden_tokens(tree)
    tree = remove_empty_nodes(tree)
    tree = calculate_rule_boundaries(tree)
    return tree
