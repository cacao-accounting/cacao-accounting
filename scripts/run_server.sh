#!/usr/bin/env bash

set -euo pipefail

export CACAO_TEST="${CACAO_TEST:-True}"
export CACAO_USER="${CACAO_USER:-test}"
export CACAO_PSWD="${CACAO_PSWD:-test}"
export SECRET_KEY="${SECRET_KEY:-ASD123kljaAddS}"

# This script is intentionally destructive and is only for local/test data.
cacaoctl --env test db clean --force
cacaoctl --env test db init --seed

exec cacaoctl --env test run --host "${CACAO_HOST:-127.0.0.1}" \
    --port "${CACAO_PORT:-8080}" --debug
