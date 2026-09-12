#!/usr/bin/env bash
# Actualiza los catalogos de traduccion de cacao-accounting.
#
# Flujo (sigue AGENTS.md):
#  1. Extrae las cadenas marcadas para traduccion desde el paquete
#     cacao_accounting hacia messages.pot.
#  2. Fusiona el .pot con los catalogos existentes en
#     cacao_accounting/translations/<locale>/LC_MESSAGES/messages.po.
#  3. Compila los .po a .mo que Flask-Babel carga en tiempo de ejecucion.
#
# Se usa -k _l ademas de los keywords por defecto porque el proyecto usa
# _l (alias de lazy_gettext) en formularios y modelos; sin el, esas cadenas
# no se extraen.
#
# Uso:
#   ./scripts/update_translations.sh
#   ./scripts/update_translations.sh --compile-only
#
# Nota: pybabel update normaliza el formato del .po (reordena por ubicacion y
# reajusta el wrapping). Es esperado; revisa el diff antes de confirmar.
#
# Exit code: 0 si todo el flujo termino correctamente.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRANSLATIONS_DIR="$PROJECT_ROOT/cacao_accounting/translations"
DOMAIN="messages"
POT_FILE="$PROJECT_ROOT/messages.pot"
BABEL_CFG="$PROJECT_ROOT/babel.cfg"

compile_only=false
for argument in "$@"; do
    case "$argument" in
        --compile-only)
            compile_only=true
            ;;
        *)
            echo "Uso: $0 [--compile-only]" >&2
            exit 2
            ;;
    esac
done

# Resolver un Python con pybabel. Se reconoce .venv/venv (Scripts/ para
# Windows y bin/ para Linux/macOS) y como ultimo recurso un python del PATH.
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
        "$candidate" -c "import babel" >/dev/null 2>&1; then
        PYTHON="$candidate"
        break
    fi
done

if [[ -z "${PYTHON:-}" ]]; then
    echo "ERROR: no se encontro un Python con Babel. Verifica el virtualenv en .venv/venv o la variable PYTHON_VENV." >&2
    exit 2
fi

echo "Usando Python: $PYTHON"

if [[ "$compile_only" == false ]]; then
    echo "== 1/3 Extrayendo cadenas a $POT_FILE =="
    "$PYTHON" -m babel.messages.frontend extract \
        -F "$BABEL_CFG" -k _l -o "$POT_FILE" \
        "$PROJECT_ROOT/cacao_accounting"

    echo "== 2/3 Fusionando $POT_FILE con los catalogos =="
    "$PYTHON" -m babel.messages.frontend update \
        -i "$POT_FILE" -d "$TRANSLATIONS_DIR" -D "$DOMAIN"
fi

echo "== 3/3 Compilando catalogos =="
"$PYTHON" -m babel.messages.frontend compile \
    -d "$TRANSLATIONS_DIR" -D "$DOMAIN" -f

echo "Listo: catalogos actualizados en $TRANSLATIONS_DIR"
