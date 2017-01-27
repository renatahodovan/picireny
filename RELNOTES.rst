========================
*Picireny* Release Notes
========================

17.1
====

Summary of changes:

* Updated dependency to *Picire* 17.1 and adopted its support for content-based
  result caching.
* Added "squeeze tree" and "hide/skip unremovable tokens" HDD tree
  optimizations.
* Improved handling of erroneous input.
* Extended the HDD algorithm with testing of single-node tree levels to ensure
  1-tree-minimality of output.
* Minor bug fixes and improvements.


16.12
=====

Summary of changes:

* Added support for Java-based input parsing to improve performance.
* Implemented HDD* (fixed-point iteration of hddmin).
* Minor bug fixes and improvements.
* Upgraded dependency to ANTLR v4.6.
* Added *Picireny* to PyPI.


16.7
====

First public release of the *Picireny* Hierarchical Delta Debugging Framework.

Summary of main features:

* ANTLRv4-based input parsing and *Picire*-based ddmin.
* Automatic "smallest allowable syntactic fragment" computation for both parser
  and lexer rules.
* Support for island grammars.
* Python 3 API and out-of-the-box useful CLI.
* py.test-based testing and tox support.
