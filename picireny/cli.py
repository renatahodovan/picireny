# Copyright (c) 2016-2021 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import json

from argparse import ArgumentParser
from os.path import abspath, dirname, exists, join, realpath
from shutil import rmtree

try:
    from importlib import metadata
except ImportError:
    import importlib_metadata as metadata

import antlerinator
import inators
import picire

from inators import log as logging

from . import filter, hdd, hddr, hoist, info, prune, transform

logger = logging.getLogger('picireny')
__version__ = metadata.version(__package__)


args_hdd_choices = {
    'hdd': hdd.hddmin,
    'hddr': hddr.hddrmin,
}


args_phase_choices = {
    'prune': {'transformations': [prune.prune]},
    'coarse-prune': {'transformations': [prune.prune], 'config_filter': filter.coarse_filter},
    'hoist': {'transformations': [hoist.hoist]},
    'prune+hoist': {'transformations': [prune.prune, hoist.hoist]},
    'coarse-prune+hoist': {'transformations': [prune.prune, hoist.hoist], 'config_filter': filter.coarse_filter}
}


def process_antlr4_args(args):
    antlerinator.process_antlr_argument(args)
    args.antlr = realpath(args.antlr)

    def load_format_config(data):
        # Interpret relative grammar paths compared to the directory of the config file.
        if 'files' in data:
            for i, fn in enumerate(data['files']):
                path = join(abspath(dirname(args.format)), fn)
                if not exists(path):
                    raise ValueError('Invalid input format definition: %s, defined in the format config, does not exist.' % path)
                data['files'][i] = path
            data['islands'] = data.get('islands', {})
            data['replacements'] = data.get('replacements', {})
        return data

    args.input_format = {}

    if args.format:
        if not exists(args.format):
            raise ValueError('Invalid input format definition: %s does not exist.' % args.format)

        with open(args.format, 'r') as f:
            try:
                input_description = json.load(f, object_hook=load_format_config)
                args.input_format = input_description['grammars']
                if not args.start:
                    args.start = input_description.get('start', None)
            except ValueError as e:
                raise ValueError('Invalid input format definition: The content of %s is not a valid JSON object.' % args.format) from e

    if not args.start:
        raise ValueError('Invalid input format definition: No start has been defined.')

    if args.grammar or args.replacements:
        # Initialize the default grammar that doesn't need to be named.
        if '' not in args.input_format:
            args.input_format[''] = {'files': [], 'replacements': {}, 'islands': {}}

        if args.grammar:
            for i, g in enumerate(args.grammar):
                args.input_format['']['files'].append(realpath(g))
                if not exists(args.input_format['']['files'][i]):
                    raise ValueError('Invalid input format definition: %s does not exist.' % args.input_format['']['files'][i])

        if args.replacements:
            if not exists(args.replacements):
                raise ValueError('Invalid input format definition: %s does not exist.' % args.replacements)

            try:
                with open(args.replacements, 'r') as f:
                    args.input_format['']['replacements'] = json.load(f)
            except ValueError as e:
                raise ValueError('Invalid input format definition: The content of %s is not a valid JSON object.' % args.replacements) from e


def process_srcml_args(args):
    if not args.srcml_language:
        raise ValueError('The following argument is required for srcML: --srcml:language')


def process_args(args):
    inators.arg.process_log_level_argument(args, logger)
    inators.arg.process_sys_recursion_limit_argument(args)

    args.hddmin = args_hdd_choices[args.hdd]
    args.hdd_phase_configs = [args_phase_choices[phase] for phase in (args.phase or ['prune'])]

    if args.builder == 'antlr4':
        process_antlr4_args(args)
    elif args.builder == 'srcml':
        process_srcml_args(args)

    picire.cli.process_args(args)


