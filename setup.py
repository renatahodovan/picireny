# Copyright (c) 2016 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.md or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import json

from os.path import dirname, join
from setuptools import setup, find_packages

with open(join(dirname(__file__), 'picireny/VERSION'), 'rb') as f:
    version = f.read().decode('ascii').strip()

with open(join(dirname(__file__), 'picireny/antlr4/resources/dependencies.json'), 'r') as f:
    deps_json = json.load(f)
    runtime_req = deps_json['runtime_req']
    runtime_url = deps_json['runtime_url']


setup(
    name='picireny',
    version=version,
    packages=find_packages(),
    url='https://github.com/renatahodovan/picireny',
    license='BSD',
    author='Renata Hodovan, Akos Kiss',
    author_email='hodovan@inf.u-szeged.hu, akiss@inf.u-szeged.hu',
    description='Picireny Hierarchical Delta Debugging Framework',
    long_description=open('README.md').read(),
    install_requires=['picire', runtime_req],
    dependency_links=[runtime_url],
    zip_safe=False,
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'picireny = picireny.cli:execute',
            'picireny-install-antlr4 = picireny.antlr4.install:execute'
        ]
    },
)
