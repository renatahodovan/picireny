#!/usr/bin/env python3

import configparser
import json
import sys


c = configparser.ConfigParser(allow_no_value=True)
c.read_file(open(sys.argv[1], 'r'))

for s in c.sections():
    for o in c.options(s):
        j = json.loads(c.get(s, o))

c.write(sys.stdout)
