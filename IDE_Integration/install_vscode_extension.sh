#!/bin/bash
set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create the extension directory
mkdir -p ~/.vscode/extensions/dushino.zap-language

# Copy the extension files
cp -r "$SCRIPT_DIR/dushino.zap-language"/* ~/.vscode/extensions/dushino.zap-language/

# remove extensions.json to force rescan of plugins
rm ~/.vscode/extensions/extensions.json

echo "VS Code extension installed successfully!"
echo "Please reload VS Code to activate the extension."
