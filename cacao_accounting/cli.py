# Copyright 2020 William José Moreno Reyes
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Contributors:
# - William José Moreno Reyes

# Fuente: https://github.com/pallets/flask/blob/master/src/flask/cli.py

"""Interfaz de linea de comandos."""

import sys
from flask.cli import FlaskGroup

LINEA_COMANDOS = FlaskGroup(
    help="""\
Interfaz de linea de comandos para la administración de Cacao Accounting.
"""
)


def linea_comandos(as_module=False):
    """Linea de comandos para administración de la aplicacion."""
    LINEA_COMANDOS.main(args=sys.argv[1:], prog_name="python -m flask" if as_module else None)
