#!/bin/sh

set -e

/usr/bin/caddy start --config /etc/caddy/Caddyfile --adapter caddyfile

exec /usr/bin/python3.12 /app/run.py
