#!/bin/bash

echo "Black"
black cacao_accounting
echo "Flake8"
flake8 cacao_accounting
echo "Mypy"
mypy cacao_accounting
echo "Pylint"
pylint cacao_accounting