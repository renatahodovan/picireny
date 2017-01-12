# Copyright (c) 2016-2017 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import codecs
import json
import logging
import picire
import pkgutil

from argparse import ArgumentParser
from os.path import abspath, basename, exists, expanduser, join, relpath
from shutil import rmtree

from antlr4 import *
from .antlr4 import create_hdd_tree, IslandDescriptor
from .hdd import hddmin

logger = logging.getLogger('picireny')
__version__ = pkgutil.get_data(__package__, 'VERSION').decode('ascii').strip()
antlr_default_path = join(expanduser('~'), '.picireny', 'antlr4.jar')


def process_args(arg_parser, args):
    if args.antlr:
        args.antlr = abspath(relpath(args.antlr))
        if not exists(args.antlr):
            arg_parser.error('%s does not exist.' % args.antlr)

    for i, g in enumerate(args.grammar):
        args.grammar[i] = abspath(relpath(g))
        if not exists(args.grammar[i]):
            arg_parser.error('%s does not exist.' % args.grammar[i])

    if args.replacements:
        if not exists(args.replacements):
            arg_parser.error('%s does not exist.' % args.replacements)
        else:
            try:
                with open(args.replacements, 'r') as f:
                    args.replacements = json.load(f)
            except json.JSONDecodeError as err:
                arg_parser.error('The content of %s is not a valid JSON object: %s' % err)
    else:
        args.replacements = {}

    if args.islands:
        if not exists(args.islands):
            arg_parser.error('%s does not exist.' % args.islands)
        with open(args.islands, 'r') as f:
            args.islands = json.load(f, object_hook=IslandDescriptor.json_load_object_hook)

    picire.cli.process_args(arg_parser, args)


def call(*,
         reduce_class, reduce_config,
         tester_class, tester_config,
         input, src, encoding, out,
         antlr, grammar, start_rule, replacements=None, islands=None, lang='python',
         hdd_star=True, squeeze_tree=True, skip_unremovable_tokens=True,
         cache_class=None, cleanup=True):
    """
    Execute picireny as if invoked from command line, however, control its
    behaviour not via command line arguments but function parameters.

    :param reduce_class: Reference to the reducer class.
    :param reduce_config: Dictionary containing information to initialize the reduce_class.
    :param tester_class: Reference to a runnable class that can decide about the interestingness of a test case.
    :param tester_config: Dictionary containing information to initialize the tester_class.
    :param input: Path to the test case to reduce (only used to determine the name of the output file).
    :param src: Contents of the test case to reduce.
    :param encoding: Encoding of the input test case.
    :param out: Path to the output directory.
    :param antlr: Path to the ANTLR4 tool (Java jar binary).
    :param grammar: Path to the grammar(s) that can parse the top-level language.
    :param start_rule: Name of the start rule of the top-level grammar.
    :param replacements: Dictionary containing the minimal replacement of every lexer and parser rules.
    :param islands: Path to the Python3 file describing how to process island grammars.
    :param lang: The target language of the parser.
    :param hdd_star: Boolean to enable the HDD star algorithm.
    :param squeeze_tree: Boolean to enable the tree squeezing optimization.
    :param skip_unremovable_tokens: Boolean to enable hiding unremovable tokens from ddmin.
    :param cache_class: Reference to the cache class to use.
    :param cleanup: Binary flag denoting whether removing auxiliary files at the end is enabled (default: True).
    :return: The path to the minimal test case.
    """

    # Get the parameters in a dictionary so that they can be pretty-printed
    # (minus src, as that parameter can be arbitrarily large)
    args = locals().copy()
    del args['src']
    logger.info('Reduce session starts for %s\n%s',
                input, ''.join(['\t%s: %s\n' % (k, v) for k, v in sorted(args.items())]))

    grammar_workdir = join(out, 'grammar')
    tests_workdir = join(out, 'tests')

    hdd_tree = create_hdd_tree(InputStream(src.decode(encoding)), grammar, start_rule, antlr, grammar_workdir,
                               replacements=replacements, island_desc=islands, lang=lang)

    if squeeze_tree:
        hdd_tree = hdd_tree.squeeze_tree()

    if skip_unremovable_tokens:
        hdd_tree.skip_unremovable_tokens()

    # Start reduce and save result to a file named the same like the original.
    out_file = join(out, basename(input))
    with codecs.open(out_file, 'w', encoding=encoding, errors='ignore') as f:
        f.write(hddmin(hdd_tree,
                       reduce_class,
                       reduce_config,
                       tester_class,
                       tester_config,
                       basename(input),
                       tests_workdir,
                       hdd_star=hdd_star,
                       cache_class=cache_class))
    logger.info('Result is saved to %s.', out_file)

    if cleanup:
        rmtree(grammar_workdir)
        rmtree(tests_workdir)

    return out_file


def execute():
    """
    The main entry point of picireny.
    """

    arg_parser = ArgumentParser(description='CLI for the Picireny Hierarchical Delta Debugging Framework',
                                parents=[picire.cli.create_parser()], add_help=False)

    # Grammar specific settings.
    arg_parser.add_argument('-s', '--start-rule', metavar='NAME', required=True,
                            help='start rule of the grammar')
    arg_parser.add_argument('-g', '--grammar', metavar='FILE', nargs='+', required=True,
                            help='grammar file(s) describing the input format')
    arg_parser.add_argument('-r', '--replacements', metavar='FILE',
                            help='JSON file defining the default replacements for lexer or parser rules')
    arg_parser.add_argument('--antlr', metavar='FILE', default=antlr_default_path,
                            help='path where the antlr jar file is installed (default: %(default)s)')
    arg_parser.add_argument('--islands', metavar='FILE',
                            help='JSON file describing how to process island languages')
    arg_parser.add_argument('--parser', metavar='LANG', default='python', choices=['python', 'java'],
                            help='language of the generated parsers (%(choices)s; default: %(default)s) '
                                 '(using Java might gain performance, but needs JDK)')
    arg_parser.add_argument('--no-hdd-star', dest='hdd_star', default=True, action='store_false',
                            help='run the hddmin algorithm only once')
    arg_parser.add_argument('--no-squeeze-tree', dest='squeeze_tree', default=True, action='store_false',
                            help='don\'t squeeze rule chains in tree representation')
    arg_parser.add_argument('--no-skip-unremovable-tokens', dest='skip_unremovable_tokens', default=True, action='store_false',
                            help='don\'t hide unremovable tokens from the ddmin algorithm')
    arg_parser.add_argument('--version', action='version', version='%(prog)s {version}'.format(version=__version__))

    args = arg_parser.parse_args()
    process_args(arg_parser, args)

    logging.basicConfig(format='%(message)s')
    logger.setLevel(args.log_level)
    logging.getLogger('picire').setLevel(logger.level)

    call(reduce_class=args.reduce_class,
         reduce_config=args.reduce_config,
         tester_class=args.tester_class,
         tester_config=args.tester_config,
         input=args.input,
         src=args.src,
         encoding=args.encoding,
         out=args.out,
         antlr=args.antlr,
         grammar=args.grammar,
         start_rule=args.start_rule,
         lang=args.parser,
         replacements=args.replacements,
         islands=args.islands,
         hdd_star=args.hdd_star,
         squeeze_tree=args.squeeze_tree,
         skip_unremovable_tokens=args.skip_unremovable_tokens,
         cache_class=args.cache,
         cleanup=args.cleanup)
