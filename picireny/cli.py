# Copyright (c) 2016-2020 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from __future__ import absolute_import

import codecs
import json
import logging
import sys

from argparse import ArgumentParser
from os import makedirs
from os.path import abspath, basename, dirname, exists, isdir, join, realpath
from shutil import rmtree

import antlerinator
import picire
import pkg_resources

from antlr4 import InputStream

from . import hdd, hddr, info, transform

logger = logging.getLogger('picireny')
__version__ = pkg_resources.get_distribution(__package__).version
antlr_default_path = antlerinator.antlr_jar_path


args_hdd_choices = {
    'full': hdd.hddmin,
    'coarse': hdd.coarse_hddmin,
    'coarse-full': hdd.coarse_full_hddmin,
    'hddr': hddr.hddrmin,
}


def process_antlr4_path(antlr=None):
    antlr = antlr or antlr_default_path
    if antlr == antlr_default_path:
        antlerinator.install(lazy=True)

    if not exists(antlr):
        logger.error('%s does not exist.', antlr)
        return None

    return realpath(antlr)


def process_antlr4_format(format=None, grammar=None, start=None, replacements=None):
    def load_format_config(data):
        # Interpret relative grammar paths compared to the directory of the config file.
        if 'files' in data:
            for i, fn in enumerate(data['files']):
                path = join(abspath(dirname(format)), fn)
                if not exists(path):
                    logger.error('%s, defined in the format config, does not exist.', path)
                    return None, None
                data['files'][i] = path
            data['islands'] = data.get('islands', {})
            data['replacements'] = data.get('replacements', {})
        return data

    input_format = dict()

    if format:
        if not exists(format):
            logger.error('%s does not exist.', format)
            return None, None

        with open(format, 'r') as f:
            try:
                input_description = json.load(f, object_hook=load_format_config)
                input_format = input_description['grammars']
                if not start:
                    start = input_description.get('start', None)
            except ValueError as err:
                logger.error('The content of %s is not a valid JSON object.', format, exc_info=err)
                return None, None

    if not start:
        logger.error('No start has been defined.')
        return None, None

    if grammar or replacements:
        # Initialize the default grammar that doesn't need to be named.
        input_format[''] = input_format.get('', {'files': [], 'replacements': {}, 'islands': {}})

        if grammar:
            for i, g in enumerate(grammar):
                input_format['']['files'].append(realpath(g))
                if not exists(input_format['']['files'][i]):
                    logger.error('%s does not exist.', input_format['']['files'][i])
                    return None, None

        if replacements:
            if not exists(replacements):
                logger.error('%s does not exist.', replacements)
                return None, None

            try:
                with open(replacements, 'r') as f:
                    input_format['']['replacements'] = json.load(f)
            except ValueError as err:
                logger.error('The content of %s is not a valid JSON object.', replacements, exc_info=err)
                return None, None

    return input_format, start


def process_antlr4_args(arg_parser, args):
    args.antlr = process_antlr4_path(args.antlr)
    if args.antlr is None:
        arg_parser.error('Invalid ANTLR definition.')

    args.input_format, args.start = process_antlr4_format(format=args.format, grammar=args.grammar, start=args.start,
                                                          replacements=args.replacements)
    if args.input_format is None or args.start is None:
        arg_parser.error('Invalid input format definition.')


def process_srcml_args(arg_parser, args):
    if not args.srcml_language:
        arg_parser.error('The following argument is required for srcML: --srcml:language')


def process_args(arg_parser, args):
    args.hddmin = args_hdd_choices[args.hdd]

    if args.builder == 'antlr4':
        process_antlr4_args(arg_parser, args)
    elif args.builder == 'srcml':
        process_srcml_args(arg_parser, args)

    picire.cli.process_args(arg_parser, args)


