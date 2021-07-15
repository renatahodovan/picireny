@echo off
python %~f0\..\sut-json-load.py %1 | find "bar" >NUL 2>&1
