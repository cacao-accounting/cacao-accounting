#!/bin/bash

echo "Verifica test"
python -m flake8 tests

echo "Pytest"
CACAO_TEST=True, CACAO_TEST_SLOW=True python -m pytest -x -v