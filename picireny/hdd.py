# Copyright (c) 2007 Ghassan Misherghi.
# Copyright (c) 2016-2017 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging

from os.path import join

from .empty_dd import EmptyDD
from .unparser import Unparser

logger = logging.getLogger(__name__)


def hddmin(hdd_tree, reduce_class, reduce_config, tester_class, tester_config, test_name, work_dir,
           *, hdd_star=True, cache=None):
    """
    Run the hierarchical delta debugging reduce algorithm.

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
    :return: The 1-tree-minimal test case.
    """

    def collect_level_ids(level):
        # Don't return a set from collect_level_ids straight away.
        # Node IDs are python object IDs, which are implementation specific
        # (memory addresses in CPython). Memory addresses may/do change from
        # execution to execution, so would change the IDs, and so may change
        # how the ID set is serialized into an ID list (necessary to construct
        # the input config for ddmin). But then, ddmin could potentially give
        # different results -- for the same tree.
        # If a list is used to collect the node IDs, however, then they will
        # always be in the same order, no matter what the actual IDs are.
        def _collect_level_ids(node, current_level):
            if current_level == level and node.state == node.KEEP:
                level_ids.append(node.id)
            return current_level + 1
        level_ids = []
        hdd_tree.inherited_attribute(_collect_level_ids, 0)
        return level_ids

    iter_cnt = 0

    while True:
        logger.info('Iteration #%d', iter_cnt)
        hdd_tree.check()

        level = 0
        changed = False
        level_ids = collect_level_ids(level)

        while len(level_ids):
            logger.info('Checking level %d ...', level)

            level_ids_set = set(level_ids)

            test_builder = Unparser(hdd_tree, level_ids_set)
            if hasattr(cache, 'set_test_builder'):
                cache.set_test_builder(test_builder)

            test = tester_class(test_builder=test_builder,
                                test_pattern=join(work_dir, 'iter_%d' % iter_cnt, 'level_%d' % level, '%s', test_name),
                                **tester_config)
            dd = reduce_class(test, cache=cache, **reduce_config)
            c = dd.ddmin(level_ids)
            if len(c) == 1:
                dd = EmptyDD(test, cache=cache)
                c = dd.ddmin(c)
            c = set(c)
            changed = changed or len(c) < len(level_ids_set)
            if cache:
                cache.clear()

            hdd_tree.set_state(level_ids_set, c)

            level += 1
            level_ids = collect_level_ids(level)

        if not hdd_star or not changed:
            break

        iter_cnt += 1

    return hdd_tree.unparse()
