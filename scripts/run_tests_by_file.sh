#!/bin/bash
# Ejecuta la suite de pruebas de cacao-accounting test file por test file.
#
# Sigue los lineamientos de AGENTS.md:
#  - No ejecutar toda la suite en una sola corrida.
#  - Ejecutar los tests test file por test file.
#  - Excluir tests/__init__.py y tests/conftest.py.
#  - Usar siempre .venv para ejecutar las pruebas de calidad.
#  - No esperar a tener todos los resultados antes de corregir.
#
# Uso:
#   ./scripts/run_tests_by_file.sh
#   TEST_PATTERN='test_withholding*' ./scripts/run_tests_by_file.sh
#
# Exit code: 0 si todas las pruebas pasaron, 2 si al menos una fallo.

set -u
set -o pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TESTS_DIR="$PROJECT_ROOT/tests"
# Resolver un Python con pytest. Se reconoce tanto .venv como venv (Scripts/
# para Windows y bin/ para Linux/macOS), y como ultimo recurso un python del
# PATH. Se elige el primero que tenga pytest disponible.
candidates=(
    "${PYTHON_VENV:-}"
    "$PROJECT_ROOT/.venv/Scripts/python.exe"
    "$PROJECT_ROOT/.venv/bin/python"
    "$PROJECT_ROOT/venv/Scripts/python.exe"
    "$PROJECT_ROOT/venv/bin/python"
    "python"
)

PYTHON=""
for candidate in "${candidates[@]}"; do
    [[ -z "$candidate" ]] && continue
    if { [[ "$candidate" == "python" ]] || [[ -x "$candidate" ]]; } && \
        "$candidate" -c "import pytest" >/dev/null 2>&1; then
        PYTHON="$candidate"
        break
    fi
done

if [[ -z "${PYTHON:-}" ]]; then
    echo "ERROR: no se encontro un Python con pytest. Verifica el virtualenv en .venv/venv o la variable PYTHON_VENV." >&2
    exit 2
fi

echo "Usando Python: $PYTHON"

flags=("--full" "--tb=line" "--disable-warnings" "--slow=True")
envs=(
    "CACAO_TEST=True"
    "LOGURU_LEVEL=WARNING"
    "SECRET_KEY=ASD123kljaAddS"
)

pattern="${TEST_PATTERN:-*}"

mapfile -t test_files < <(
    find "$TESTS_DIR" -maxdepth 1 -name "$pattern.py" -type f \
        ! -name '__init__.py' \
        ! -name 'conftest.py' | sort
)

if [[ "${#test_files[@]}" -eq 0 ]]; then
    echo "No se encontraron archivos de test con el patron: $pattern" >&2
    exit 2
fi

echo "==== Ejecutando ${#test_files[@]} archivos de test por archivo ===="
echo

total=0
failed=0
passed=0

for file in "${test_files[@]}"; do
    total=$((total + 1))
    rel="${file#"$PROJECT_ROOT/"}"

    echo "------------------------------------------------------------------"
    echo "[$total] $rel"
    echo "------------------------------------------------------------------"

    env "${envs[@]}" "$PYTHON" -m pytest "${flags[@]}" "$file"
    rc=$?

    if [[ $rc -eq 0 ]]; then
        passed=$((passed + 1))
        echo "OK: $rel"
    else
        failed=$((failed + 1))
        echo "FAIL (exit $rc): $rel"
    fi
    echo
done

echo "=================================================================="
echo "Resumen: $passed pasaron, $failed fallaron, $total ejecutados"
echo "=================================================================="

if [[ $failed -gt 0 ]]; then
    exit 2
fi
exit 0
