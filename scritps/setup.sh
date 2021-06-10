#!/bin/bash

python -m pip install -r development.txt
python -m pip install -e .
flask setupdb
yarn
