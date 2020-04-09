# Copyright (c) 2007 Ghassan Misherghi.
# Copyright (c) 2016-2020 Renata Hodovan, Akos Kiss.
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

    def traverse(self, visitor):
        """
        Function providing depth-first traversal for a visitor function.

        :param visitor: Function applying to the visited nodes.
        """
        raise NotImplementedError()

    def synthetic_attribute(self, visitor):
        """
        Call visitor on nodes without propagating any values (used by
        unparsing).

        :param visitor: Function applying on the visited nodes.
        :return: The value returned by visitor after applying on the node.
        """
        raise NotImplementedError()

    def inherited_attribute(self, visitor, attribute=None):
        """
        Call visitor on the nodes and propagate the return value to the children
        (only setLevel uses it).

        :param visitor: Function applying to the visited nodes.
        :param attribute: The propagated value.
        """
        raise NotImplementedError()

    def unparse(self, with_whitespace=True):
        """
        Build test case from a HDD tree.

        :param with_whitespace: Add whitespace (space, new line) to separate
            nonadjacent nodes.
        :return: The unparsed test case.
        """
        def unparse_attribute(node, attribs):
            if node.state != self.KEEP:
                return node.replace

            # Keep the text of the token.
            if isinstance(node, HDDToken):
                return node.text

            if not attribs:
                return ''

            # Concat the text of children.
            assert node.children
            test_src = attribs[0]
            if len(node.children) > 1:
                for i in range(1, len(node.children)):
                    # Do not add extra spaces if the next chunk is empty.
                    if not attribs[i]:
                        continue
                    if with_whitespace:
                        if node.children[i].start.line > node.children[i - 1].end.line:
                            test_src += '\n'
                        elif node.children[i].start.idx > node.children[i - 1].end.idx:
                            test_src += ' '
                    test_src += attribs[i]

            return test_src

        return self.synthetic_attribute(unparse_attribute)

    def set_state(self, ids, keepers):
        """
        Set the status of some selected nodes: if they are in the collection of
        keepers, mark them as kept, otherwise mark them as removed.

        :param ids: The collection (list or set) of node IDs to set state for.
        :param keepers: The collection (list or set) of IDs to be kept.
        """
        def _set_state(node):
            if node.id in ids:
                node.state = self.KEEP if node.id in keepers else self.REMOVED
        self.traverse(_set_state)

    def check(self):
        """
        Run sanity check on the HDD tree.
        """
        def bad_parent(node):
            if node is None:
                return
            assert isinstance(node, HDDToken) or None not in node.children, 'Bad parent node: %s' % node.name
        self.traverse(bad_parent)

    def tree_str(self, current=None):
        """
        Pretty print HDD tree to help debugging.

        :param current: Reference to a node that will be marked with a '*' in
            the output.
        :return: String representation of the tree.
        """

        def _tree_str(node, attrib):
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
                ''.join('    ' + line + '\n' for line in ''.join(attrib).splitlines()))

        return self.synthetic_attribute(_tree_str)

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

    def traverse(self, visitor):
        visitor(self)

    def synthetic_attribute(self, visitor):
        return visitor(self, [])

    def inherited_attribute(self, visitor, attribute=None):
        visitor(self, attribute)


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

    def traverse(self, visitor):
        visitor(self)
        if self.state != self.KEEP:
            return
        for child in self.children:
            child.traverse(visitor)

    def synthetic_attribute(self, visitor):
        if self.state != self.KEEP:
            return visitor(self, [])
        return visitor(self, [child.synthetic_attribute(visitor) for child in self.children])

    def inherited_attribute(self, visitor, attribute=None):
        inherit_value = visitor(self, attribute)

        if self.state != self.KEEP:
            return

        for child in self.children:
            child.inherited_attribute(visitor, inherit_value)
