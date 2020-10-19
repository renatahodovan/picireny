# Copyright (c) 2007 Ghassan Misherghi.
# Copyright (c) 2016-2021 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from itertools import count


class Position(object):
    """
    Class defining a position in the input file. Used to recognise line breaks
    between tokens.
    """
    def __init__(self, line, idx):
        """
        Initialize position object.

        :param line: Line index in the input.
        :param idx: Absolute character index in the input.
        """
        self.line = line
        self.idx = idx

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__, self.line, self.idx)


class HDDTree:
    # Node states for unparsing.
    REMOVED = 0
    KEEP = 1

    # ID generator
    __id = count()

    def __init__(self, name, start=None, end=None, replace=None):
        """
        Initialize a HDD tree/node.

        :param name: The name of the node.
        :param start: Position object describing the start of the HDDTree node.
        :param end: Position object describing the end of the HDDTree node.
        :param replace: The minimal replacement string of the current node.
        """
        self.name = name
        self.replace = replace
        self.start = start
        self.end = end
        self.parent = None
        self.state = self.KEEP
        self.id = next(self.__id)

    def unparse(self, with_whitespace=True, transform=None):
        """
        Build test case from a HDD tree.

        :param with_whitespace: Add whitespace (space, new line) to separate
            nonadjacent nodes.
        :param transform: A function applied to each node before unparsing, or
            None.
        :return: The unparsed test case.
        """
        def _unparse(node):
            if transform:
                node = transform(node)

            if node.state != node.KEEP:
                return node.replace

            # Keep the text of the token.
            if isinstance(node, HDDToken):
                return node.text

            if not node.children:
                return ''

            # Concat the text of children.
            child_strs = [_unparse(child) for child in node.children]
            node_str = child_strs[0]
            for i in range(1, len(node.children)):
                # Do not add extra spaces if the next chunk is empty.
                if not child_strs[i]:
                    continue
                if with_whitespace:
                    if node.children[i].start.line > node.children[i - 1].end.line:
                        node_str += '\n'
                    elif node.children[i].start.idx > node.children[i - 1].end.idx:
                        node_str += ' '
                node_str += child_strs[i]

            return node_str

        return _unparse(self)

    def replace_with(self, other):
        """
        Replace the current node with `other` in the HDD tree.

        :param other: Node to replace the current with.
        """
        self.parent.children[self.parent.children.index(self)] = other
        other.parent = self.parent


class HDDToken(HDDTree):
    def __init__(self, name, text, start, end, replace=None):
        HDDTree.__init__(self, name, start=start, end=end, replace=replace)
        self.text = text

    def __repr__(self):
        parts = [
            'name=%r' % self.name,
            'text=%r' % self.text,
        ]
        if self.replace is not None:
            parts.append('replace=%r' % self.replace)
        if self.start is not None:
            parts.append('start=%r' % self.start)
        if self.end is not None:
            parts.append('end=%r' % self.end)
        parts.append('id=%r' % self.id)
        if self.state != self.KEEP:
            parts.append('state=%r' % self.state)

        return '%s(%s)' % (self.__class__.__name__, ', '.join(parts))


class HDDRule(HDDTree):
    def __init__(self, name, start=None, end=None, replace=None):
        HDDTree.__init__(self, name, start=start, end=end, replace=replace)
        self.children = []

    def add_child(self, child):
        self.children.append(child)
        child.parent = self

    def add_children(self, children):
        for child in children:
            self.add_child(child)

    def remove_child(self, child):
        self.children.remove(child)

    def __repr__(self):
        def _indent(text, prefix):
            return ''.join(prefix + line for line in text.splitlines(True))

        parts = [
            'name=%r' % self.name,
        ]
        if self.replace is not None:
            parts.append('replace=%r' % self.replace)
        if self.start is not None:
            parts.append('start=%r' % self.start)
        if self.end is not None:
            parts.append('end=%r' % self.end)
        parts.append('id=%r' % self.id)
        if self.state != self.KEEP:
            parts.append('state=%r' % self.state)
        if self.state == self.KEEP and self.children:
            parts.append('children=[\n%s\n]' % _indent(',\n'.join(repr(child) for child in self.children), '  '))

        return '%s(%s)' % (self.__class__.__name__, ', '.join(parts))
