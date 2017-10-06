#! /bin/bash
$(dirname $0)/sut-inijson-load.py $1 2>&1 | grep -q "87"
