#!/bin/bash
echo Formating Code with Black
echo
black cacao_accounting/
echo
echo Linting code with ruff
echo
python -m ruff check cacao_accounting/
echo
echo Testing code with pytest
echo
echo
CACAO_TEST=True python -m pytest  -v -s --exitfirst --slow=True --cov=cacao_accounting --cov-append tests/test_00basicos.py
CACAO_TEST=True python -m pytest  -v -s --exitfirst --slow=True --cov=cacao_accounting --cov-append tests/test_01forms.py
CACAO_TEST=True python -m pytest  -v -s --exitfirst --slow=True --cov=cacao_accounting --cov-append tests/test_02vistas.py
CACAO_TEST=True python -m pytest  -v -s --exitfirst --slow=True --cov=cacao_accounting --cov-append tests/test_03webactions.py
