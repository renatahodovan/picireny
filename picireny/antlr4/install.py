# Copyright (c) 2016 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import json
import pkgutil
import urllib.request

from argparse import ArgumentParser
from os import makedirs
from os.path import dirname, exists, join

from ..cli import __version__, antlr_default_path


def execute():
    """
    Entry point of the install helper tool to ease the download of the right
    version of the ANTLR v4 tool jar.
    """

    arg_parser = ArgumentParser(description='Install helper tool to download the right version of the ANTLR v4 tool jar.')

    arg_parser.add_argument('--version', action='version', version='%(prog)s {version}'.format(version=__version__))

    mode_group = arg_parser.add_mutually_exclusive_group()
    mode_group.add_argument('-f', '--force', action='store_true', default=False,
                            help='force download even if local antlr4.jar already exists')
    mode_group.add_argument('-l', '--lazy', action='store_true', default=False,
                            help='don\'t report an error if local antlr4.jar already exists and don\'t try to download it either')

    args = arg_parser.parse_args()

    tool_path = antlr_default_path
    local_dir = dirname(tool_path)

    if exists(tool_path):
        if args.lazy:
            arg_parser.exit()
        if not args.force:
            arg_parser.error('Local antlr4.jar already exists: %s' % tool_path)

    tool_url = json.loads(pkgutil.get_data(__package__, join('resources', 'dependencies.json')).decode('ascii'))['tool_url']
    with urllib.request.urlopen(tool_url) as response:
        tool_jar = response.read()

    makedirs(local_dir, exist_ok=True)

    with open(tool_path, mode='wb') as tool_file:
        tool_file.write(tool_jar)
