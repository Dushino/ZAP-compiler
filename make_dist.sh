#!/bin/bash
set -e
source ./python_venv/bin/activate
pyinstaller -D -F --onefile -n zapc -c "compiler.py"

# Set ZAPC_INSTALL_DIR to override the default install location.
INSTALL_DIR="${ZAPC_INSTALL_DIR:-$HOME/local/bin}"
mkdir -p "$INSTALL_DIR"
cp ./dist/zapc "$INSTALL_DIR/zapc"
deactivate


