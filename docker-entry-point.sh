#!/bin/sh

set -e

/usr/bin/caddy start --config /etc/caddy/Caddyfile --adapter caddyfile

# Inicializa la base de datos si no existe (idempotente).
python -c "from cacao_accounting import command; command()" db init || true

# Aplica migraciones pendientes (idempotente).
python -c "from cacao_accounting import command; command()" db migrate || true

exec /usr/bin/python3.12 /app/run.py
