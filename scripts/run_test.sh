#!/bin/bash
set -euo pipefail

if [[ -f "./venv/Scripts/activate" ]]; then
	source "./venv/Scripts/activate"
elif [[ -f "./.venv/Scripts/activate" ]]; then
	source "./.venv/Scripts/activate"
else
	echo "No se encontró un entorno virtual en ./venv o ./.venv"
	exit 1
fi

python -m black cacao_accounting
echo Verificando con flake8
python -m flake8 cacao_accounting/
echo
echo Linting code with ruff
echo
python -m ruff check cacao_accounting/
echo
echo Ejecutando pydocstyle
echo
python -m pydocstyle cacao_accounting/ --convention=pep257
echo
echo Testing code with pytest
echo
echo
CACAO_TEST=True LOGURU_LEVEL=WARNING SECRET_KEY=ASD123kljaAddS python -m pytest  -v -s --slow=True
echo
echo Testing code with npm
echo
echo
cd cacao_accounting/static/
npm test
