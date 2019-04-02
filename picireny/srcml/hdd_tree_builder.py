# Copyright (c) 2018-2019 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import logging
import xml.etree.ElementTree as ET

from subprocess import CalledProcessError, PIPE, Popen

from ..hdd_tree import HDDRule, HDDToken, Position
from ..transform import remove_empty_nodes


logger = logging.getLogger(__name__)


def calculate_end_position(text, start):
    return Position(start.line + len(text.splitlines()) - 1, start.idx + len(text))


def build_hdd_tree(element, start):
    name = element.tag
    name = name.replace('{http://www.srcML.org/srcML/src}', 'src:')
    name = name.replace('{http://www.srcML.org/srcML/cpp}', 'cpp:')
    name = name.replace('{http://www.srcML.org/srcML/position}', 'pos:')

    rule = HDDRule(name, start=start, end=start, replace='')
    result = [rule]

    if element.text:
        end = calculate_end_position(element.text, start)
        rule.add_child(HDDToken('{name}@text'.format(name=name), element.text, start=start, end=end, replace=element.text))
        rule.end = end

    for child in list(element):
        if child.tag.startswith('{http://www.srcML.org/srcML/position}'):
            continue
        for node in build_hdd_tree(child, rule.end):
            rule.add_child(node)
            rule.end = rule.children[-1].end

    if element.tail:
        result += [HDDToken('{name}@tail'.format(name=name), element.tail, start=rule.end, end=calculate_end_position(element.tail, rule.end), replace=element.tail)]

    return result


def create_hdd_tree(src, language):
    """
    Build a tree that the HDD algorithm can work with.

    :param src: Input source to srcML.
    :param language: Language of the input source (C, C++, C#, or Java).
    :return: The root of the created HDD tree.
    """

    cmd = 'srcml --language={language}'.format(language=language)
    proc = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE, shell=True)
    stdout, stderr = proc.communicate(src)
    if proc.returncode:
        logger.error('Parsing with srcml failed!\n%s\n%s\n', stdout, stderr)
        raise CalledProcessError(returncode=proc.returncode, cmd=cmd, output=stdout + stderr)

    root = ET.fromstring(stdout)

    tree_result = build_hdd_tree(root, Position(1, 1))
    assert len(tree_result) == 1
    tree = tree_result[0]

    tree = remove_empty_nodes(tree)
    return tree
