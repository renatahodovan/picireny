# Copyright (c) 2016-2022 Renata Hodovan, Akos Kiss.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.

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
    ('test-inijson-str-arr-87', 'inp-str-arr.ini', 'exp-str-arr-87.ini', None, None, 'inijson-crlf.json' if is_windows else 'inijson.json'),
])
@pytest.mark.parametrize('args', [
    ('--cache=config', ),
    ('--no-skip-unremovable', '--parser=java', '--cache=content', ),
    ('--no-squeeze-tree', '--parser=java', '--cache=none', ),
    ('--no-squeeze-tree', '--no-skip-unremovable', '--cache=config', ),
    ('--no-hdd-star', '--parser=java', '--cache=content', ),
    ('--no-hdd-star', '--no-skip-unremovable', '--cache=none', ),
    ('--no-hdd-star', '--no-squeeze-tree', '--cache=config', ),
    ('--no-hdd-star', '--no-squeeze-tree', '--no-skip-unremovable', '--parser=java', '--cache=content', ),
    ('--parallel', ),
])
def test_cli(test, inp, exp, grammar, rule, input_format, args, tmpdir):
    out_dir = str(tmpdir)
    cmd = (sys.executable, '-m', 'picireny') \
          + (f'--test={test}{script_ext}', f'--input={inp}', f'--out={out_dir}') \
          + ('--log-level=TRACE', )
    if grammar:
        cmd += (f'--grammar={grammar}', )
    if rule:
        cmd += (f'--start={rule}', )
    if input_format:
        cmd += (f'--format={input_format}', )
    if antlr:
        cmd += (f'--antlr={antlr}', )
    cmd += args
    subprocess.run(cmd, cwd=resources_dir, check=True)

    with open(os.path.join(out_dir, inp), 'rb') as outf:
        outb = outf.read()
    with open(os.path.join(resources_dir, exp), 'rb') as expf:
        expb = expf.read()
    assert outb == expb
