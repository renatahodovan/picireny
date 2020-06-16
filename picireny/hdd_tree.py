# Copyright (c) 2007 Ghassan Misherghi.
# Copyright (c) 2016-2021 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.


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


class HDDTree:
    # Node states for unparsing.
    REMOVED = 0
    KEEP = 1

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
        self.id = id(self)

    def unparse(self, with_whitespace=True):
        """
        Build test case from a HDD tree.

        :param with_whitespace: Add whitespace (space, new line) to separate
            nonadjacent nodes.
        :return: The unparsed test case.
        """
        def _unparse(node):
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

    def set_state(self, ids, keepers):
        """
        Set the status of some selected nodes: if they are in the collection of
        keepers, mark them as kept, otherwise mark them as removed.

        :param ids: The collection (list or set) of node IDs to set state for.
        :param keepers: The collection (list or set) of IDs to be kept.
        """
        def _set_state(node):
            if node.id in ids:
                node.state = node.KEEP if node.id in keepers else node.REMOVED
            elif isinstance(node, HDDRule) and node.state == node.KEEP:
                for child in node.children:
                    _set_state(child)
        _set_state(self)

    def tree_str(self, current=None):
        """
        Pretty print HDD tree to help debugging.

        :param current: Reference to a node that will be marked with a '*' in
            the output.
        :return: String representation of the tree.
        """
        def _indent(text, prefix):
            return ''.join(prefix + line for line in text.splitlines(True))

        def _tree_str(node):

            if node.state != node.KEEP:
                return ''

            return '[%s:%s]%s%s%s(%s)\n%s' % (
                node.name,
                node.__class__.__name__,
                ('"%s"' % node.text) if isinstance(node, HDDToken) else '',
                ('(ln:%d,i:%d)-(ln:%d,i:%d)' % (node.start.line, node.start.idx, node.end.line,
                                                node.end.idx)) if self.start is not None and self.end is not None else '',
                '*' if node == current else '',
                node.replace,
                ''.join(_indent(_tree_str(child), '    ') for child in node.children) if isinstance(node, HDDRule) else '')

        return _tree_str(self)

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
