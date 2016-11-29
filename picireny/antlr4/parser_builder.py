# Copyright (c) 2016 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging
import sys

from os import listdir
from os.path import basename, commonprefix, split, splitext
from subprocess import Popen, PIPE, STDOUT

logger = logging.getLogger(__name__)
grammar_cache = {}


def build_grammars(grammars, out, antlr, lang='python'):
    """
    Build lexer and grammar from ANTLRv4 grammar files in Python3 target.

    :param grammars: Tuple of grammar files.
    :param out: Output directory.
    :param antlr: Path to the ANTLR4 tool (Java jar binary).
    :param lang: The target language of the parser.
    :return: List of references/names of the lexer, parser and listener classes of the target.
    """

    # Generate parser and lexer in the target language and return either with
    # python class ref or the name of java classes.
    global grammar_cache
    if lang not in grammar_cache:
        grammar_cache[lang] = {}
    if grammars in grammar_cache[lang]:
        logger.debug('{grammars} is already built with {lang} target.'.format(grammars=', '.join(grammars), lang=lang))
        return grammar_cache[lang][grammars]

    try:
        languages = {
            'python': {'antlr_arg': '-Dlanguage=Python3', 'ext': 'py', 'listener_format': 'Listener'},
            'java': {'antlr_arg': '', 'ext': 'java', 'listener_format': 'BaseListener'},
        }

        with Popen('java -jar {antlr} {lang} -o {out} {grammars}'.format(antlr=antlr,
                                                                         lang=languages[lang]['antlr_arg'],
                                                                         out=out,
                                                                         grammars=' '.join(grammars)),
                   stdout=PIPE, stderr=STDOUT, shell=True, cwd=out) as proc:
            output, exit_code = proc.stdout.read().decode(), proc.returncode
            if exit_code:
                logger.critical('Building grammars ({grammars}) failed: {error}'.format(grammars=', '.join(grammars), error=output))
                sys.exit(1)

        files = listdir(out)
        filename = basename(grammars[0])

        def file_endswith(end_pattern):
            return splitext(split(list(
                filter(lambda x: len(commonprefix([filename, x])) > 0 and x.endswith(end_pattern), files))[0])[1])[0]

        # Extract the name of lexer and parser from their path.
        lexer = file_endswith('Lexer.{ext}'.format(ext=languages[lang]['ext']))
        parser = file_endswith('Parser.{ext}'.format(ext=languages[lang]['ext']))
        # The name of the generated listeners differs if Python or other language target is used.
        listener = file_endswith('{listener_format}.{ext}'.format(listener_format=languages[lang]['listener_format'], ext=languages[lang]['ext']))

        if lang == 'python':
            grammar_cache[lang][grammars] = [getattr(__import__(x, globals(), locals(), [x], 0), x) for x in [lexer, parser, listener]]
        else:
            grammar_cache[lang][grammars] = [lexer, parser, listener]

        return grammar_cache[lang][grammars]
    except Exception as e:
        logger.critical('Exception while loading parser modules: %s' % e)
        sys.exit(1)
