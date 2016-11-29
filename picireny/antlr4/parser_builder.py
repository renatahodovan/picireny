# Copyright (c) 2016 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.md or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging
import sys

from os import listdir
from os.path import basename, commonprefix, split, splitext
from subprocess import Popen, PIPE, STDOUT

logger = logging.getLogger(__name__)
grammar_cache = {}


def build_grammars(grammars, out, antlr):
    """
    Build lexer and grammar from ANTLRv4 grammar files in Python3 target.

    :param grammars: List of grammar files.
    :param out: Output directory.
    :param antlr: Path to the ANTLR4 tool (Java jar binary).
    :return: Tuple of references to the lexer, parser and listener classes of the target.
    """
    grammar_list = ' '.join(grammars)
    global grammar_cache
    if grammar_list in grammar_cache:
        logger.debug('%s is already built.' % str(grammar_list))
        return grammar_cache[grammar_list]

    try:
        with Popen('java -jar %s -Dlanguage=Python3 -o %s %s' % (antlr, out, grammar_list),
                   stdout=PIPE, stderr=STDOUT, shell=True, cwd=out) as proc:
            output, exit_code = proc.stdout.read().decode(), proc.returncode
            if exit_code:
                logger.critical('Building grammars (%s) failed: %s' % (grammar_list, output))
                sys.exit(1)

            files = listdir(out)
            filename = basename(grammars[0])

            def file_endswith(end_pattern):
                return splitext(split(list(
                    filter(lambda x: len(commonprefix([filename, x])) > 0 and x.endswith(end_pattern), files))[0])[1])[0]

            # Extract the name of lexer and parser from their path.
            lexer = file_endswith('Lexer.py')
            parser = file_endswith('Parser.py')
            listener = file_endswith('Listener.py')

            grammar_cache[grammar_list] = [getattr(__import__(x, globals(), locals(), [x], 0), x) for x in
                                           [lexer, parser, listener]]
            return grammar_cache[grammar_list]
    except Exception as e:
        logger.critical('Exception while loading parser modules: %s' % e)
        sys.exit(1)
