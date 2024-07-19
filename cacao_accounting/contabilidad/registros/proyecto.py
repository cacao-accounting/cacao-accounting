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

"""Administración de registro de proyectos."""

from cacao_accounting.registro import Registro


class RegistroProyecto(Registro):
    """Registro para manejar los proyetos."""

    def __init__(self):
        """Registro para la administración de Proyectos."""
        from cacao_accounting.database import Proyecto

        self.tabla = Proyecto
