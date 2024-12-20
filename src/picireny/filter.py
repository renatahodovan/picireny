# Copyright (c) 2021 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.


def coarse_filter(node):
    """
    Config filter to keep nodes with empty replacements only, which is the core
    of the coarse hierarchical delta debugging reduce algorithm.
    """
    return node.replace == ''
