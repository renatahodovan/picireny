# Copyright (c) 2021 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import sys

if sys.version_info.major == 2:
    from .py2 import ANTLRv4Lexer, ANTLRv4Parser
else:
    from .py3 import ANTLRv4Lexer, ANTLRv4Parser

del sys
