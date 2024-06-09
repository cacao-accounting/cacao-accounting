#!/bin/bash
python -m ruff check cacao_accounting/
python -m pytest  -v --exitfirst --slow=True --cov=cacao_accounting
