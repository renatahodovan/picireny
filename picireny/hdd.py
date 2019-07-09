# Copyright (c) 2007 Ghassan Misherghi.
# Copyright (c) 2016-2019 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import itertools
import logging

from os.path import join

from .empty_dd import EmptyDD
from .info import height
from .unparser import Unparser

logger = logging.getLogger(__name__)


def hddmin(hdd_tree, reduce_class, reduce_config, tester_class, tester_config, test_name, work_dir,
           hdd_star=True, cache=None, config_filter=None, unparse_with_whitespace=True, granularity=2):
    """
    Run the hierarchical delta debugging reduce algorithm.

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
    :return: The reduced test case (1-tree-minimal if hdd_star is True and
        config_filter is None).
    """

    def collect_level_nodes(level):
        def _collect_level_nodes(node, current_level):
            if current_level == level and node.state == node.KEEP:
                level_nodes.append(node)
            return current_level + 1
        level_nodes = []  # Using `list` (not `set`) for the sake of stability.
        hdd_tree.inherited_attribute(_collect_level_nodes, 0)
        return level_nodes

    for iter_cnt in itertools.count():
        logger.info('Iteration #%d', iter_cnt)
        hdd_tree.check()

        changed = False
        for level in itertools.count():
            level_nodes = collect_level_nodes(level)
            if not level_nodes:
                break

            if config_filter:
                level_nodes = list(filter(config_filter, level_nodes))
                if not level_nodes:
                    continue

            logger.info('Checking level %d / %d ...', level, height(hdd_tree))

            level_ids = [node.id for node in level_nodes]
            level_ids_set = set(level_ids)

            test_builder = Unparser(hdd_tree, level_ids_set, with_whitespace=unparse_with_whitespace)
            if hasattr(cache, 'set_test_builder'):
                cache.set_test_builder(test_builder)

            test = tester_class(test_builder=test_builder,
                                test_pattern=join(work_dir, 'iter_%d' % iter_cnt, 'level_%d' % level, '%s', test_name),
                                **tester_config)
            id_prefix = ('i%d' % iter_cnt, 'l%d' % level)
            dd = reduce_class(test, cache=cache, id_prefix=id_prefix, **reduce_config)
            c = dd.ddmin(level_ids, n=granularity)
            if len(c) == 1:
                dd = EmptyDD(test, cache=cache, id_prefix=id_prefix)
                c = dd.ddmin(c, n=granularity)
            c = set(c)
            changed = changed or len(c) < len(level_ids_set)
            if cache:
                cache.clear()

            hdd_tree.set_state(level_ids_set, c)

        if not hdd_star or not changed:
            break

    return hdd_tree.unparse(with_whitespace=unparse_with_whitespace)


def coarse_filter(node):
    """
    Config filter to keep nodes with empty replacements only, which is the core
    of the coarse hierarchical delta debugging reduce algorithm.
    """
    return node.replace == ''


def coarse_hddmin(*args, **kwargs):
    """
    Run the coarse hierarchical delta debugging reduce algorithm.

    Note: Same as calling hddmin with coarse_filter as config_filter.
    """
    return hddmin(*args, **dict(kwargs, config_filter=coarse_filter))


def coarse_full_hddmin(*args, **kwargs):
    """
    Run the coarse and the full hierarchical delta debugging reduce algorithms
    in sequence.

    Note: Same as calling coarse_hddmin and hddmin in sequence with the same
    arguments.
    """
    # Note: `args[-1]` is `work_dir`.
    coarse_hddmin(*(args[:-1] + (join(args[-1], 'coarse'),)), **kwargs)
    return hddmin(*(args[:-1] + (join(args[-1], 'full'),)), **kwargs)
