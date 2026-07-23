#!/usr/bin/env bash

set -euo pipefail

script_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_directory="$(cd -- "$script_directory/.." && pwd)"

export CACAO_TEST="${CACAO_TEST:-True}"
export CACAO_USER="${CACAO_USER:-test}"
export CACAO_PSWD="${CACAO_PSWD:-test}"
export SECRET_KEY="${SECRET_KEY:-ASD123kljaAddS}"
export CACAO_DATABASE_URL="${CACAO_DATABASE_URL:-sqlite:///${project_directory}/cacaoaccounting.db}"
# The development server is HTTP by default, so browsers must send the
# session/CSRF cookie back over HTTP. HTTPS deployments keep the secure default.
export CACAO_SESSION_COOKIE_SECURE="${CACAO_SESSION_COOKIE_SECURE:-False}"
# Replit terminates HTTPS at its proxy and may expose a different backend
# host/port. The CSRF token remains enabled; only strict referrer comparison is
# disabled for this local development server.
export CACAO_CSRF_SSL_STRICT="${CACAO_CSRF_SSL_STRICT:-False}"

clean_database=false
for argument in "$@"; do
    case "$argument" in
        --clean)
            clean_database=true
            ;;
        *)
            echo "Uso: $0 [--clean]" >&2
            exit 2
            ;;
    esac
done

if [[ "$clean_database" == true ]]; then
    # This option is intentionally destructive and is only for local/test data.
    cacaoctl --env test db clean --force
fi

cacaoctl --env test db init --seed

exec cacaoctl --env test run --host "${CACAO_HOST:-127.0.0.1}" \
    --port "${CACAO_PORT:-8080}" --debug
