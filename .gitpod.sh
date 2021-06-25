#!/bin/bash
git config pull.rebase true
/home/gitpod/.pyenv/versions/3.8.10/bin/python -m pip install --upgrade pip
/home/gitpod/.pyenv/versions/3.8.10/bin/python -m pip install --upgrade pip
/home/gitpod/.pyenv/versions/3.8.10/bin/python -m pip install -r development.txt
/home/gitpod/.pyenv/versions/3.8.10/bin/python -m pip install -e .
/home/gitpod/.pyenv/versions/3.8.10/bin/python setup.py develop
/home/gitpod/.pyenv/versions/3.8.10/bin/python -m flask setupdb
yarn
export CACAO_TEST=True
export FLASK_APP=cacao_accounting
export FLASK_DEBUG=True
export FLASK_ENV=development
$CACAO_TEST
$FLASK_DEBUG