# Copyright (c) 2021-2026 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging

from copy import copy

from picire import DD, Outcome, ReductionError, ReductionException, ReductionStopped

logger = logging.getLogger(__name__)


class PruningTestBuilder:

    def __init__(self, tree, ids, *, with_whitespace=True):
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


class EmptyDD(DD):
    """
    Special DD variant that *does* test the empty configuration (and nothing
    else).
    """

    def __init__(self, test, *, cache=None, id_prefix=None, stop=None, test_builder=None):
        """
        Initialize an EmptyDD object.

        :param test: A callable tester object.
        :param cache: Cache object to use.
        :param id_prefix: Tuple to prepend to config IDs during tests.
        :param stop: A callable invoked before the execution of every test.
        :param test_builder: Callable that builds test content from a config.
        """
        super().__init__(test=test, cache=cache, id_prefix=id_prefix, stop=stop, test_builder=test_builder)

    def __call__(self, config):
        """
        Return a 1-minimal failing subset of the initial configuration, and also
        test the empty configuration while doing so.

        Note: The initial configuration is expected to be of size 1, thus the
        1-minimal failing subset is always its trivial subset: either itself or
        the empty configuration.

        :param config: The initial configuration that will be reduced.
        :return: 1-minimal failing configuration.
        :raises ReductionException: If reduction could not run until completion.
            The ``result`` attribute of the exception contains the smallest,
            potentially non-minimal, but failing configuration found during
            reduction.
        """
        assert len(config) == 1
        try:
            empty = []
            config_id = ('empty',)

            logger.info('Run #empty')
            logger.info('\tConfig size: %d', len(config))
            logger.debug('\tConfig: %r', config)

            content = self._test_builder(empty)
            outcome = self._lookup_cache(empty, content, config_id)
            if outcome is None:
                self._check_stop()
                outcome = self._test_config(empty, content, config_id)
            if outcome is Outcome.FAIL:
                config = empty
                logger.info('\tReduced')

            logger.info('\tDone')
            return config
        except ReductionStopped as e:
            logger.info('\tStopped')
            e.result = config
            raise
        except Exception as e:
            logger.info('\tErrored')
            raise ReductionError(str(e), result=config) from e


def set_state(hdd_tree, config_ids, keep_ids):
    def _set_state(node):
        if node.id in config_ids:
            node.state = node.KEEP if node.id in keep_ids else node.REMOVED
        elif hasattr(node, 'children') and node.state == node.KEEP:
            for child in node.children:
                _set_state(child)
    _set_state(hdd_tree)


def prune(hdd_tree, config_nodes, *,
          reduce_class, reduce_config, tester_class, tester_config,
          id_prefix, cache, unparse_with_whitespace):
    """
    Pruning-based reduction of a set of nodes (i.e., sub-trees), as used by
    various hierarchical delta debugging algorithm variants.

    :param hdd_tree: The root of the tree.
    :param config_nodes: The list of nodes to reduce.
    :param reduce_class: Reference to the reducer class (DD or ParallelDD from
        the picire module).
    :param reduce_config: Dictionary containing the parameters of the
        reduce_class init function.
    :param tester_class: Reference to a callable class that can decide about the
        interestingness of a test case.
    :param tester_config: Dictionary containing the parameters of the tester
        class init function.
    :param id_prefix: Tuple to prepend to config IDs during tests.
    :param cache: Cache to use.
    :param unparse_with_whitespace: Build test case by adding whitespace between
        nonadjacent tree nodes during unparsing.
    :return: Tuple: (root of the tree, bool whether the tree changed)
    :raises ReductionException: If reduction could not run until completion. The
        ``result`` attribute of the exception contains the smallest, potentially
        non-minimal, but failing tree found during reduction.
    """

    config_ids = [node.id for node in config_nodes]
    config_ids_set = set(config_ids)

    test_builder = PruningTestBuilder(hdd_tree, config_ids_set, with_whitespace=unparse_with_whitespace)
    if cache:
        cache.clear()

    test = tester_class(**tester_config)
    dd = reduce_class(test, cache=cache, id_prefix=id_prefix, test_builder=test_builder, **reduce_config)
    empty_dd = EmptyDD(test, cache=cache, id_prefix=id_prefix, stop=reduce_config.get('stop', None), test_builder=test_builder)

    try:
        config_ids = dd(config_ids)
        if len(config_ids) == 1:
            config_ids = empty_dd(config_ids)
        config_ids = set(config_ids)
        set_state(hdd_tree, config_ids_set, config_ids)
        return hdd_tree, len(config_ids) < len(config_ids_set)
    except ReductionException as e:
        set_state(hdd_tree, config_ids_set, set(e.result))
        e.result = hdd_tree
        raise
