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

"""Administración de Registro de Entidades."""

from cacao_accounting.registro import Registro


class RegistroEntidad(Registro):
    """
    Registro base para controlar la logica de negocios de una entidad.

    Una entidad es la base contra la que se realizan las transacciones en el
    sistema.
    """

    def __init__(self):
        """Administración de entidades."""
        from cacao_accounting.database import Entidad

        self.tabla = Entidad
