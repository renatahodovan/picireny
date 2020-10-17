# Copyright (c) 2007 Ghassan Misherghi.
# Copyright (c) 2016-2021 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import itertools
import logging

from os.path import join

from .info import height
from .prune import prune

logger = logging.getLogger(__name__)


def hddmin(hdd_tree, reduce_class, reduce_config, tester_class, tester_config, test_name, work_dir,
           hdd_star=True, cache=None, config_filter=None, unparse_with_whitespace=True):
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
    :return: The reduced test case (1-tree-minimal if hdd_star is True and
        config_filter is None).
    """

    def collect_level_nodes(level):
        def _collect_level_nodes(node, current_level):
            if node.state != node.KEEP:
                return
            if current_level == level:
                level_nodes.append(node)
            elif hasattr(node, 'children'):
                for child in node.children:
                    _collect_level_nodes(child, current_level + 1)
        level_nodes = []  # Using `list` (not `set`) for the sake of stability.
        _collect_level_nodes(hdd_tree, 0)
        return level_nodes

    for iter_cnt in itertools.count():
        logger.info('Iteration #%d', iter_cnt)

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

            hdd_tree, pruned = prune(hdd_tree=hdd_tree, config_nodes=level_nodes,
                                     reduce_class=reduce_class, reduce_config=reduce_config,
                                     tester_class=tester_class, tester_config=tester_config,
                                     test_pattern=join(work_dir, 'iter_%d' % iter_cnt, 'level_%d' % level, '%s', test_name),
                                     id_prefix=('i%d' % iter_cnt, 'l%d' % level),
                                     cache=cache, unparse_with_whitespace=unparse_with_whitespace)
            changed = changed or pruned

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
