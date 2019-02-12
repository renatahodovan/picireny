========
Picireny
========
*Hierarchical Delta Debugging Framework*

.. image:: https://badge.fury.io/py/picireny.svg
   :target: https://badge.fury.io/py/picireny
.. image:: https://travis-ci.org/renatahodovan/picireny.svg?branch=master
   :target: https://travis-ci.org/renatahodovan/picireny
.. image:: https://ci.appveyor.com/api/projects/status/jsg8qiflkakbhni1/branch/master?svg=true
   :target: https://ci.appveyor.com/project/renatahodovan/picireny/branch/master
.. image:: https://coveralls.io/repos/github/renatahodovan/picireny/badge.svg?branch=master
   :target: https://coveralls.io/github/renatahodovan/picireny?branch=master

Picireny is a Python implementation of the Hierarchical Delta Debugging
(HDD in short) algorithm adapted to use ANTLR_ v4 for parsing both the input
and the grammar(s) describing the format of the input. It relies on picire_
to provide the implementation of the core Delta Debugging algorithm along
with various tweaks like parallelization. Just like the *picire* framework,
*picireny* can also be used either as a command line tool or as a library.

Both Hierarchical Delta Debugging and Delta Debugging automatically reduce
"interesting" tests while keeping their "interesting" behaviour. (E.g.,
"interestingness" may mean failure-inducing input to a system-under-test.)
However, HDD is an improvement that tries to investigate less test cases during
the reduction process by making use of knowledge on the structure of the input.

The tool (and the algorithm) works iteratively in several ways. As a first
step, it splits up the input into tokens and organizes them in a tree structure
as defined by a grammar. Then, iteratively, it invokes Delta Debugging on each
level of the tree from top to bottom, and DD is an iterative process itself,
too. Finally, the nodes kept in the tree are "unparsed" to yield a reduced but
still "interesting" output.

.. _picire: https://github.com/renatahodovan/picire


Requirements
============

* Python_ ~= 2.7 or >= 3.4
* pip_ and setuptools Python packages (the latter is automatically installed by
  pip).
* ANTLR_ v4
* Java_ SE >= 7 JRE or JDK (the latter is optional, only needed if Java is used
  as the parser language)

.. _Python: https://www.python.org
.. _pip: https://pip.pypa.io
.. _ANTLR: http://www.antlr.org
.. _Java: https://www.oracle.com/java/


Install
=======

The quick way::

    pip install picireny

Alternatively, by cloning the project and running setuptools::

    python setup.py install


Usage
=====

*picireny* uses the same CLI as *picire* and hence accepts the same
options_.
On top of the inherited ones, *picireny* accepts several further arguments:

* ``--grammar`` (optional): List of grammars describing the input format. (You
  can write them by hand or simply download them from the
  `ANTLR v4 grammars repository`_.)
* ``--start`` (optional): Name of the start rule (optionally prefixed with a
  grammar name) as ``[grammarname:]rulename``.
* ``--replacements`` (optional): Json file containing rule names and minimal
  replacement strings (otherwise these are calculated automatically) (see
  schema__).
* ``--format`` (optional): Json file describing the input format (see schema__
  and example_). This descriptor can incorporate all the above (``--grammar``,
  ``--start`` and ``--replacements``) properties, along with the possibility of
  island grammar definitions. If both ``--format`` and the aforementioned
  arguments are present, then the latter will override the appropriate values of
  the format file.
* ``--antlr`` (optional): Path to the ANTLR tool jar.
* ``--parser`` (optional): Language of the generated parser. Currently 'python'
  (default) and 'java' targets (faster, but needs JDK) are supported.

Note: although, all the arguments are optional, the grammar files and the start
rule of the top-level parser must be defined with an arbitrary combination of the
``--format``, ``--grammars``, and ``--start`` arguments.

.. _options: https://github.com/renatahodovan/picire/tree/master/README.rst#usage
.. _`ANTLR v4 grammars repository`: https://github.com/antlr/grammars-v4
.. __: schemas/replacements.json
.. __: schemas/format.json
.. _example: tests/resources/inijson.json

Example usage to reduce an HTML file::

    picireny --input=<path/to/the/input.html> --test=<path/to/the/tester> \
             --grammar "HTMLLexer.g4 HTMLParser.g4" --start htmlDocument \
             --parallel --subset-iterator=skip --complement-iterator=backward


Compatibility
=============

*picireny* was tested on:

* Linux (Ubuntu 14.04 / 16.04 / 18.04)
* Mac OS X (El Capitan 10.11 / Sierra 10.12 / High Sierra 10.13 / Mojave 10.14)
* Windows (Server 2012 R2)


Acknowledgement and Citations
=============================

*picireny* is motivated by the idea of Hierarchial Delta Debugging:

* G. Misherghi, Z. Su: "HDD: Hierarchical delta debugging",
  ICSE 2006.

The details of the modernized reimplementation and further improvements are
published in:

* R. Hodovan, A. Kiss: "Modernizing Hierarchical Delta Debugging.",
  A-TEST 2016.
* R. Hodovan, A. Kiss, T. Gyimothy: "Tree Preprocessing and Test Outcome
  Caching for Efficient Hierarchical Delta Debugging", AST 2017.
* R. Hodovan, A. Kiss, T. Gyimothy: "Coarse Hierarchical Delta Debugging",
  ICSME 2017.
* A. Kiss, R. Hodovan, T. Gyimothy: "HDDr: A Recursive Variant of the
  Hierarchical Delta Debugging Algorithm", A-TEST 2018.


Copyright and Licensing
=======================

Licensed under the BSD 3-Clause License_.

.. _License: LICENSE.rst
