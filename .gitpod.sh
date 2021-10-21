#!/bin/bash
sudo apt install -y sqlite
git config pull.rebase true
python -m pip install --upgrade pip
python -m pip install --upgrade pip
python -m pip install -r development.txt
python -m pip install -e .
python setup.py develop
python -m flask setupdb
yarn
export CACAO_TEST=True
export FLASK_APP=cacao_accounting
export FLASK_DEBUG=True
export FLASK_ENV=development
pip install hupper
hupper -m waitress --listen=*:8080 wsgi:app
