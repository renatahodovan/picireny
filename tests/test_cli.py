# Copyright (c) 2016-2018 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

import filecmp
import os
import pytest
import subprocess
import sys


is_windows = sys.platform.startswith('win32')
script_ext = '.bat' if is_windows else '.sh'

tests_dir = os.path.dirname(os.path.abspath(__file__))
resources_dir = os.path.join(tests_dir, 'resources')
antlr = os.getenv('ANTLR')


@pytest.mark.parametrize('test, inp, exp, grammar, rule, input_format', [
    ('test-json-obj-arr-foo', 'inp-obj-arr.json', 'exp-obj-arr-foo.json', 'JSON.g4', 'json', None),
    ('test-json-obj-arr-bar', 'inp-obj-arr.json', 'exp-obj-arr-bar.json', 'JSON.g4', 'json', None),
    ('test-json-obj-arr-baz', 'inp-obj-arr.json', 'exp-obj-arr-baz.json', 'JSON.g4', 'json', None),
    ('test-json-obj-arr-87', 'inp-obj-arr.json', 'exp-obj-arr-87.json', 'JSON.g4', 'json', None),
    ('test-inijson-str-arr-87', 'inp-str-arr.ini', 'exp-str-arr-87.ini', None, None, 'inijson.json'),
])
class TestCli:

    def _run_picireny(self, test, inp, exp, grammar, rule, input_format, tmpdir, args):
        out_dir = '%s' % tmpdir
        cmd = (sys.executable, '-m', 'picireny') \
              + ('--test=' + test + script_ext, '--input=' + inp, '--out=' + out_dir) \
              + ('--log-level=DEBUG', )
        if grammar:
            cmd += ('--grammar=' + grammar, )
        if rule:
            cmd += ('--start=' + rule, )
        if input_format:
            cmd += ('--format=' + input_format, )
        if antlr:
            cmd += ('--antlr=' + antlr, )
        cmd += args
        proc = subprocess.Popen(cmd, cwd=resources_dir)
        proc.communicate()
        assert proc.returncode == 0
        assert filecmp.cmp(os.path.join(out_dir, inp), os.path.join(resources_dir, exp))

    @pytest.mark.parametrize('args_parallel', [
        (),
    ])
    @pytest.mark.parametrize('args_cache', [
        ('--cache=none', ),
        ('--cache=config', ),
        ('--cache=content', ),
    ])
    @pytest.mark.parametrize('args_parser', [
        (),
        ('--parser=java', ),
    ])
    @pytest.mark.parametrize('args_hdd_star', [
        (),
        ('--no-hdd-star', ),
    ])
    @pytest.mark.parametrize('args_squeeze', [
        (),
        ('--no-squeeze-tree', ),
    ])
    @pytest.mark.parametrize('args_skip_unremovable', [
        (),
        ('--no-skip-unremovable', ),
    ])
    def test_light(self, test, inp, exp, grammar, rule, input_format, tmpdir, args_parallel, args_cache, args_parser, args_hdd_star, args_squeeze, args_skip_unremovable):
        self._run_picireny(test, inp, exp, grammar, rule, input_format, tmpdir,
                           args_parallel + args_cache + args_parser + args_hdd_star + args_squeeze + args_skip_unremovable)

    @pytest.mark.parametrize('args_parallel', [
        ('--parallel', ),
    ])
    @pytest.mark.parametrize('args_cache', [
        (),
    ])
    @pytest.mark.parametrize('args_parser', [
        (),
    ])
    @pytest.mark.parametrize('args_hdd_star', [
        (),
    ])
    @pytest.mark.parametrize('args_squeeze', [
        (),
    ])
    @pytest.mark.parametrize('args_skip_unremovable', [
        (),
    ])
    def test_parallel(self, test, inp, exp, grammar, rule, input_format, tmpdir, args_parallel, args_cache, args_parser, args_hdd_star, args_squeeze, args_skip_unremovable):
        self._run_picireny(test, inp, exp, grammar, rule, input_format, tmpdir,
                           args_parallel + args_cache + args_parser + args_hdd_star + args_squeeze + args_skip_unremovable)
