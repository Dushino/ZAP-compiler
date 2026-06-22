#!/bin/bash

# only first time
#curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
#sudo apt-get install -y nodejs

#mkdir -p ~/.npm-global
#npm config set prefix '~/.npm-global'
#export PATH="$HOME/.npm-global/bin:$PATH"
#source ~/.bashrc
#npm install -g @vscode/vsce
# end of first time install only

source ~/.bashrc
cd dushino.zap-language
npx @vscode/vsce package

