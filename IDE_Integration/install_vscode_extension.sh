#!/bin/bash
set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create the extension directory
mkdir -p ~/.vscode/extensions/dushino.zap-language
mkdir -p ~/.antigravity/extensions/dushino.zap-language

# Copy the extension files
cp -r "$SCRIPT_DIR/dushino.zap-language"/* ~/.vscode/extensions/dushino.zap-language/
cp -r "$SCRIPT_DIR/dushino.zap-language"/* ~/.antigravity/extensions/dushino.zap-language/

# remove extensions.json to force rescan of plugins
rm ~/.vscode/extensions/extensions.json
rm ~/.antigravity/extensions/extensions.json

echo "VS Code extension installed successfully!"
echo "Please reload VS Code / Antigravity to activate the extension."
