# Copyright (c) 2018-2021 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import itertools
import logging

from os.path import join

from .hoist import hoist
from .prune import prune

logger = logging.getLogger(__name__)


def hddrmin(hdd_tree, reduce_class, reduce_config, tester_class, tester_config, test_name, work_dir,
            hdd_star=True, id_prefix=(), cache=None, config_filter=None, unparse_with_whitespace=True,
            pop_first=False, append_reversed=False,
            pruning=True, hoisting=False):
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
    :param reduce_class: Reference to the reducer class (LightDD, ParallelDD or
        CombinedParallelDD from the picire module).
    :param reduce_config: Dictionary containing the parameters of the
        reduce_class init function.
    :param tester_class: Reference to a callable class that can decide about the
        interestingness of a test case.
    :param tester_config: Dictionary containing the parameters of the tester
        class init function (except test_builder).
    :param test_name: Name of the test case file.
    :param work_dir: Directory to save temporary test files.
    :param hdd_star: Boolean to enable the HDD star algorithm.
    :param id_prefix: Tuple to prepend to config IDs during tests.
    :param cache: Cache to use.
    :param config_filter: Filter function from node to boolean, to allow running
        hddmin selectively.
    :param unparse_with_whitespace: Build test case by adding whitespace between
        nonadjacent tree nodes during unparsing.
    :param pop_first: Boolean to control tree traversal (see above for details).
    :param append_reverse: Boolean to control tree traversal (see above for
        details).
    :param pruning: Binary flag denoting whether pruning is to be run at each
        node.
    :param hoisting: Binary flag denoting whether hoisting is to be run at each
        node.
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
            if not children:
                continue

            logger.info('Checking node #%d ...', node_cnt)

            if pruning:
                hdd_tree, pruned = prune(hdd_tree=hdd_tree, config_nodes=children,
                                         reduce_class=reduce_class, reduce_config=reduce_config,
                                         tester_class=tester_class, tester_config=tester_config,
                                         test_pattern=join(work_dir, 'iter_%d' % iter_cnt, 'node_%d' % node_cnt, 'prune', '%s', test_name),
                                         id_prefix=id_prefix + ('i%d' % iter_cnt, 'n%d' % node_cnt, 'p'),
                                         cache=cache, unparse_with_whitespace=unparse_with_whitespace)
                changed = changed or pruned

            if hoisting:
                hdd_tree, hoisted = hoist(hdd_tree=hdd_tree, config_nodes=children,
                                          tester_class=tester_class, tester_config=tester_config,
                                          test_pattern=join(work_dir, 'iter_%d' % iter_cnt, 'node_%d' % node_cnt, 'hoist', '%s', test_name),
                                          id_prefix=id_prefix + ('i%d' % iter_cnt, 'n%d' % node_cnt, 'h'),
                                          cache=cache, unparse_with_whitespace=unparse_with_whitespace)
                changed = changed or hoisted

            for child in node.children if not append_reversed else reversed(node.children):
                if child.state == child.KEEP:
                    queue.append(child)

        if not hdd_star or not changed:
            break

    return hdd_tree
