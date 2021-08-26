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

"""Administración Cuentas Contables."""

from cacao_accounting.registro import Registro


class RegistroCuentaContable(Registro):
    """Clase para administrar cuentas en el sistema."""

    def __init__(self):
        """Administración cuentas contables."""
        from cacao_accounting.database import Cuentas

        self.tabla = Cuentas
