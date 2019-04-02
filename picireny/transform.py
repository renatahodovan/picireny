# Copyright (c) 2017-2019 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from .hdd_tree import HDDRule, HDDToken


def remove_empty_nodes(node):
    """
    Delete those nodes from the HDD tree that don't contribute to the output at
    all (tokens with empty text, e.g., the EOF token; and rules with no
    children, e.g., lambda rules).

    :param node: The root of the tree to be transformed.
    :return: The root of the transformed tree.
    """
    if isinstance(node, HDDRule):
        non_empty_children = []

        for child in node.children:
            if isinstance(child, HDDToken):
                # empty token is usually the EOF only (but interestingly, it may
                # appear multiple times in the tree)
                if child.text != '':
                    non_empty_children.append(child)
            else:
                assert isinstance(child, HDDRule)
                remove_empty_nodes(child)

                # a grammar may contain lambda rules (with nothing on the
                # right-hand side, or with an empty alternative), or rules that
                # produce EOF only (which is removed in the branch above)
                if child.children:
                    non_empty_children.append(child)

        node.children[:] = non_empty_children

    return node


def flatten_recursion(node):
    """
    Heuristics to flatten left or right-recursion. E.g., given a rule
        rule : a | rule b
    and a HDD tree built with it from an input, rewrite the resulting HDD tree
    as if it was built using
        rule : a b*
    This allows HDD to potentially completely remove the recurring blocks
    (instead of replacing them with their minimal replacement, which is usually
    not "").

    :param node: The root of the tree to be transformed.
    :return: The root of the transformed tree.
    """
    if isinstance(node, HDDRule) and node.state == node.KEEP:
        for child in node.children:
            flatten_recursion(child)

        if len(node.children) > 1 and node.name:
            if node.children[0].name == node.name:
                left = node.children[0]

                right = HDDRule('', replace='', start=node.children[1].start, end=node.children[-1].end)
                right.add_children(node.children[1:])
                del node.children[:]

                node.add_children(left.children)
                node.add_child(right)

            elif node.children[-1].name == node.name:
                right = node.children[-1]

                left = HDDRule('', replace='', start=node.children[0].start, end=node.children[-2].end)
                left.add_children(node.children[0:-1])
                del node.children[:]

                node.add_child(left)
                node.add_children(right.children)

        # This only seems to happen if there was some error during parsing.
        # In this case a weird 1-step chain gets inserted into the left/right-
        # recursive tree, which prevents flattening. But we cannot postpone the
        # merging of this 1-step chain to squeeze_tree because flatten_recursion
        # is usually not called again afterwards. So, do a degenerate "rotation"
        # (i.e., simple lifting) here.
        if len(node.children) == 1 and node.name:
            if node.children[0].name == node.name:
                child = node.children[0]
                del node.children[:]
                node.add_children(child.children)

    return node


def squeeze_tree(node):
    """
    Compress single line chains in the HDD tree whose minimal replacements are
    the same and hence they would result in redundant checks during the
    minimization.

    :param node: The root of the tree to be transformed.
    :return: The root of the transformed tree.
    """
    if isinstance(node, HDDRule):
        for i, child in enumerate(node.children):
            squeezed_child = squeeze_tree(child)
            if child != squeezed_child:
                node.children[i].replace_with(squeezed_child)

        if len(node.children) == 1 and node.children[0].replace == node.replace:
            return node.children[0]

    return node


def skip_unremovable(node, unparse_with_whitespace=True):
    """
    Mark those nodes as removed whose unparsing (e.g., for tokens, their text)
    is the same tokens as their minimal replacement, thus hiding them from
    hddmin, because they just cause extra test runs but cannot reduce the input.

    :param node: The root of the tree to be transformed.
    :return: The root of the transformed tree.
    """
    if isinstance(node, HDDRule):
        for child in node.children:
            skip_unremovable(child)

    if node.unparse(with_whitespace=unparse_with_whitespace) == node.replace:
        node.state = node.REMOVED

    return node


def skip_whitespace(node):
    """
    Mark tokens with whitespace-only text as removed. Useful when hidden-channel
    tokens are built into the tree to let hddmin deal with
    hidden-but-non-whitespace tokens only.

    :param node: The root of the tree to be transformed.
    :return: The root of the transformed tree.
    """
    if isinstance(node, HDDRule):
        for child in node.children:
            skip_whitespace(child)
    else:
        assert isinstance(node, HDDToken)
        if node.text.isspace():
            node.state = node.REMOVED

    return node
