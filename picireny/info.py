# Copyright (c) 2018-2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from .hdd_tree import HDDRule


def count(node, removed=False):
    """
    Count nodes in the tree by type.

    Note: If `removed` is `True`, removed tokens and rules are also counted (but
    sub-trees of removed rules are not).

    :param node: The root of the tree to do the counting for.
    :return: A dictionary of counts indexed by node type name.
    """
    def _count(node):
        if node.state != node.KEEP and not removed:
            return

        ty = node.__class__.__name__
        if ty not in stats:
            stats[ty] = 0
        stats[ty] += 1

        if isinstance(node, HDDRule) and node.state == node.KEEP:
            for child in node.children:
                _count(child)

    stats = dict()
    _count(node)
    return stats


def height(node, removed=False):
    """
    Calculate the height of the tree.

    Note: If `removed` is `True`, removed tokens and rules are also counted (but
    sub-trees of removed rules are not).

    :param node: The root of the tree to do the calculation for.
    :return: The height of the tree.
    """
    if node.state != node.KEEP and not removed:
        return 0

    return 1 + (max((height(child) for child in node.children) if node.children else [0])
                if isinstance(node, HDDRule) and node.state == node.KEEP else 0)


def shape(node, removed=False):
    """
    Calculate the shape of the tree, i.e., the number of nodes on each tree
    level.

    Note: If `removed` is `True`, removed tokens and rules are also counted (but
    sub-trees of removed rules are not).

    :param node: The root of the tree to do the calculation for.
    :return: A list of level sizes.
    """
    def _shape(node, level):
        if node.state != node.KEEP and not removed:
            return

        if len(sizes) <= level:
            sizes.extend([0] * (level - len(sizes) + 1))
        sizes[level] += 1

        if isinstance(node, HDDRule) and node.state == node.KEEP:
            for child in node.children:
                _shape(child, level + 1)

    sizes = []
    _shape(node, 0)
    return sizes
