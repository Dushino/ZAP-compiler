#!/bin/bash
source ./python_venv/bin/activate
pyinstaller -D -F --onefile -n zapc -c "compiler.py"
cp ./dist/zapc ~/local/bin/zapc
deactivate


