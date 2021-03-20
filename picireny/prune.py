# Copyright (c) 2021 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging

from copy import copy

from picire import AbstractDD

logger = logging.getLogger(__name__)


class PruningTestBuilder(object):

    def __init__(self, tree, ids, with_whitespace=True):
        """
        Initialize the test builder.

        :param tree: Tree representing the current test case.
        :param ids: The IDs of nodes that can change status.
        :param with_whitespace: Unparse by adding whitespace between nonadjacent
            nodes.
        """
        self.tree = tree
        self.ids = ids
        self.with_whitespace = with_whitespace

    def __call__(self, config):
        """
        :param config: List of IDs of nodes that will be kept in the next test
            case.
        :return: The unparsed test case containing only the units defined in
            config.
        """
        def removed(node):
            if node.id in self.ids and node.id not in config:
                removed_node = copy(node)
                removed_node.state = removed_node.REMOVED
                return removed_node
            return node

        config = set(config)
        return self.tree.unparse(with_whitespace=self.with_whitespace, transform=removed)


class EmptyDD(AbstractDD):
    """
    Special DD variant that *does* test the empty configuration (and nothing
    else).
    """

    def __init__(self, test, cache=None, id_prefix=()):
        """
        Initialize an EmptyDD object.

        :param test: A callable tester object.
        :param cache: Cache object to use.
        :param id_prefix: Tuple to prepend to config IDs during tests.
        """
        AbstractDD.__init__(self, test=test, split=None, cache=cache, id_prefix=id_prefix)

    def ddmin(self, config):
        """
        Return a 1-minimal failing subset of the initial configuration, and also
        test the empty configuration while doing so.

        Note: The initial configuration is expected to be of size 1, thus the
        1-minimal failing subset is always its trivial subset: either itself or
        the empty configuration.

        :param config: The initial configuration that will be reduced.
        :return: 1-minimal failing configuration.
        """
        assert len(config) == 1
        # assert self._test_config(config, ('assert',)) == self.FAIL

        emptyset = []
        config_id = ('empty',)

        logger.info('Run: trying 0.')

        outcome = self._lookup_cache(emptyset, config_id) or self._test_config(emptyset, config_id)
        if outcome == self.FAIL:
            logger.info('Reduced to 0 units.')
            logger.debug('New config: %r.', emptyset)

            logger.info('Done.')
            return emptyset

        logger.info('Done.')
        return config


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

    test_builder = PruningTestBuilder(hdd_tree, config_ids_set, with_whitespace=unparse_with_whitespace)
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

    def _set_state(node):
        if node.id in config_ids_set:
            node.state = node.KEEP if node.id in c else node.REMOVED
        elif hasattr(node, 'children') and node.state == node.KEEP:
            for child in node.children:
                _set_state(child)
    _set_state(hdd_tree)

    return hdd_tree, len(c) < len(config_ids_set)
