# Copyright (c) 2016-2017 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import antlerinator
import codecs
import json
import logging
import picire
import pkgutil

from argparse import ArgumentParser
from os.path import abspath, basename, dirname, exists, isabs, join, relpath
from shutil import rmtree

from antlr4 import *
from .antlr4 import create_hdd_tree
from .coarse_hdd import coarse_hddmin, coarse_full_hddmin
from .hdd import hddmin

logger = logging.getLogger('picireny')
__version__ = pkgutil.get_data(__package__, 'VERSION').decode('ascii').strip()
antlr_default_path = antlerinator.antlr_jar_path


args_hdd_choices = {
    'full': hddmin,
    'coarse': coarse_hddmin,
    'coarse-full': coarse_full_hddmin,
}


def process_args(arg_parser, args):

    def load_format_config(data):
        # Interpret relative grammar paths compared to the directory of the config file.
        if 'files' in data:
            for i, fn in enumerate(data['files']):
                path = join(abspath(dirname(args.format)), fn)
                if not exists(path):
                    arg_parser.error('{path}, defined in the format config, doesn\'t exist.'.format(path=path))
                data['files'][i] = path
            data['islands'] = data.get('islands', {})
            data['replacements'] = data.get('replacements', {})
        return data

    args.hddmin = args_hdd_choices[args.hdd]

    if args.antlr:
        if args.antlr == antlr_default_path:
            antlerinator.install(lazy=True)

        args.antlr = abspath(relpath(args.antlr))
        if not exists(args.antlr):
            arg_parser.error('%s does not exist.' % args.antlr)

    args.input_format = dict()

    if args.format:
        if not exists(args.format):
            arg_parser.error('{path} does not exist.'.format(path=args.format))

        with open(args.format, 'r') as f:
            try:
                input_description = json.load(f, object_hook=load_format_config)
                args.input_format = input_description['grammars']
                if not args.start:
                    args.start = input_description.get('start', None)
            except json.JSONDecodeError as err:
                arg_parser.error('The content of {path} is not a valid JSON object: {err}'.format(path=args.format, err=err))

    if not args.start:
        arg_parser.error('No start has been defined either in config or as CLI argument.')

    if args.grammar or args.replacements:
        # Initialize the default grammar that doesn't need to be named.
        args.input_format[''] = args.input_format.get('', {'files': [], 'replacements': {}, 'islands': {}})

        if args.grammar:
            for i, g in enumerate(args.grammar):
                args.input_format['']['files'].append(abspath(relpath(g)))
                if not exists(args.input_format['']['files'][i]):
                    arg_parser.error('{path} does not exist.'.format(path=args.input_format['']['files'][i]))

        if args.replacements:
            if not exists(args.replacements):
                arg_parser.error('{path} does not exist.'.format(path=args.replacements))

            try:
                with open(args.replacements, 'r') as f:
                    args.input_format['']['replacements'] = json.load(f)
            except json.JSONDecodeError as err:
                arg_parser.error('The content of {path} is not a valid JSON object: {err}'.format(path=args.replacements, err=err))

    picire.cli.process_args(arg_parser, args)


def call(*,
         reduce_class, reduce_config,
         tester_class, tester_config,
         input, src, encoding, out,
         hddmin,
         antlr, input_format, start, lang='python',
         hdd_star=True, squeeze_tree=True, skip_unremovable_tokens=True,
         flatten_recursion=False,
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
    :param hddmin: Function implementing a HDD minimization algorithm.
    :param antlr: Path to the ANTLR4 tool (Java jar binary).
    :param input_format: Dictionary describing the input format.
    :param start: Name of the start rule in [grammarname:]rulename format.
    :param lang: The target language of the parser.
    :param hdd_star: Boolean to enable the HDD star algorithm.
    :param squeeze_tree: Boolean to enable the tree squeezing optimization.
    :param skip_unremovable_tokens: Boolean to enable hiding unremovable tokens from ddmin.
    :param flatten_recursion: Boolean to enable flattening left/right-recursive trees.
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

    hdd_tree = create_hdd_tree(InputStream(src.decode(encoding)), input_format, start, antlr, grammar_workdir,
                               lang=lang)

    if flatten_recursion:
        hdd_tree.flatten_recursion()

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
                       cache=cache_class() if cache_class else None))
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
    arg_parser.add_argument('--hdd', metavar='NAME', choices=args_hdd_choices.keys(), default='full',
                            help='HDD variant to run (%(choices)s; default: %(default)s)')
    arg_parser.add_argument('-s', '--start', metavar='NAME',
                            help='name of the start rule in [grammarname:]rulename format (default for '
                                 'the optional grammarname is the empty string)')
    arg_parser.add_argument('-g', '--grammar', metavar='FILE', nargs='+',
                            help='grammar file(s) describing the input format (these grammars will be '
                                 'associated with the empty grammar name, see `--start`)')
    arg_parser.add_argument('-r', '--replacements', metavar='FILE',
                            help='JSON file defining the default replacements for lexer and parser '
                                 'rules of the grammar with the empty name (usually defined via `--grammar`)')
    arg_parser.add_argument('--antlr', metavar='FILE', default=antlr_default_path,
                            help='path where the antlr jar file is installed (default: %(default)s)')
    arg_parser.add_argument('--format', metavar='FILE',
                            help='JSON file describing a (possibly complex) input format')
    arg_parser.add_argument('--parser', metavar='LANG', default='python', choices=['python', 'java'],
                            help='language of the generated parsers (%(choices)s; default: %(default)s) '
                                 '(using Java might gain performance, but needs JDK)')
    arg_parser.add_argument('--no-hdd-star', dest='hdd_star', default=True, action='store_false',
                            help='run the hddmin algorithm only once')
    arg_parser.add_argument('--no-squeeze-tree', dest='squeeze_tree', default=True, action='store_false',
                            help='don\'t squeeze rule chains in tree representation')
    arg_parser.add_argument('--no-skip-unremovable-tokens', dest='skip_unremovable_tokens', default=True, action='store_false',
                            help='don\'t hide unremovable tokens from the ddmin algorithm')
    arg_parser.add_argument('--flatten-recursion', default=False, action='store_true',
                            help='flatten recurring blocks of left/right-recursive rules')
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
         hddmin=args.hddmin,
         antlr=args.antlr,
         input_format=args.input_format,
         start=args.start,
         lang=args.parser,
         hdd_star=args.hdd_star,
         squeeze_tree=args.squeeze_tree,
         skip_unremovable_tokens=args.skip_unremovable_tokens,
         flatten_recursion=args.flatten_recursion,
         cache_class=args.cache,
         cleanup=args.cleanup)
