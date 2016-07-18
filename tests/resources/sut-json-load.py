#!/usr/bin/env python3

import json
import sys


with open(sys.argv[1], 'r') as f:
    j = json.load(f)

print("%s" % repr(j))
