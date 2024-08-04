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
rm *.db
CACAO_TEST=True python -m pytest  -v -s --exitfirst --slow=True --cov=cacao_accounting
