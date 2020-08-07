# Copyright (c) 2016-2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from antlr4 import CommonTokenStream, FileStream
from antlr4.tree import Tree

from .antlr_tree import *


def analyze_grammars(antlr_lexer, antlr_parser, grammars, replacements):
    """
    Determine the minimal parser rule replacements of the input grammar.

    :param antlr_lexer: Reference to the ANTLR4 lexer class.
    :param antlr_parser: Reference to the ANTLR4 parser class.
    :param grammars: List of the grammars describing the input format.
    :param replacements: Dictionary that contains the predefined minimal
        replacement of any lexer or parser rules. These won't be overridden
        later.
    :return: Pair of the replacement dictionary and the positions of quantified
        elements in the grammars.
    """

    def set_replacements(tree):
        """
        Set the minimal replacements of the various subtrees.

        :param tree: AST-like tree representation built by create_grammar_tree.
        """
        iterate = True
        # Iterate until any updates were performed.
        while iterate:
            iterate = False
            for e in tree:
                # If all of the children have a min set:
                s = isinstance(e, ANTLRLexerElement) and e.calc_starters()
                r = e.calc_replacement()
                if s or r:
                    iterate = True

    # Only those ParseTrees are present in our tree representation that
    # have real effect on the minimal replacements of the rules.
    # e.g. actions, channels, return values, syntax elements (like: |;:), etc
    # are avoided, but e.g. rule definitions, alternations, references,
    # token definitions or such nodes that can have quantifier are kept.
    def create_node(ctx, optional):
        """
        Create tree node of the lexer and parser subtrees.

        :param ctx: The ANTLRRuleContext object under processing.
        :param optional: Boolean indicating whether the current context/node is
            optional or not.
        :return: Node representation of the current context if needed, otherwise
            None.
        """

        # Parser rules.

        if isinstance(ctx, parser.ParserRuleSpecContext):
            # The parserRuleSpec rule contains 3 or 4 terminal tokens and one of them is the ID of the rule.
            # Since we cannot make a distinction between terminals at this point, they have to be referred
            # by indices. Since only the first terminal is optional indexing them from the back is safe
            # (the 3th from back is the rule ID).
            name = [x for x in ctx.children if isinstance(x, Tree.TerminalNodeImpl)][-3].symbol.text
            return ANTLRRule(name, replacements.get(name, None))

        # Alternations need special handling since their minimal replacements are their shortest
        # child (in every other cases the children would be concatenated).
        if isinstance(ctx, (parser.AltListContext, parser.RuleAltListContext)):
            return ANTLRAlternation()

        # Node is created from Alternative to group its element+ children (it's a sequence).
        if isinstance(ctx, parser.AlternativeContext):
            return ANTLRAlternative(repl=('' if not ctx.children else None))

        # LabeledElement and Block are created since they can have quantifier.
        if isinstance(ctx, (parser.LabeledElementContext, parser.BlockContext)):
            return ANTLRElement(optional=optional)

        # Atom can also have quantifier. Furthermore it may have a terminal child
        # (DOT = matching any character) that has to be handled here.
        if isinstance(ctx, parser.AtomContext):
            if isinstance(ctx.children[0], Tree.TerminalNodeImpl):
                assert ctx.children[0] == '.'
                return ANTLRDotElement(optional=optional)
            # Create a base ANTLRElement anyway to make possible applying the quantifier
            # to the subtree.
            return ANTLRElement(optional=optional)

        # Only the reference is set here but in the next step the whole referenced
        # subtree will be plugged as its child.
        if isinstance(ctx, parser.RulerefContext):
            assert ctx.getChildCount() == 1, 'RuleRef must have exactly one child.'
            return ANTLRRef(ctx.children[0].symbol.text, optional=optional)

        # Lexer rules.

        # The main difference between parser and lexer rules in this representation is that
        # lexer rules have an additional field (start_intervals) that aims to track all the
        # possible character ranges that a given token can start with. The purpose of this
        # is being able to generate minimal replacement for a negated lexer rule: having
        # all the possible character intervals that a lexer rule can start with we can easily
        # invert these ranges.
        if isinstance(ctx, parser.LexerRuleSpecContext):
            # Just like at ANTLRRule, the 3rd terminal from the back contains the name of the lexer rule.
            name = [x for x in ctx.children if isinstance(x, Tree.TerminalNodeImpl)][-3].symbol.text
            return ANTLRLexerRule(name, repl=replacements.get(name, None))

        # The same logic as with parser alternations.
        if isinstance(ctx, parser.LexerAltListContext):
            return ANTLRLexerAlternation()

        # The special about LexerAlt is that it can have an empty child which makes
        # possible such alternations in lexer like: ('a'| ). Capturing an empty LexerAlt
        # construction is only possible here, in which case its minimal replacement is
        # the empty string.
        if isinstance(ctx, parser.LexerAltContext):
            # If the alternative has no children means that it's left explicitly empty.
            return ANTLRLexerElement(repl=('' if not ctx.children else None))

        # The special about LexerElements is that by determining its start character range
        # is enough to get the first character of its first child (since it's a token sequence).
        if isinstance(ctx, parser.LexerElementsContext):
            return ANTLRLexerElements()

        # LabeledLexerElement and LexerBlock are created since they can have quantifier.
        if isinstance(ctx, (parser.LabeledLexerElementContext, parser.LexerBlockContext)):
            return ANTLRLexerElement(optional=optional)

        # LexerAtom can also have quantifier. Furthermore it may have terminal children
        # (DOT or character set) that has to be handled here.
        if isinstance(ctx, parser.LexerAtomContext):
            if isinstance(ctx.children[0], Tree.TerminalNodeImpl):
                content = ctx.children[0].symbol.text
                if content == '.':
                    return ANTLRDotElement(optional=optional)
                if content.startswith('['):
                    return ANTLRSetElement(content=content, optional=optional)
                assert False
            # Create a base ANTLRLexerElement anyway to make possible applying the
            # quantifier to the subtree.
            return ANTLRLexerElement(optional=optional)

        if isinstance(ctx, parser.CharacterRangeContext):
            # The 1st and 3rd token of a character range defines its boundaries.
            return ANTLRCharacterRange(ctx.children[0].symbol.text[1:-1], ctx.children[2].symbol.text[1:-1])

        if isinstance(ctx, parser.TerminalContext):
            # Terminal node is either a string literal or a token reference.
            content = ctx.children[0].symbol.text
            if content.startswith(('"', '\'')):
                return ANTLRString(content[1:-1])
            return ANTLRTokenRef(content)

        if isinstance(ctx, parser.NotSetContext):
            return ANTLRNotSet()

        # SetElement is the lexer rule that will be negated.
        if isinstance(ctx, parser.SetElementContext):
            # If the first child is a terminal node then it must be one of the followings:
            # token_ref, string_literal or char set.
            if isinstance(ctx.children[0], Tree.TerminalNodeImpl):
                if ctx.children[0].symbol.text.isupper():
                    return ANTLRTokenRef(ctx.children[0].symbol.text)
                return ANTLRSetElement(content=ctx.children[0].symbol.text)
            # In this case we have a character range.
            return ANTLRSetElement()

        # Tokens without lexer rules.

        # Identifiers in a TokensSpec are definitions of token names without an
        # associated lexer rule. We don't know anything about them, but they are
        # added with a dummy representation to the tree to avoid dead links (as
        # they may be referenced from other (parser) rules).
        if isinstance(ctx, parser.IdentifierContext) and isinstance(ctx.parentCtx, parser.IdListContext) and isinstance(ctx.parentCtx.parentCtx, parser.TokensSpecContext):
            return ANTLRLexerRule(str(ctx.TOKEN_REF()), repl='')

        return None

    def get_quantifier(children, idx):
        """
        Check whether a quantifier is defined on the idx-th children.

        :param children: All the siblings of the current node.
        :param idx: The index of the current node among the siblings.
        :return: Quantifier string of the idx-th context if one is defined, None
            otherwise.
        """
        if len(children) <= idx + 1:
            return None
        suffix = None
        if isinstance(children[idx + 1], parser.EbnfSuffixContext):
            suffix = children[idx + 1].start.text
        elif isinstance(children[idx + 1], parser.BlockSuffixContext):
            suffix = children[idx + 1].children[0].start.text
        return suffix

    def is_optional(quantifier):
        """
        Check whether a quantifier string makes its quantified expression
        optional, i.e., if it allows the expression to occur 0 times.

        :param quantifier: Quantifier string.
        :return: Boolean indicating whether the quantifier is optional or not.
        """
        return quantifier.startswith(('*', '?'))

    def create_grammar_tree(node, positions, parent_idx, optional, parser_rule):
        """
        Creates a tree representation of the target parser grammar to facilitate
        the generation of minimal replacement strings.

        :param node: The ANTLR parser tree whose representation will be inserted
            now.
        :param positions: Dictionary describing positions in grammars where
            optional actions should be injected.
        :param parent_idx: The index of the parent node in the elements list or
            None if without parent.
        :param optional: Boolean deciding if the current node is optional or
            not.
        :param parser_rule: Boolean value indicating if a parser rule being
            processed.
        """
        element = create_node(node, optional)
        if element:
            elements.append(element)
            idx = len(elements) - 1
            if parent_idx is not None:
                elements[parent_idx].children.append(element)
        else:
            idx = parent_idx

        if node.getChildCount() > 0:
            # TerminalNodeImpl nodes already have been added by create_node
            # when processing their parent since at this point we don't know their type.
            for i, c in enumerate(x for x in node.children if not isinstance(x, Tree.TerminalNodeImpl)):
                quantifier = get_quantifier(node.children, i)

                # Mark positions in parser rules that have any quantifier applied on them.
                if quantifier and parser_rule:
                    start_token = parser.getInputStream().get(c.getSourceInterval()[0])
                    end_token = parser.getInputStream().get(c.getSourceInterval()[1])

                    start_ln = start_token.line
                    start = start_token.column

                    line_breaks = end_token.text.count('\n')
                    end_ln = end_token.line + line_breaks
                    end = end_token.column + len(end_token.text) if not line_breaks else \
                        len(end_token.text) - end_token.text.rfind('\n') + 1

                    if start_ln not in positions:
                        positions[start_ln] = []
                    if end_ln not in positions:
                        positions[end_ln] = []

                    positions[start_ln].append(('s', start))
                    positions[end_ln].append(('e', end))

                create_grammar_tree(c, positions, idx, quantifier and is_optional(quantifier),
                                    parser_rule and not isinstance(element, ANTLRLexerRule))

    # EOF is a special token provided by the ANTLR framework. It's added preliminarily to
    # our tree to avoid dead links to it.
    elements = [ANTLRLexerRule('EOF', '')]
    action_positions = {}
    replacements = replacements if replacements else {}
    # Fill elements with node representations.
    for grammar in grammars:
        action_positions[grammar] = {}
        parser = antlr_parser(CommonTokenStream(antlr_lexer(FileStream(grammar, 'utf-8'))))
        create_grammar_tree(parser.grammarSpec(), action_positions[grammar], None, False, True)

    # Create mapping between references and indices of antlr_tree to be able to plug the
    # appropriate subtrees into reference nodes.
    rules = dict((x.name, i) for i, x in enumerate(elements) if isinstance(x, (ANTLRRule, ANTLRLexerRule)))

    # Plug the referred node under the referrers.
    for i, x in enumerate(elements):
        if isinstance(x, (ANTLRRef, ANTLRTokenRef)):
            assert not elements[i].children, 'Referrer nodes must not contain children.'
            elements[i].children = [elements[rules[x.ref]]]

    # Associate tree nodes with minimal string replacements.
    set_replacements(elements)
    return dict((x.name, x.replacement) for x in elements if isinstance(x, (ANTLRRule, ANTLRLexerRule))), action_positions