def log_tree(title, hdd_tree):
    logger.debug('%s\n\theight: %s\n\tshape: %s\n\tnodes: %s\n',
                 title,
                 info.height(hdd_tree),
                 ', '.join('%s' % cnt for cnt in info.shape(hdd_tree)),
                 ', '.join('%d %s' % (cnt, ty) for ty, cnt in sorted(info.count(hdd_tree).items())))
    logger.trace('%r', hdd_tree)


def build_with_antlr4(src, *,
                      input_format, start,
                      antlr, lang='python',
                      build_hidden_tokens=False,
                      work_dir):
    """
    Execute ANTLRv4-based tree building part of picireny as if invoked from
    command line, however, control its behaviour not via command line arguments
    but function parameters.

    :param src: Contents of the test case to reduce.
    :param input_format: Dictionary describing the input format.
    :param start: Name of the start rule in [grammarname:]rulename format.
    :param antlr: Path to the ANTLR4 tool (Java jar binary).
    :param lang: The target language of the parser.
    :param build_hidden_tokens: Build hidden tokens of the input format into the
        HDD tree.
    :param work_dir: Path to a working directory.
    :return: The built HDD tree.
    """
    # Get the parameters in a dictionary so that they can be pretty-printed
    args = locals().copy()
    del args['src']
    picire.cli.log_args('Building tree with ANTLRv4', args)

    from .antlr4 import create_hdd_tree
    return create_hdd_tree(src,
                           input_format=input_format, start=start,
                           antlr=antlr, lang=lang,
                           hidden_tokens=build_hidden_tokens,
                           work_dir=work_dir)


def build_with_srcml(src, *, language):
    """
    Execute srcML-based tree building part of picireny as if invoked from
    command line, however, control its behaviour not via command line arguments
    but function parameters.

    :param src: Contents of the test case to reduce.
    :param language: Language of the input source (C, C++, C#, or Java).
    :return: The built HDD tree.
    """
    # Get the parameters in a dictionary so that they can be pretty-printed
    args = locals().copy()
    del args['src']
    picire.cli.log_args('Building tree with srcML', args)

    from .srcml import create_hdd_tree
    return create_hdd_tree(src, language=language)


def reduce(hdd_tree, *,
           hddmin, reduce_class, reduce_config, tester_class, tester_config,
           cache_class=None, unparse_with_whitespace=True,
           hdd_phase_configs=({},), hdd_star=True,
           flatten_recursion=False, squeeze_tree=True, skip_unremovable=True, skip_whitespace=False):
    """
    Execute tree reduction part of picireny as if invoked from command line,
    however, control its behaviour not via command line arguments but function
    parameters.

    :param hdd_tree: HDD tree to reduce.
    :param hddmin: Function implementing a HDD minimization algorithm.
    :param reduce_class: Reference to the reducer class.
    :param reduce_config: Dictionary containing information to initialize the
        reduce_class.
    :param tester_class: Reference to a runnable class that can decide about the
        interestingness of a test case.
    :param tester_config: Dictionary containing information to initialize the
        tester_class.
    :param cache_class: Reference to the cache class to use.
    :param unparse_with_whitespace: Unparse by adding whitespace between
        nonadjacent nodes.
    :param hdd_phase_configs: Sequence of dictionaries containing information to
        parametrize the hddmin function.
    :param hdd_star: Boolean to enable the HDD star algorithm.
    :param flatten_recursion: Boolean to enable flattening left/right-recursive
        trees.
    :param squeeze_tree: Boolean to enable the tree squeezing optimization.
    :param skip_unremovable: Boolean to enable hiding unremovable nodes from
        ddmin.
    :param skip_whitespace: Boolean to enable hiding whitespace-only tokens from
        ddmin.
    :return: The reduced HDD tree.
    """
    # Get the parameters in a dictionary so that they can be pretty-printed
    args = locals().copy()
    del args['hdd_tree']
    picire.cli.log_args('Reduce session starts', args)

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

    # Perform reduction.
    for phase_cnt, phase_config in enumerate(hdd_phase_configs):
        logger.info('Phase #%d', phase_cnt)
        hdd_tree = hddmin(hdd_tree,
                          reduce_class=reduce_class, reduce_config=reduce_config,
                          tester_class=tester_class, tester_config=tester_config,
                          id_prefix=('p%d' % phase_cnt,),
                          cache=cache_class() if cache_class else None,
                          unparse_with_whitespace=unparse_with_whitespace,
                          hdd_star=hdd_star,
                          **phase_config)
        log_tree('Tree after reduction phase #%d' % phase_cnt, hdd_tree)

    return hdd_tree


