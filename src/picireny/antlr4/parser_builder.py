# Copyright (c) 2016-2022 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging

from os import listdir
from os.path import basename, commonprefix, split, splitext
from subprocess import CalledProcessError, PIPE, run, STDOUT

logger = logging.getLogger(__name__)
grammar_cache = {}


def build_grammars(grammars, out, antlr, lang='python'):
    """
    Build lexer and grammar from ANTLRv4 grammar files in Python target.

    :param grammars: Tuple of grammar files.
    :param out: Output directory.
    :param antlr: Path to the ANTLR4 tool (Java jar binary).
    :param lang: The target language of the parser.
    :return: List of references/names of the lexer, parser and listener classes
        of the target.
    """

    # Generate parser and lexer in the target language and return either with
    # python class ref or the name of java classes.
    if lang not in grammar_cache:
        grammar_cache[lang] = {}
    if grammars in grammar_cache[lang]:
        logger.debug('%r is already built with %s target.', grammars, lang)
        return grammar_cache[lang][grammars]

    try:
        languages = {
            'python': {'antlr_arg': '-Dlanguage=Python3', 'ext': 'py', 'listener_format': 'Listener'},
            'java': {'antlr_arg': '-Dlanguage=Java', 'ext': 'java', 'listener_format': 'BaseListener'},
        }

        try:
            run(('java', '-jar', antlr, languages[lang]['antlr_arg'], '-o', out) + grammars,
                stdout=PIPE, stderr=STDOUT, cwd=out, check=True)
        except CalledProcessError as e:
            logger.error('Building grammars %r failed!\n%s\n', grammars, e.output)
            raise

        files = listdir(out)
        filename = basename(grammars[0])

        def file_endswith(end_pattern):
            f = next(f for f in files if len(commonprefix([filename, f])) > 0 and f.endswith(end_pattern))
            _, f = split(f)
            f, _ = splitext(f)
            return f

        # Extract the name of lexer and parser from their path.
        lexer = file_endswith(f'Lexer.{languages[lang]["ext"]}')
        parser = file_endswith(f'Parser.{languages[lang]["ext"]}')
        # The name of the generated listeners differs if Python or other language target is used.
        listener = file_endswith(f'{languages[lang]["listener_format"]}.{languages[lang]["ext"]}')

        if lang == 'python':
            grammar_cache[lang][grammars] = [getattr(__import__(x, globals(), locals(), [x], 0), x) for x in [lexer, parser, listener]]
        else:
            grammar_cache[lang][grammars] = [lexer, parser, listener]

        return grammar_cache[lang][grammars]
    except Exception as e:
        logger.error('Exception while loading parser modules', exc_info=e)
        raise
