# Copyright (c) 2018-2021 Renata Hodovan, Akos Kiss.
# Copyright (c) 2021 Daniel Vince
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import itertools
import logging

from .prune import prune

logger = logging.getLogger(__name__)


def hddrmin(hdd_tree, *,
            reduce_class, reduce_config, tester_class, tester_config,
            id_prefix=(), cache=None, unparse_with_whitespace=True,
            config_filter=None, transformations=(prune,), hdd_star=True,
            pop_first=False, append_reversed=False):
    """
    Run the recursive variant of the hierarchical delta debugging reduce
    algorithm (a.k.a. HDDr).

    The tree traversal implementation is actually not recursive but an iterative
    queue-based reformulation of HDDr. How tree nodes are popped from the queue
    during the iteration (whether from the beginning or from the end of the
    queue) and how the children of a visited node are appended to the queue
    (whether they are added in forward or reverse order) give rise to different
    variants of HDDr:

        - 'pop first' with 'forward append' gives the classic breadth-first
          traversal,
        - 'pop first' with 'reverse append' gives syntactically reversed
          breadth-first traversal,
        - 'pop last' with 'reverse append' gives the classic depth-first
          traversal,
        - 'pop last' with 'forward append' gives syntactically reversed
          depth-first traversal.

    :param hdd_tree: The root of the tree that the reduce will work with (it's
        the output of create_hdd_tree).
    :param reduce_class: Reference to the reducer class (DD, ParallelDD or
        CombinedParallelDD from the picire module).
    :param reduce_config: Dictionary containing the parameters of the
        reduce_class init function.
    :param tester_class: Reference to a callable class that can decide about the
        interestingness of a test case.
    :param tester_config: Dictionary containing the parameters of the tester
        class init function (except test_builder).
    :param id_prefix: Tuple to prepend to config IDs during tests.
    :param cache: Cache to use.
    :param unparse_with_whitespace: Build test case by adding whitespace between
        nonadjacent tree nodes during unparsing.
    :param config_filter: Filter function from node to boolean, to allow running
        hddmin selectively.
    :param transformations: Iterable of transformations that reduce a
        configuration of nodes.
    :param hdd_star: Boolean to enable the HDD star algorithm.
    :param pop_first: Boolean to control tree traversal (see above for details).
    :param append_reverse: Boolean to control tree traversal (see above for
        details).
    :return: The reduced test case (1-tree-minimal if hdd_star is True and
        config_filter is None).
    """

    for iter_cnt in itertools.count():
        logger.info('Iteration #%d', iter_cnt)

        changed = False
        queue = [hdd_tree]
        for node_cnt in itertools.count():
            if not queue:
                break
            if pop_first:
                queue, node = queue[1:], queue[0]
            else:
                queue, node = queue[:-1], queue[-1]
            if not hasattr(node, 'children') or node.state != node.KEEP:
                continue

            children = [child for child in node.children if child.state == child.KEEP]
            if config_filter:
                children = list(filter(config_filter, children))

            if children:
                logger.info('Checking node #%d ...', node_cnt)

                for trans_cnt, transformation in enumerate(transformations):
                    hdd_tree, transformed = transformation(hdd_tree, children,
                                                           reduce_class=reduce_class, reduce_config=reduce_config,
                                                           tester_class=tester_class, tester_config=tester_config,
                                                           id_prefix=id_prefix + ('i%d' % iter_cnt, 'n%d' % node_cnt, 't%d' % trans_cnt),
                                                           cache=cache,
                                                           unparse_with_whitespace=unparse_with_whitespace)

                    changed = changed or transformed

            for child in node.children if not append_reversed else reversed(node.children):
                if child.state == child.KEEP:
                    queue.append(child)

        if not hdd_star or not changed:
            break

    return hdd_tree
