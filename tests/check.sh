#! /usr/bin/bash

black cacao_accounting
flake8 cacao_accounting
pytest
pydocstyle cacao_accounting