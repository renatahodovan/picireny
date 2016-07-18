# Picireny
_Hierarchical Delta Debugging Framework_

Picireny is a Python3 implementation of the Hierarchical Delta Debugging
(HDD in short) algorithm adapted to use [ANTLR v4](http://www.antlr.org/)
for parsing both the input and the grammar(s) describing the format of
the input. It relies on [*picire*](https://github.com/renatahodovan/picire)
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


## Requirements

* Python >= 3.4
* pip and setuptools Python packages (the latter is automatically installed by
  pip).
* ANTLR v4


## Install

Clone the project and run setuptools:

    wget -O antlr.jar https://github.com/akosthekiss/antlr4/releases/download/4.5.4-SNAPSHOT%2Bpy3fixes-20160705-1111/antlr4-4.5.4-SNAPSHOT.py3fixes-20160705-1111.jar
    pip install -r requirements.txt
    python setup.py install

Quick pip install from PyPi will be available when ANTLR 4.5.4 is officially
released containing important fixes to the Python target and runtime.

## Usage

*picireny* uses the same CLI as *picire* and hence accepts the same
[options](https://github.com/renatahodovan/picire/blob/master/README.md#usage).
On top of the inherited ones, *picireny* accepts three further arguments:

* `--grammars` (required): List of grammars describing the input format. (You
  can write them by hand or simply download them from the [ANTLR v4 grammars
  repository](https://github.com/antlr/grammars-v4)).
* `--start-rule` (required): Name of the rule where parsing has to start.
* `--antlr` (required): Path the ANTLR tool jar.
* `--islands` (optional): File describing how to process island grammars if
  needed.

Example usage to reduce an HTML file:

    picireny --input=<path/to/the/input.html> --test=<path/to/the/tester> \
             --grammars "HTMLLexer.g4 HTMLParser.g4" --start-rule document --antlr antlr.jar \
             --parallel --subset-iterator=skip --complement-iterator=backward

## Compatibility

*picireny* was tested on:

* Linux (Ubuntu 14.04 / 15.10)
* Mac OS X (OS X El Capitan - 10.11).


## Copyright and Licensing

See [LICENSE](LICENSE.md).
