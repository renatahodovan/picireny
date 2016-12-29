# Copyright (c) 2007 Ghassan Misherghi.
# Copyright (c) 2016 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging

from os.path import join

from picire import *

logger = logging.getLogger(__name__)


def hddmin(hdd_tree, reduce_class, reduce_config, tester_class, tester_config, test_name, work_dir,
           *, hdd_star=True):
    """
    Run the main reduce algorithm.

    :param hdd_tree: The root of the tree that the reduce will work with (it's the output of create_hdd_tree).
    :param reduce_class: Reference to the reducer class (LightDD, ParallelDD or CombinedParallelDD from the
                         picire module).
    :param reduce_config: Dictionary containing the parameters of the reduce_class init function.
    :param tester_class: Reference to a callable class that can decide about the interestingness of a test case.
    :param tester_config: Dictionary containing the parameters of the tester class init function (except test_builder).
    :param test_name: Name of the test case file.
    :param work_dir: Directory to save temporary test files.
    :param hdd_star: Boolean to enable the HDD star algorithm.
    :return: The 1-minimal test case.
    """

    class Unparser(object):
        """Class defines how to build test case from an HDD tree."""

        def __init__(self, tree, level):
            """
            Initialize the unparser object.

            :param tree: Tree representing the current test case.
            :param level: The current level or granularity that the reducer work with.
            """
            self.tree = tree
            self.level = level

        def __call__(self, config):
            """
            :param config: List of tree units/deltas will be kept in the next test case.
            :return: The unparsed test case containing only the units defined in config.
            """
            self.tree.clear_remove()
            self.tree.set_remove(self.level, config)
            return self.tree.unparse()

    iter_cnt = 0
    while True:
        logger.info('Iteration #%d' % iter_cnt)
        hdd_tree.check()
        hdd_tree.set_levels()

        level = 0
        changed = False
        count = hdd_tree.tag(level)

        while count:
            logger.info('Checking level %d ...' % level)
            dd = reduce_class(tester_class(test_builder=Unparser(hdd_tree, level),
                                           test_pattern=join(work_dir, 'level_%d' % level, '%s', test_name),
                                           **tester_config),
                              **reduce_config)
            logger.info('Checking subsets: %s' % str(list(range(count))))
            c = dd.ddmin(list(range(count)))
            changed = changed or count > len(c)
            if global_structures.outcome_cache:
                global_structures.outcome_cache.clear()

            hdd_tree.commit_remove(level, c)
            hdd_tree.clear_remove()

            while True:
                level += 1
                count = hdd_tree.tag(level)
                if count != 1:
                    break

        if not hdd_star or not changed:
            break

        iter_cnt += 1

    return hdd_tree.unparse()
