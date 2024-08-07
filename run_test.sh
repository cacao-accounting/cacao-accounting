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
CACAO_TEST=True LOGURU_LEVEL=WARNING python -m pytest  -v -s --exitfirst --slow=True --cov=cacao_accounting tests/test_basicos.py
CACAO_TEST=True LOGURU_LEVEL=WARNING python -m pytest  -v -s --exitfirst --slow=True --cov=cacao_accounting tests/test_forms.py
CACAO_TEST=True LOGURU_LEVEL=WARNING python -m pytest  -v -s --exitfirst --slow=True --cov=cacao_accounting tests/test_vistas.py
CACAO_TEST=True LOGURU_LEVEL=WARNING python -m pytest  -v -s --exitfirst --slow=True --cov=cacao_accounting tests/test_webactions.py
