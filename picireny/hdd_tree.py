# Copyright (c) 2007 Ghassan Misherghi.
# Copyright (c) 2016 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.


class HDDTree:
    # Node states for unparsing.
    KEEP = 0
    REMOVE_TEMP = 1
    REMOVED = 2

    def __init__(self, name, *, start=None, end=None, replace=None):
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
        self.level = 0
        self.tagID = None

    class Position(object):
        """Class defining a position in the input file. Used to recognise line breaks between tokens."""
        def __init__(self, line, idx):
            """
            Initialize position object.

            :param line: Line index in the input.
            :param idx: Absolute character index in the input.
            """
            self.line = line
            self.idx = idx

    def traverse(self, visitor):
        """
        Function providing depth-first traversal for a visitor function.

        :param visitor: Function applying to the visited nodes.
        """
        assert False, 'Should never be reached: it should be overridden in sub-classes.'

    def synthetic_attribute(self, visitor):
        """
        Call visitor on nodes without propagating any values (used by unparsing).

        :param visitor: Function applying on the visited nodes.
        :return: The value returned by visitor after applying on the node.
        """
        assert False, 'Should never be reached: it should be overridden in sub-classes.'

    def inherited_attribute(self, visitor, attribute=None):
        """
        Call visitor on the nodes and propagate the return value to the children (only setLevel uses it).

        :param visitor: Function applying to the visited nodes.
        :param attribute: The propagated value.
        """
        assert False, 'Should never be reached: it should be overridden in sub-classes.'

    def unparse(self):
        """
        Build test case from a HDD tree.

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
                    if node.children[i].start.line > node.children[i - 1].end.line:
                        test_src += '\n'
                    elif node.children[i].start.idx > node.children[i - 1].end.idx:
                        test_src += ' '
                    test_src += attribs[i]

            return test_src

        return self.synthetic_attribute(unparse_attribute)

    def tag(self, level):
        """
        Label every available nodes with incrementing numbers from 0.

        :param level: The level of HDD tree that will be labeled.
        :return: The maximum label/index on the given level.
        """
        def tag_visitor(node):
            if node.level == level and node.state == self.KEEP:
                node.tagID = count[0]
                count[0] += 1
            else:
                # Make sure that tags will not be messed up even if HDD star runs.
                node.tagID = None

        count = [0]
        self.traverse(tag_visitor)
        return count[0]

    def set_remove(self, level, keepers):
        """
        Temporarily remove nodes from the tree on the given level.

        :param level: The level that the nodes will be removed from.
        :param keepers: List of nodes that will be kept.
        """
        def remove(node):
            if node.level == level:
                if node.tagID not in keepers and node.state == self.KEEP:
                    node.state = self.REMOVE_TEMP
        self.traverse(remove)

    def clear_remove(self):
        """Undo temporary removal (change REMOVE_TEMP flags to KEEP)."""
        def clear_r(node):
            if node.state == self.REMOVE_TEMP:
                node.state = self.KEEP
        self.traverse(clear_r)

    def commit_remove(self, level, keepers):
        """
        Make temporary removes permanent on the given level.

        :param level: The level where the removal is executed.
        :param keepers: Nodes that will be kept.
        """
        def remove(node):
            if node.level == level:
                if node.tagID not in keepers:
                    node.state = self.REMOVED
                else:
                    node.state = self.KEEP
        self.traverse(remove)

    def set_levels(self):
        """
        Assign a number to nodes such that nodes on the same level have the same value.

        :return: Return the index of the next level (it will be inherited by the children).
        """
        def set_level(node, current_level):
            node.level = current_level
            return current_level + 1
        self.inherited_attribute(set_level, 0)

    def check(self):
        """Run sanity check on the HDD tree."""
        def bad_parent(node):
            if node is None:
                return
            assert isinstance(node, HDDToken) or None not in node.children, 'Bad parent node: %s' % node.name
        self.traverse(bad_parent)

    def tree_str(self, *, current=None):
        """
        Pretty print HDD tree to help debugging.

        :param current: Reference to a node that will be marked with a '*' in the output.
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
                ''.join(['    ' + line + '\n' for line in ''.join(attrib).splitlines()]))

        return self.synthetic_attribute(_tree_str)

    def replace_with(self, other):
        """
        Replace the current node with `other` in the HDD tree.

        :param other: Node to replace the current with.
        """
        self.parent.children[self.parent.children.index(self)] = other
        other.parent = self.parent


class HDDToken(HDDTree):
    def __init__(self, name, text, *, start, end, replace=None):
        HDDTree.__init__(self, name, start=start, end=end, replace=replace)
        self.text = text

    def traverse(self, visitor):
        visitor(self)

    def synthetic_attribute(self, visitor):
        return visitor(self, [])

    def inherited_attribute(self, visitor, attribute=None):
        visitor(self, attribute)


class HDDRule(HDDTree):
    def __init__(self, name, *, start=None, end=None, replace=None):
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