def log_args(title, args):
    def _log_args(args):
        if not args:
            return repr(args)
        if isinstance(args, dict):
            log = []
            for k, v in sorted(args.items()):
                k_log = _log_args(k)
                v_log = _log_args(v)
                if isinstance(v_log, list):
                    log += ['%s:' % k_log]
                    for line in v_log:
                        log += ['\t' + line]
                else:
                    log += ['%s: %s' % (k_log, v_log)]
            return log if len(log) > 1 else log[0]
        if isinstance(args, list):
            return ', '.join(_log_args(v) for v in args)
        if hasattr(args, '__name__'):
            return '.'.join(([args.__module__] if hasattr(args, '__module__') else []) + [args.__name__])
        return args
    logger.info('%s\n\t%s\n', title, '\n\t'.join(_log_args(args)))


def log_tree(title, hdd_tree):
    logger.debug('%s\n\theight: %s\n\tshape: %s\n\tnodes: %s\n',
                 title,
                 info.height(hdd_tree),
                 ', '.join('%s' % cnt for cnt in info.shape(hdd_tree)),
                 ', '.join('%d %s' % (cnt, ty) for ty, cnt in sorted(info.count(hdd_tree).items())))


def build_with_antlr4(input, src, encoding, out,
                      input_format, start,
                      antlr, lang='python',
                      build_hidden_tokens=False,
                      cleanup=True):
    """
    Execute ANTLRv4-based tree building part of picireny as if invoked from
    command line, however, control its behaviour not via command line arguments
    but function parameters.

    :param input: Path to the test case to reduce (only used for logging).
    :param src: Contents of the test case to reduce.
    :param encoding: Encoding of the input test case.
    :param out: Path to the output directory.
    :param input_format: Dictionary describing the input format.
    :param start: Name of the start rule in [grammarname:]rulename format.
    :param antlr: Path to the ANTLR4 tool (Java jar binary).
    :param lang: The target language of the parser.
    :param build_hidden_tokens: Build hidden tokens of the input format into the
        HDD tree.
    :param cleanup: Binary flag denoting whether removing auxiliary files at the
        end is enabled.
    :return: The built HDD tree.
    """
    # Get the parameters in a dictionary so that they can be pretty-printed
    args = locals().copy()
    del args['src']
    log_args('Building tree with ANTLRv4 for %s' % input, args)

    grammar_workdir = join(out, 'grammar')
    if not isdir(grammar_workdir):
        makedirs(grammar_workdir)

    from .antlr4 import create_hdd_tree
    hdd_tree = create_hdd_tree(InputStream(src.decode(encoding)), input_format, start, antlr, grammar_workdir,
                               hidden_tokens=build_hidden_tokens, lang=lang)

    if cleanup:
        rmtree(grammar_workdir)

    return hdd_tree


def build_with_srcml(input, src, language):
    """
    Execute srcML-based tree building part of picireny as if invoked from
    command line, however, control its behaviour not via command line arguments
    but function parameters.

    :param input: Path to the test case to reduce (only used for logging).
    :param src: Contents of the test case to reduce.
    :param language: Language of the input source (C, C++, C#, or Java).
    :return: The built HDD tree.
    """
    # Get the parameters in a dictionary so that they can be pretty-printed
    args = locals().copy()
    del args['src']
    log_args('Building tree with srcML for %s' % input, args)

    from .srcml import create_hdd_tree
    return create_hdd_tree(src, language)


