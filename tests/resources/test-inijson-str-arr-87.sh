#! /bin/bash
python $(dirname $0)/sut-inijson-load.py $1 | grep -q "87"
