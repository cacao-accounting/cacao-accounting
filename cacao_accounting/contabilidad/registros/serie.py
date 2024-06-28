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

"""Administración de Registro de Series."""

from cacao_accounting.registro import Registro


class RegistroSerie(Registro):
    """
    Registro base para controlar diferentes numeros de serie.

    Los números de seríe permiten llevar control del ingreso de las transacciones.
    """

    def __init__(self):
        """Administración de Series."""
        from cacao_accounting.database import Serie

        self.tabla = Serie
