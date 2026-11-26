# Copyright (c) 2021-2026 Renata Hodovan, Akos Kiss.
# Copyright (c) 2021-2026 Daniel Vince.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import itertools
import logging

from picire import DD, Outcome, ReductionError, ReductionException, ReductionStopped

logger = logging.getLogger(__name__)


class HoistingTestBuilder:

    def __init__(self, tree, *, with_whitespace=True):
        """
        Initialize the test builder.

        :param tree: Tree representing the current test case.
        :param with_whitespace: Unparse by adding whitespace between nonadjacent
            nodes.
        """
        self.tree = tree
        self.with_whitespace = with_whitespace

    def __call__(self, mapping_config):
        """
        :param mapping_config: A list of mappings of initial configuration
            elements to new ones.
        :return: The unparsed test case with the mappings applied.
        """
        def map(node):
            return mapping.get(node, node)

        mapping = dict(mapping_config)
        return self.tree.unparse(with_whitespace=self.with_whitespace, transform=map)


class MappingMin(DD):

    def __init__(self, test, *, cache=None, id_prefix=None, stop=None, test_builder=None):
        """
        :param test: A callable tester object.
        :param cache: Cache object to use.
        :param id_prefix: Tuple to prepend to config IDs during tests.
        :param stop: A callable invoked before the execution of every test.
        :param test_builder: Callable that builds test content from a config.
        """

        super().__init__(test=test, cache=cache, id_prefix=id_prefix, stop=stop, test_builder=test_builder)

    def __call__(self, config):
        """
        Compute a mapping of the initial configuration to another (usually
        smaller) but still failing configuration.

        :param config: The initial configuration that will be reduced.
        :return: A mapping of initial configuration elements to new ones.
        :raises ReductionException: If mapping computation could not run until
            completion. The ``result`` attribute of the exception contains the
            best, potentially non-optimal, but failing mapping found
            during reduction.
        """

        def collect_hoistables(node):
            def _collect_hoistables(desc):
                if desc.name == node.name:
                    hoistables.append(desc)
                    return
                if hasattr(desc, 'children') and desc.state == desc.KEEP:
                    for child in desc.children:
                        _collect_hoistables(child)

            hoistables = []
            if hasattr(node, 'children') and node.state == node.KEEP and node.name:
                for child in node.children:
                    _collect_hoistables(child)
            return hoistables

        mapping = {}

        try:
            for run in itertools.count():
                logger.info('Run #%d', run)
                logger.info('\tMapping size: %d', len(mapping))
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug('\tMapping: %r', {c.id: m.id for c, m in mapping.items()})

                for i, (c, m) in enumerate((c, m) for c in config for m in collect_hoistables(mapping.get(c, c))):
                    new_mapping = mapping.copy()
                    new_mapping[c] = m
                    mapping_config = list(new_mapping.items())
                    config_id = (f'r{run}', f'm{i}')

                    content = self._test_builder(mapping_config)
                    outcome = self._lookup_cache(mapping_config, content, config_id)
                    if outcome is None:
                        self._check_stop()
                        outcome = self._test_config(mapping_config, content, config_id)
                    if outcome is Outcome.FAIL:
                        mapping = new_mapping
                        logger.info('\tHoisted')
                        break
                else:
                    break

            logger.info('\tDone')
            return mapping
        except ReductionStopped as e:
            logger.info('\tStopped')
            e.result = mapping
            raise
        except Exception as e:
            logger.info('\tErrored')
            raise ReductionError(str(e), result=mapping) from e


def apply_mapping(hdd_tree, mapping):
    def _apply_mapping(node):
        node = mapping.get(node, node)
        if hasattr(node, 'children'):
            for i, child in enumerate(node.children):
                node.children[i].replace_with(_apply_mapping(child))
        return node
    return _apply_mapping(hdd_tree)


def hoist(hdd_tree, config_nodes, *,
          reduce_class=None, reduce_config=None, tester_class, tester_config,
          id_prefix, cache, unparse_with_whitespace):
    """
    Try hoisting subtrees.

    :param hdd_tree: The root of the tree that the reduce will work with.
    :param config_nodes: Nodes from one level collected by the HDD algorithm.
    :param reduce_class: Unused, present for being compatible with 'prune'
        transformation.
    :param reduce_config: Dictionary containing the parameters of the
        reduce_class init function. Unused except for the 'stop' key that
        controls the limits of reduction.
    :param tester_class: Reference to a callable class that can decide about the
        interestingness of a test case.
    :param tester_config: Dictionary containing the parameters of the tester
        class init function.
    :param id_prefix: Tuple to prepend to config IDs during tests.
    :param cache: Cache to use.
    :param unparse_with_whitespace: Build test case by adding whitespace between
        nonadjacent tree nodes during unparsing.
    :return: The reduced tree and a boolean value that shows whether the tree
        has changed during hoisting.
    :raises ReductionException: If reduction could not run until completion. The
        ``result`` attribute of the exception contains the smallest, potentially
        non-minimal, but failing tree found during reduction.
    """

    if not config_nodes:
        return hdd_tree, False

    test_builder = HoistingTestBuilder(hdd_tree, with_whitespace=unparse_with_whitespace)
    if cache:
        cache.clear()

    test = tester_class(**tester_config)
    mapping_min = MappingMin(test, cache=cache, id_prefix=id_prefix, stop=reduce_config.get('stop', None), test_builder=test_builder)

    try:
        mapping = mapping_min(config_nodes)
        hdd_tree = apply_mapping(hdd_tree, mapping)
        return hdd_tree, bool(mapping)
    except ReductionException as e:
        e.result = apply_mapping(hdd_tree, e.result)
        raise
