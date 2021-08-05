# Copyright (c) 2007 Ghassan Misherghi.
# Copyright (c) 2016-2021 Renata Hodovan, Akos Kiss.
# Copyright (c) 2021 Daniel Vince
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import itertools
import logging

from .info import height
from .prune import prune

logger = logging.getLogger(__name__)


def hddmin(hdd_tree, *,
           reduce_class, reduce_config, tester_class, tester_config,
           id_prefix=(), cache=None, unparse_with_whitespace=True,
           config_filter=None, transformations=(prune,), hdd_star=True):
    """
    Run the hierarchical delta debugging reduce algorithm.

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

            for trans_cnt, transformation in enumerate(transformations):
                hdd_tree, transformed = transformation(hdd_tree, level_nodes,
                                                       reduce_class=reduce_class, reduce_config=reduce_config,
                                                       tester_class=tester_class, tester_config=tester_config,
                                                       id_prefix=id_prefix + ('i%d' % iter_cnt, 'l%d' % level, 't%d' % trans_cnt),
                                                       cache=cache,
                                                       unparse_with_whitespace=unparse_with_whitespace)

                changed = changed or transformed

        if not hdd_star or not changed:
            break

    return hdd_tree
