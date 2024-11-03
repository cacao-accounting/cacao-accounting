#!/bin/bash
black cacao_accounting
echo Verificando con flake8
python -m flake8 cacao_accounting/
echo
echo Linting code with ruff
echo
python -m ruff check cacao_accounting/
echo
echo Ejecutando bandit
echo
python -m bandit -r cacao_accounting/
echo
echo Testing code with pytest
echo
echo
CACAO_TEST=True LOGURU_LEVEL=WARNING SECRET_KEY=ASD123kljaAddS python -m pytest  -v -s --exitfirst --slow=True