def execute():
    """
    The main entry point of picireny.
    """
    logging.basicConfig(format='%(message)s')

    arg_parser = ArgumentParser(description='CLI for the Picireny Hierarchical Delta Debugging Framework',
                                parents=[picire.cli.create_parser()], add_help=False)

    # General HDD settings.
    arg_parser.add_argument('--builder', metavar='NAME', choices=['antlr4', 'srcml'], default='antlr4',
                            help='tool to build tree representation from input (%(choices)s; default: %(default)s)')
    arg_parser.add_argument('--hdd', metavar='NAME', choices=args_hdd_choices.keys(), default='hdd',
                            help='HDD variant to run (%(choices)s; default: %(default)s)')
    arg_parser.add_argument('--phase', metavar='NAME', choices=args_phase_choices.keys(), action='append',
                            help='parametrization of the HDD variant to run (%(choices)s; default: prune) '
                                 '(may be specified multiple times to run different parametrizations in sequence)')
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
    inators.arg.add_sys_recursion_limit_argument(arg_parser)
    inators.arg.add_version_argument(arg_parser, version=__version__)

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
    antlerinator.add_antlr_argument(antlr4_grp, long_alias='--antlr4:antlr')
    antlr4_grp.add_argument('--parser', '--antlr4:parser', metavar='LANG', default='python', choices=['python', 'java'],
                            help='language of the generated parsers (%(choices)s; default: %(default)s) '
                                 '(using Java might gain performance, but needs JDK)')

    # srcML-specific settings.
    srcml_grp = arg_parser.add_argument_group('srcML-specific arguments')
    srcml_grp.add_argument('--srcml:language', dest='srcml_language', metavar='LANG', choices=['C', 'C++', 'C#', 'Java'],
                           help='language of the input (%(choices)s; default: %(default)s)')

    args = arg_parser.parse_args()

    try:
        process_args(args)
    except ValueError as e:
        arg_parser.error(e)

    if args.builder == 'antlr4':
        work_dir = join(args.out, 'grammar')
        hdd_tree = build_with_antlr4(args.src,
                                     input_format=args.input_format, start=args.start,
                                     antlr=args.antlr, lang=args.parser,
                                     build_hidden_tokens=args.build_hidden_tokens,
                                     work_dir=work_dir)
        unparse_with_whitespace = not args.build_hidden_tokens
        if args.cleanup:
            rmtree(work_dir)
    elif args.builder == 'srcml':
        hdd_tree = build_with_srcml(args.src, language=args.srcml_language)
        unparse_with_whitespace = False

    hdd_tree = reduce(hdd_tree,
                      hddmin=args.hddmin,
                      reduce_class=args.reduce_class, reduce_config=args.reduce_config,
                      tester_class=args.tester_class, tester_config=args.tester_config,
                      cache_class=args.cache, unparse_with_whitespace=unparse_with_whitespace,
                      hdd_phase_configs=args.hdd_phase_configs, hdd_star=args.hdd_star,
                      flatten_recursion=args.flatten_recursion,
                      squeeze_tree=args.squeeze_tree,
                      skip_unremovable=args.skip_unremovable,
                      skip_whitespace=args.skip_whitespace)
    out_src = hdd_tree.unparse(with_whitespace=unparse_with_whitespace)

    picire.cli.postprocess(args, out_src)
