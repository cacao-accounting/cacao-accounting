#!/bin/bash
git config pull.rebase true
python -m pip install --upgrade pip
python -m pip install -r development.txt
python -m pip install -e .
python setup.py develop
python -m flask setupdb
yarn
export CACAO_TEST=True
export FLASK_APP=cacao_accounting
export FLASK_DEBUG=True
$CACAO_TEST
$FLASK_DEBUG