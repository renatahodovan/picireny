# Copyright (c) 2021 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from .empty_dd import EmptyDD
from .unparser import Unparser


def prune(hdd_tree, config_nodes, reduce_class, reduce_config, tester_class, tester_config, test_pattern, id_prefix,
          cache, unparse_with_whitespace):
    """
    Pruning-based reduction of a set of nodes (i.e., sub-trees), as used by
    various hierarchical delta debugging algorithm variants.

    :param hdd_tree: The root of the tree.
    :param config_nodes: The list of nodes to reduce.
    :param reduce_class: Reference to the reducer class (LightDD, ParallelDD or
        CombinedParallelDD from the picire module).
    :param reduce_config: Dictionary containing the parameters of the
        reduce_class init function.
    :param tester_class: Reference to a callable class that can decide about the
        interestingness of a test case.
    :param tester_config: Dictionary containing the parameters of the tester
        class init function (except test_builder).
    :param test_pattern: The pattern of the test's path. It contains one %s part
        that will be replaced with the ID of the certain configurations.
    :param id_prefix: Tuple to prepend to config IDs during tests.
    :param cache: Cache to use.
    :param unparse_with_whitespace: Build test case by adding whitespace between
        nonadjacent tree nodes during unparsing.
    :return: Tuple: (root of the tree, bool whether the tree changed)
    """

    config_ids = [node.id for node in config_nodes]
    config_ids_set = set(config_ids)

    test_builder = Unparser(hdd_tree, config_ids_set, with_whitespace=unparse_with_whitespace)
    if cache:
        cache.clear()
        cache.set_test_builder(test_builder)

    test = tester_class(test_builder=test_builder, test_pattern=test_pattern, **tester_config)
    dd = reduce_class(test, cache=cache, id_prefix=id_prefix, **reduce_config)
    c = dd.ddmin(config_ids)
    if len(c) == 1:
        dd = EmptyDD(test, cache=cache, id_prefix=id_prefix)
        c = dd.ddmin(c)
    c = set(c)
    hdd_tree.set_state(config_ids_set, c)

    return hdd_tree, len(c) < len(config_ids_set)
