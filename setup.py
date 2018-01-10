# Copyright (c) 2016-2018 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

from os.path import dirname, join
from setuptools import setup, find_packages

with open(join(dirname(__file__), 'picireny/VERSION'), 'rb') as f:
    version = f.read().decode('ascii').strip()


setup(
    name='picireny',
    version=version,
    packages=find_packages(),
    url='https://github.com/renatahodovan/picireny',
    license='BSD',
    author='Renata Hodovan, Akos Kiss',
    author_email='hodovan@inf.u-szeged.hu, akiss@inf.u-szeged.hu',
    description='Picireny Hierarchical Delta Debugging Framework',
    long_description=open('README.rst').read(),
    install_requires=['antlerinator==4.7.1', 'picire==18.1'],
    zip_safe=False,
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'picireny = picireny.cli:execute'
        ]
    },
)
