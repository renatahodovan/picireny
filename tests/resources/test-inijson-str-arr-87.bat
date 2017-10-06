@echo off
%~f0\..\sut-inijson-load.py %1 2>&1 | find "87" >NUL 2>&1
