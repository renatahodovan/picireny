#!/usr/bin/env python3

import configparser
import json
import sys


c = configparser.ConfigParser(allow_no_value=True)
with open(sys.argv[1], 'r') as f:
    c.read_file(f)

for s in c.sections():
    for o in c.options(s):
        j = json.loads(c.get(s, o))

c.write(sys.stdout)
