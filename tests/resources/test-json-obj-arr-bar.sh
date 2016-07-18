#! /bin/bash
./sut-json-load.py $1 2>&1 | grep -q "bar"
