#!/bin/sh

set -e

/usr/bin/python3.12 -m flask setupdb
/usr/bin/python3.12 -m flask serve

