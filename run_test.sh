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
echomyp
python -m pytest  -v --exitfirst --slow=True --cov=cacao_accounting
