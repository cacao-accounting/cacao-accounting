#!/bin/sh

set -e

/usr/bin/caddy start --config /etc/caddy/Caddyfile --adapter caddyfile

# Inicializa o repara la base de datos hasta que exista la tabla user y un
# usuario inicial. Los fallos deben detener el contenedor.
python -c "from cacao_accounting import command; command()" db init

# Aplica migraciones pendientes (idempotente).
python -c "from cacao_accounting import command; command()" db migrate

exec /usr/bin/python3.12 /app/run.py
