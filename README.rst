========
Picireny
========
*Hierarchical Delta Debugging Framework*

.. image:: https://badge.fury.io/py/picireny.svg
   :target: https://badge.fury.io/py/picireny
.. image:: https://travis-ci.org/renatahodovan/picireny.svg?branch=master
   :target: https://travis-ci.org/renatahodovan/picireny

Picireny is a Python 3 implementation of the Hierarchical Delta Debugging
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

* Python_ >= 3.4
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

Once the project is installed, a helper script becomes available that downloads
the right version of the ANTLR v4 tool jar::

    picireny-install-antlr4


Usage
=====

*picireny* uses the same CLI as *picire* and hence accepts the same
options_.
On top of the inherited ones, *picireny* accepts several further arguments:

* `--grammars` (required): List of grammars describing the input format. (You
  can write them by hand or simply download them from the
  `ANTLR v4 grammars repository`_.
* `--start-rule` (required): Name of the rule where parsing has to start.
* `--antlr` (optional): Path the ANTLR tool jar.
* `--parser` (optional): Language of the generated parser. Currently 'python'
  (default) and 'java' targets (faster, but needs JDK) are supported.
* `--islands` (optional): File describing how to process island grammars if
  needed.

.. _`ANTLR v4 grammars repository`: https://github.com/antlr/grammars-v4
.. _options: https://github.com/renatahodovan/picire/blob/master/README.rst#usage

Example usage to reduce an HTML file::

    picireny --input=<path/to/the/input.html> --test=<path/to/the/tester> \
             --grammars "HTMLLexer.g4 HTMLParser.g4" --start-rule document \
             --parallel --subset-iterator=skip --complement-iterator=backward


Compatibility
=============

*picireny* was tested on:

* Linux (Ubuntu 14.04 / 15.10)
* Mac OS X (OS X El Capitan - 10.11).


Copyright and Licensing
=======================

See LICENSE_.

.. _LICENSE: LICENSE.rst
