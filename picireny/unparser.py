# Copyright (c) 2017-2019 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.


class Unparser(object):
    """
    Class defines how to build test case from an HDD tree.
    """

    def __init__(self, tree, ids, with_whitespace=True):
        """
        Initialize the unparser object.

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
        self.tree.set_state(self.ids, set(config))
        return self.tree.unparse(with_whitespace=self.with_whitespace)
