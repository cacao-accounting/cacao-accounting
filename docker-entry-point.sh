#!/bin/sh

set -e

exec /usr/bin/python3.12 -m cacao_accounting "$@"