def reduce(hdd_tree,
           reduce_class, reduce_config,
           tester_class, tester_config,
           input, encoding, out, hddmin, hdd_star=True,
           flatten_recursion=False, squeeze_tree=True,
           skip_unremovable=True, skip_whitespace=False,
           unparse_with_whitespace=True, granularity=2,
           cache_class=None, cleanup=True):
    """
    Execute tree reduction part of picireny as if invoked from command line,
    however, control its behaviour not via command line arguments but function
    parameters.

    :param hdd_tree: HDD tree to reduce.
    :param reduce_class: Reference to the reducer class.
    :param reduce_config: Dictionary containing information to initialize the
        reduce_class.
    :param tester_class: Reference to a runnable class that can decide about the
        interestingness of a test case.
    :param tester_config: Dictionary containing information to initialize the
        tester_class.
    :param input: Path to the test case to reduce (only used to determine the
        name of the output file).
    :param encoding: Encoding of the input test case.
    :param out: Path to the output directory.
    :param hddmin: Function implementing a HDD minimization algorithm.
    :param hdd_star: Boolean to enable the HDD star algorithm.
    :param flatten_recursion: Boolean to enable flattening left/right-recursive
        trees.
    :param squeeze_tree: Boolean to enable the tree squeezing optimization.
    :param skip_unremovable: Boolean to enable hiding unremovable nodes from
        ddmin.
    :param skip_whitespace: Boolean to enable hiding whitespace-only tokens from
        ddmin.
    :param unparse_with_whitespace: Unparse by adding whitespace between
        nonadjacent nodes.
    :param granularity: Initial granularity.
    :param cache_class: Reference to the cache class to use.
    :param cleanup: Binary flag denoting whether removing auxiliary files at the
        end is enabled.
    :return: The path to the minimal test case.
    """
    # Get the parameters in a dictionary so that they can be pretty-printed
    args = locals().copy()
    del args['hdd_tree']
    log_args('Reduce session starts for %s' % input, args)

    log_tree('Initial tree', hdd_tree)

    # Perform tree transformations.
    if flatten_recursion:
        hdd_tree = transform.flatten_recursion(hdd_tree)
        log_tree('Tree after recursion flattening', hdd_tree)

    if squeeze_tree:
        hdd_tree = transform.squeeze_tree(hdd_tree)
        log_tree('Tree after squeezing', hdd_tree)

    if skip_unremovable:
        hdd_tree = transform.skip_unremovable(hdd_tree, unparse_with_whitespace=unparse_with_whitespace)
        log_tree('Tree after skipping unremovable nodes', hdd_tree)

    if skip_whitespace:
        hdd_tree = transform.skip_whitespace(hdd_tree)
        log_tree('Tree after skipping whitespace tokens', hdd_tree)

    # Start reduce and save result to a file named the same like the original.
    tests_workdir = join(out, 'tests')
    if not isdir(tests_workdir):
        makedirs(tests_workdir)
    out_src = hddmin(hdd_tree,
                     reduce_class,
                     reduce_config,
                     tester_class,
                     tester_config,
                     basename(input),
                     tests_workdir,
                     hdd_star=hdd_star,
                     cache=cache_class() if cache_class else None,
                     unparse_with_whitespace=unparse_with_whitespace,
                     granularity=granularity)
    out_file = join(out, basename(input))
    with codecs.open(out_file, 'w', encoding=encoding, errors='ignore') as f:
        f.write(out_src)
    logger.info('Result is saved to %s.', out_file)

    if cleanup:
        rmtree(tests_workdir)

    return out_file


