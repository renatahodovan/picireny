========
Picireny
========
*Hierarchical Delta Debugging Framework*

.. image:: https://img.shields.io/pypi/v/picireny?logo=python&logoColor=white
   :target: https://pypi.org/project/picireny/
.. image:: https://img.shields.io/pypi/l/picireny?logo=open-source-initiative&logoColor=white
   :target: https://pypi.org/project/picireny/
.. image:: https://img.shields.io/github/workflow/status/renatahodovan/picireny/main/master?logo=github&logoColor=white
   :target: https://github.com/renatahodovan/picireny/actions
.. image:: https://img.shields.io/coveralls/github/renatahodovan/picireny/master?logo=coveralls&logoColor=white
   :target: https://coveralls.io/github/renatahodovan/picireny

*Picireny* is a Python implementation of the Hierarchical Delta Debugging
(HDD in short) algorithm adapted to use ANTLR_ v4 for parsing both the input
and the grammar(s) describing the format of the input. It relies on Picire_
to provide the implementation of the core Delta Debugging algorithm along
with various tweaks like parallelization. Just like the *Picire* framework,
*Picireny* can also be used either as a command line tool or as a library.

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

.. _ANTLR: http://www.antlr.org
.. _Picire: https://github.com/renatahodovan/picire


Requirements
============

* Python_ >= 3.5
* Java_ SE >= 7 JRE or JDK (the latter is optional, only needed if Java is used
  as the parser language)

.. _Python: https://www.python.org
.. _Java: https://www.oracle.com/java/


Install
=======

To use *Picireny* in another project, it can be added to ``setup.cfg`` as an
install requirement (if using setuptools_ with declarative config):

.. code-block:: ini

    [options]
    install_requires =
        picireny

To install *Picireny* manually, e.g., into a virtual environment, use pip_::

    pip install picireny

The above approaches install the latest release of *Picireny* from PyPI_.
Alternatively, for the development version, clone the project and perform a
local install::

    pip install .

.. _setuptools: https://github.com/pypa/setuptools
.. _pip: https://pip.pypa.io
.. _PyPI: https://pypi.org/


Usage
=====

*Picireny* uses the same CLI as *Picire* and hence accepts the same
options_.
On top of the inherited ones, *Picireny* accepts several further arguments:

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
             --grammar HTMLLexer.g4 HTMLParser.g4 --start htmlDocument \
             --parallel --subset-iterator=skip --complement-iterator=backward


Compatibility
=============

*Picireny* was tested on:

* Linux (Ubuntu 14.04 / 16.04 / 18.04 / 20.04)
* OS X / macOS (10.11 / 10.12 / 10.13 / 10.14 / 10.15 / 11)
* Windows (Server 2012 R2 / Server version 1809 / Windows 10)


Acknowledgement and Citations
=============================

*Picireny* is motivated by the idea of Hierarchical Delta Debugging:

* Ghassan Misherghi and Zhendong Su. HDD: Hierarchical Delta Debugging.
  In Proceedings of the 28th International Conference on Software Engineering
  (ICSE '06), pages 142-151, Shanghai, China, May 2006. ACM.
  https://doi.org/10.1145/1134285.1134307

The details of the modernized re-implementation and further improvements are
published in:

* Renata Hodovan and Akos Kiss. Modernizing Hierarchical Delta Debugging.
  In Proceedings of the 7th International Workshop on Automating Test Case
  Design, Selection, and Evaluation (A-TEST 2016), pages 31-37, Seattle,
  Washington, USA, November 2016. ACM.
  https://doi.org/10.1145/2994291.2994296
* Renata Hodovan, Akos Kiss, and Tibor Gyimothy. Tree Preprocessing and Test
  Outcome Caching for Efficient Hierarchical Delta Debugging.
  In Proceedings of the 12th IEEE/ACM International Workshop on Automation of
  Software Testing (AST 2017), pages 23-29, Buenos Aires, Argentina, May 2017.
  IEEE.
  https://doi.org/10.1109/AST.2017.4
* Renata Hodovan, Akos Kiss, and Tibor Gyimothy. Coarse Hierarchical Delta
  Debugging.
  In Proceedings of the 33rd IEEE International Conference on Software
  Maintenance and Evolution (ICSME 2017), pages 194-203, Shanghai, China,
  September 2017. IEEE.
  https://doi.org/10.1109/ICSME.2017.26
* Akos Kiss, Renata Hodovan, and Tibor Gyimothy. HDDr: A Recursive Variant of
  the Hierarchical Delta Debugging Algorithm.
  In Proceedings of the 9th ACM SIGSOFT International Workshop on Automating
  Test Case Design, Selection, and Evaluation (A-TEST 2018), pages 16-22, Lake
  Buena Vista, Florida, USA, November 2018. ACM.
  https://doi.org/10.1145/3278186.3278189
* Daniel Vince, Renata Hodovan, Daniella Barsony, and Akos Kiss. Extending
  Hierarchical Delta Debugging with Hoisting.
  In Proceedings of the 2nd ACM/IEEE International Conference on Automation of
  Software Test (AST 2021), pages 60-69, Madrid, Spain (Virtual), May 2021.
  IEEE.
  https://doi.org/10.1109/AST52587.2021.00015


Copyright and Licensing
=======================

Licensed under the BSD 3-Clause License_.

.. _License: LICENSE.rst
