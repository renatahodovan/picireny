#!/usr/bin/env python3

import json
import sys


with open(sys.argv[1], 'r', encoding='utf-8') as f:
    j = json.load(f)

print(f'{j!r}')