def execute():
    """
    The main entry point of picireny.
    """

    arg_parser = ArgumentParser(description='CLI for the Picireny Hierarchical Delta Debugging Framework',
                                parents=[picire.cli.create_parser()], add_help=False)

    # General HDD settings.
    arg_parser.add_argument('--builder', metavar='NAME', choices=['antlr4', 'srcml'], default='antlr4',
                            help='tool to build tree representation from input (%(choices)s; default: %(default)s)')
    arg_parser.add_argument('--hdd', metavar='NAME', choices=args_hdd_choices.keys(), default='full',
                            help='HDD variant to run (%(choices)s; default: %(default)s)')
    arg_parser.add_argument('--no-hdd-star', dest='hdd_star', default=True, action='store_false',
                            help='run the hddmin algorithm only once')
    arg_parser.add_argument('--flatten-recursion', default=False, action='store_true',
                            help='flatten recurring blocks of left/right-recursive rules')
    arg_parser.add_argument('--no-squeeze-tree', dest='squeeze_tree', default=True, action='store_false',
                            help='don\'t squeeze rule chains in tree representation')
    arg_parser.add_argument('--no-skip-unremovable', dest='skip_unremovable', default=True, action='store_false',
                            help='don\'t hide unremovable nodes from the ddmin algorithm')
    arg_parser.add_argument('--skip-whitespace', dest='skip_whitespace', default=False, action='store_true',
                            help='hide whitespace tokens from the ddmin algorithm')
    arg_parser.add_argument('--sys-recursion-limit', metavar='NUM', type=int, default=sys.getrecursionlimit(),
                            help='override maximum depth of the Python interpreter stack (may be needed for `--parser=java`; default: %(default)d)')
    arg_parser.add_argument('--version', action='version', version='%(prog)s {version}'.format(version=__version__))

    # ANTLRv4-specific settings.
    antlr4_grp = arg_parser.add_argument_group('ANTLRv4-specific arguments')
    antlr4_grp.add_argument('-s', '--start', '--antlr4:start', metavar='NAME',
                            help='name of the start rule in [grammarname:]rulename format (default for '
                                 'the optional grammarname is the empty string)')
    antlr4_grp.add_argument('-g', '--grammar', '--antlr4:grammar', metavar='FILE', nargs='+',
                            help='grammar file(s) describing the input format (these grammars will be '
                                 'associated with the empty grammar name, see `--start`)')
    antlr4_grp.add_argument('-r', '--replacements', '--antlr4:replacements', metavar='FILE',
                            help='JSON file defining the default replacements for lexer and parser '
                                 'rules of the grammar with the empty name (usually defined via `--grammar`)')
    antlr4_grp.add_argument('--format', '--antlr4:format', metavar='FILE',
                            help='JSON file describing a (possibly complex) input format')
    antlr4_grp.add_argument('--build-hidden-tokens', '--antlr4:build-hidden-tokens', default=False, action='store_true',
                            help='build hidden tokens of the grammar(s) into the HDD tree')
    antlr4_grp.add_argument('--antlr', '--antlr4:antlr', metavar='FILE', default=antlr_default_path,
                            help='path where the antlr jar file is installed (default: %(default)s)')
    antlr4_grp.add_argument('--parser', '--antlr4:parser', metavar='LANG', default='python', choices=['python', 'java'],
                            help='language of the generated parsers (%(choices)s; default: %(default)s) '
                                 '(using Java might gain performance, but needs JDK)')

    # srcML-specific settings.
    srcml_grp = arg_parser.add_argument_group('srcML-specific arguments')
    srcml_grp.add_argument('--srcml:language', dest='srcml_language', metavar='LANG', choices=['C', 'C++', 'C#', 'Java'],
                           help='language of the input (%(choices)s; default: %(default)s)')

    args = arg_parser.parse_args()
    process_args(arg_parser, args)

    logging.basicConfig(format='%(message)s')
    logger.setLevel(args.log_level)
    logging.getLogger('picire').setLevel(logger.level)

    sys.setrecursionlimit(args.sys_recursion_limit)

    if args.builder == 'antlr4':
        hdd_tree = build_with_antlr4(input=args.input, src=args.src, encoding=args.encoding, out=args.out,
                                     input_format=args.input_format, start=args.start,
                                     antlr=args.antlr, lang=args.parser,
                                     build_hidden_tokens=args.build_hidden_tokens,
                                     cleanup=args.cleanup)
        unparse_with_whitespace = not args.build_hidden_tokens
    elif args.builder == 'srcml':
        hdd_tree = build_with_srcml(input=args.input, src=args.src, language=args.srcml_language)
        unparse_with_whitespace = False

    reduce(hdd_tree=hdd_tree,
           reduce_class=args.reduce_class, reduce_config=args.reduce_config,
           tester_class=args.tester_class, tester_config=args.tester_config,
           input=args.input, encoding=args.encoding, out=args.out,
           hddmin=args.hddmin, hdd_star=args.hdd_star,
           flatten_recursion=args.flatten_recursion, squeeze_tree=args.squeeze_tree,
           skip_unremovable=args.skip_unremovable, skip_whitespace=args.skip_whitespace,
           unparse_with_whitespace=unparse_with_whitespace, granularity=args.granularity,
           cache_class=args.cache, cleanup=args.cleanup)
