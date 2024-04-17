#!/bin/bash

python -m pip install -r development.txt
python -m pip install -e .
python -m flask setupdb
yarn
