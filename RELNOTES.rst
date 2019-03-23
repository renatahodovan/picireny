========================
*Picireny* Release Notes
========================

19.3
====

Summary of changes:

* Made code Python 2 compatible (with the help of upgraded dependencies
  *Picire* 19.3 and *ANTLeRinator* 4.7.1-1).
* Improved the testing infrastructure (testing Python 2.7 and 3.7 on Travis CI;
  maintenance changes to various CI configurations).


18.10
=====

Summary of changes:

* Added implementation for the recursive variant of the HDD algorithm (a.k.a.
  HDDr).
* Upgraded dependency to *Picire* 18.10 to utilize its new config ID and prefix
  concepts.
* Minor improvements.


18.2
====

Summary of changes:

* Added support for multiple tree builders, and added srcML as an experimental
  builder in addition to the existing ANTLRv4-based solution.
* Generalized HDD implementation to be parametric to express classic HDD and
  Coarse HDD as well.
* Upgraded dependency to *Picire* 18.1 to utilize custom initial granularity.
* Upgraded dependency to ANTLR v4.7.1 (via *ANTLeRinator*).
* Added support for building tokens from hidden ANTLR channels (whitespace,
  comments, etc.) into the tree but also hiding them from the reducer (for
  inputs where whitespace or other hidden tokens may matter during tree
  unparsing).
* Added new module for gathering statistics on trees and improved the logging of
  the results of tree transformation algorithms.
* Improved various algorithms (minimal replacement calculation from ANTLRv4
  grammars, tree flattening for non-syntax-conforming inputs, unremovable node
  detection for rules in addition to tokens).
* Improved Python-Java interworking (for Java-based ANTLRv4 parsers).
* Improved API usability (for use-cases when *Picireny* is not called via its
  CLI).
* Improved the testing infrastructure (by using the Coveralls online service).
* Minor bug fixes and internal refactorings.


17.10
=====

Summary of changes:

* Improved the way how input format can be defined by enabling the use of a more
  consistent and well-defined config file.
* Upgraded dependency to *Picire* 17.10 to utilize its Windows support.
* Minor bug fixes.


17.7
====

Summary of changes:

* Added implementation for the coarse variant of the HDD algorithm.
* Implemented heuristical optimization to flatten left and right-recursive tree
  structures.
* Improvements to the internal tree representation.
* Simplified usage and ANTLR dependency installation via *ANTLeRinator*, and
  upgraded dependency to *Picire* 17.6.
* Improved the testing infrastructure (support for Python 3.6 and code coverage
  measurement).


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
