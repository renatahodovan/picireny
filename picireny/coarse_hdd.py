# Copyright (c) 2017-2018 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging

from os.path import join

from .empty_dd import EmptyDD
from .info import height
from .hdd import hddmin
from .unparser import Unparser

logger = logging.getLogger(__name__)


def coarse_hddmin(hdd_tree, reduce_class, reduce_config, tester_class, tester_config, test_name, work_dir,
                  *, hdd_star=True, cache=None, unparse_with_whitespace=True, granularity=2):
    """
    Run the coarse hierarchical delta debugging reduce algorithm.

    :param hdd_tree: The root of the tree that the reduce will work with (it's the output of create_hdd_tree).
    :param reduce_class: Reference to the reducer class (LightDD, ParallelDD or CombinedParallelDD from the
                         picire module).
    :param reduce_config: Dictionary containing the parameters of the reduce_class init function.
    :param tester_class: Reference to a callable class that can decide about the interestingness of a test case.
    :param tester_config: Dictionary containing the parameters of the tester class init function (except test_builder).
    :param test_name: Name of the test case file.
    :param work_dir: Directory to save temporary test files.
    :param hdd_star: Boolean to enable the HDD star algorithm.
    :param cache: Cache to use.
    :param unparse_with_whitespace: Build test case by adding whitespace between nonadjacent tree nodes during unparsing.
    :param granularity: Initial granularity.
    :return: The 1-tree-minimal test case.
    """

    def collect_level_nodes(level):
        def _collect_level_nodes(node, current_level):
            if current_level == level and node.state == node.KEEP:
                level_nodes.append(node)
            return current_level + 1
        level_nodes = []
        hdd_tree.inherited_attribute(_collect_level_nodes, 0)
        return level_nodes

    iter_cnt = 0

    while True:
        logger.info('Iteration #%d', iter_cnt)
        hdd_tree.check()

        level = 0
        changed = False
        level_nodes = collect_level_nodes(level)

        while len(level_nodes):
            level_nodes = list(filter(lambda node: node.replace == '', level_nodes))
            if len(level_nodes):
                logger.info('Checking level %d / %d ...', level, height(hdd_tree))

                level_ids = [node.id for node in level_nodes]
                level_ids_set = set(level_ids)

                test_builder = Unparser(hdd_tree, level_ids_set, with_whitespace=unparse_with_whitespace)
                if hasattr(cache, 'set_test_builder'):
                    cache.set_test_builder(test_builder)

                test = tester_class(test_builder=test_builder,
                                    test_pattern=join(work_dir, 'iter_%d' % iter_cnt, 'level_%d' % level, '%s', test_name),
                                    **tester_config)
                dd = reduce_class(test, cache=cache, **reduce_config)
                c = dd.ddmin(level_ids, n=granularity)
                if len(c) == 1:
                    dd = EmptyDD(test, cache=cache)
                    c = dd.ddmin(c, n=granularity)
                c = set(c)
                changed = changed or len(c) < len(level_ids_set)
                if cache:
                    cache.clear()

                hdd_tree.set_state(level_ids_set, c)

            level += 1
            level_nodes = collect_level_nodes(level)

        if not hdd_star or not changed:
            break

        iter_cnt += 1

    return hdd_tree.unparse(with_whitespace=unparse_with_whitespace)


def coarse_full_hddmin(hdd_tree, reduce_class, reduce_config, tester_class, tester_config, test_name, work_dir,
                       *, hdd_star=True, cache=None, unparse_with_whitespace=True):
    """
    Run the coarse and the full hierarchical delta debugging reduce algorithms
    in sequence.
    """

    coarse_hddmin(hdd_tree, reduce_class, reduce_config, tester_class, tester_config, test_name, join(work_dir, 'coarse'),
                  hdd_star=hdd_star, cache=cache, unparse_with_whitespace=unparse_with_whitespace)
    return hddmin(hdd_tree, reduce_class, reduce_config, tester_class, tester_config, test_name, join(work_dir, 'full'),
                  hdd_star=hdd_star, cache=cache, unparse_with_whitespace=unparse_with_whitespace)
