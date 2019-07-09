# Copyright (c) 2018-2019 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import itertools
import logging

from os.path import join

from .empty_dd import EmptyDD
from .unparser import Unparser

logger = logging.getLogger(__name__)


def hddrmin(hdd_tree, reduce_class, reduce_config, tester_class, tester_config, test_name, work_dir,
            hdd_star=True, cache=None, config_filter=None, unparse_with_whitespace=True, granularity=2,
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
    :param cache: Cache to use.
    :param config_filter: Filter function from node to boolean, to allow running
        hddmin selectively.
    :param unparse_with_whitespace: Build test case by adding whitespace between
        nonadjacent tree nodes during unparsing.
    :param granularity: Initial granularity.
    :param pop_first: Boolean to control tree traversal (see above for details).
    :param append_reverse: Boolean to control tree traversal (see above for
        details).
    :return: The reduced test case (1-tree-minimal if hdd_star is True and
        config_filter is None).
    """

    for iter_cnt in itertools.count():
        logger.info('Iteration #%d', iter_cnt)
        hdd_tree.check()

        node_cnt = -1
        changed = False
        queue = [hdd_tree]
        while queue:
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

            node_cnt += 1
            logger.info('Checking node #%d ...', node_cnt)

            children_ids = [child.id for child in children]
            children_ids_set = set(children_ids)

            test_builder = Unparser(hdd_tree, children_ids_set, with_whitespace=unparse_with_whitespace)
            if hasattr(cache, 'set_test_builder'):
                cache.set_test_builder(test_builder)

            test = tester_class(test_builder=test_builder,
                                test_pattern=join(work_dir, 'iter_%d' % iter_cnt, 'node_%d' % node_cnt, '%s', test_name),
                                **tester_config)
            id_prefix = ('i%d' % iter_cnt, 'n%d' % node_cnt)
            dd = reduce_class(test, cache=cache, id_prefix=id_prefix, **reduce_config)
            c = dd.ddmin(children_ids, n=granularity)
            if len(c) == 1:
                dd = EmptyDD(test, cache=cache, id_prefix=id_prefix)
                c = dd.ddmin(c, n=granularity)
            c = set(c)
            changed = changed or len(c) < len(children_ids_set)
            if cache:
                cache.clear()

            hdd_tree.set_state(children_ids_set, c)

            for child in node.children if not append_reversed else reversed(node.children):
                if child.state == child.KEEP:
                    queue.append(child)

        if not hdd_star or not changed:
            break

    return hdd_tree.unparse(with_whitespace=unparse_with_whitespace)
