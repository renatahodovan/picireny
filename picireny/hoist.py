# Copyright (c) 2021 Renata Hodovan, Akos Kiss.
# Copyright (c) 2021 Daniel Vince.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import itertools
import logging

from picire import AbstractDD

logger = logging.getLogger(__name__)


class HoistingTestBuilder(object):

    def __init__(self, tree, with_whitespace=True):
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


class MappingMin(AbstractDD):

    def __init__(self, test, cache=None, id_prefix=()):
        """
        :param test: A callable tester object.
        :param cache: Cache object to use.
        :param id_prefix: Tuple to prepend to config IDs during tests.
        """

        AbstractDD.__init__(self, test=test, split=None, cache=cache, id_prefix=id_prefix)

    def ddmin(self, config):
        """
        Compute a mapping of the initial configuration to another (usually
        smaller) but still failing configuration.

        :param config: The initial configuration that will be reduced.
        :return: A mapping of initial configuration elements to new ones.
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

        for run in itertools.count():
            logger.info('Run #%d', run)
            logger.info('\tMapping size: %d', len(mapping))
            logger.debug('\tMapping: %r', {c.id: m.id for c, m in mapping.items()})

            for i, (c, m) in enumerate((c, m) for c in config for m in collect_hoistables(mapping.get(c, c))):
                new_mapping = mapping.copy()
                new_mapping[c] = m
                mapping_config = list(new_mapping.items())
                config_id = ('r%d' % run, 'm%d' % i)

                outcome = self._lookup_cache(mapping_config, config_id) or self._test_config(mapping_config, config_id)

                if outcome == self.FAIL:
                    mapping = new_mapping
                    logger.info('\tHoisted')
                    break
            else:
                break

        logger.info('\tDone')
        return mapping


def hoist(hdd_tree, config_nodes, tester_class, tester_config, test_pattern, id_prefix,
          cache, unparse_with_whitespace):
    """
    Try hoisting subtrees.

    :param hdd_tree: The root of the tree that the reduce will work with.
    :param config_nodes: Nodes from one level collected by the HDD algorithm.
    :param tester_class: Reference to a callable class that can decide about the
        interestingness of a test case.
    :param tester_config: Dictionary containing the parameters of the tester
        class init function (except test_builder).
    :param test_pattern: Directory to save temporary test files.
    :param id_prefix: Tuple to prepend to config IDs during tests.
    :param cache: Cache to use.
    :param unparse_with_whitespace: Build test case by adding whitespace between
        nonadjacent tree nodes during unparsing.
    :return: The reduced tree and a boolean value that shows whether the tree
        has changed during hoisting.
    """

    if not config_nodes:
        return hdd_tree, False

    test_builder = HoistingTestBuilder(hdd_tree, with_whitespace=unparse_with_whitespace)
    cache.set_test_builder(test_builder)

    test = tester_class(test_builder=test_builder, test_pattern=test_pattern, **tester_config)
    mapping_min = MappingMin(test, cache=cache, id_prefix=id_prefix)
    mapping = mapping_min.ddmin(config_nodes)

    def _apply_mapping(node):
        if node in mapping:
            node = mapping[node]
        if hasattr(node, 'children'):
            for i, child in enumerate(node.children):
                node.children[i].replace_with(_apply_mapping(child))
        return node
    hdd_tree = _apply_mapping(hdd_tree)

    if cache:
        cache.clear()

    return hdd_tree, bool(mapping)
