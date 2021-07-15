#! /bin/bash
python $(dirname $0)/sut-json-load.py $1 | grep -q "baz"
