#!/bin/bash
sudo apt install -y sqlite
git config pull.rebase true
python -m pip install --upgrade pip
python -m pip install -r development.txt
python -m pip install -e .
python -m flask initdb
cd cacao_accounting/static/
cd ..
cd ..
bash run_server.sh
