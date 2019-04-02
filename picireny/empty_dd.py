# Copyright (c) 2017-2019 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging

from picire import AbstractDD

logger = logging.getLogger(__name__)


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
        AbstractDD.__init__(self, test, None, cache=cache, id_prefix=id_prefix)

    def ddmin(self, config, n=2):
        """
        Return a 1-minimal failing subset of the initial configuration, and also
        test the empty configuration while doing so.

        Note: The initial configuration is expected to be of size 1, thus the
        1-minimal failing subset is always its trivial subset: either itself or
        the empty configuration.

        :param config: The initial configuration that will be reduced.
        :param n: The number of sets that the config is initially split to
            (unused, available for API compatibility with other DD variants).
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
