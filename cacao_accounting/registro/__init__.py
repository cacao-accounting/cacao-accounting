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

"""Registro."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# ---------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask_login import current_user

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.database import database
from cacao_accounting.modulos import mapping_documentos_a_tablas

DOC_MAPPING = mapping_documentos_a_tablas()


class Registro:
    """Definición de un registro en el sistema."""

    def __init__(self, tipo=None, nuevo=None, id=None, serie=None, data=None, detalle=None, **kwargs):

        self.tipo = DOC_MAPPING.get(tipo)
        self.nuevo = nuevo

        if self.nuevo:
            self.id = None
            self.serie = serie
            self.data = data
            self.detalle = detalle
            # Usuario actual como creador del registro.
            self.data["creado_por"] = current_user.usuario
        else:
            self.id = id
            self.data = self.obtener_datos_por_id()
            self.detalle = self.obtener_datos_detalle()

        self.tabla = self.tipo.t_principal

        if self.tipo.requiere_detalle:
            self.tabla_detalle = self.tipo.t_principal.t_detalle
        else:
            self.tabla_detalle = None

    @classmethod
    def __init_subclass__(cls, tipo=None, nuevo=None, id=None, serie=None, data=None, detalle=None, **kwargs) -> None:
        super().__init_subclass__(**kwargs)

    @classmethod
    def obtener_datos_por_id(self):
        """Información principal del registro."""
        pass

    @classmethod
    def obtener_datos_detalle(self):
        """Información detalla del registro."""
        pass

    @classmethod
    def obtener_nuevo_id(self):
        """Nuevo ID."""
        pass

    @classmethod
    def crear_grabar_registro(self):
        """Crea una nueva transacción en la tabla."""
        pass

    @classmethod
    def ejecutar_transaccion(self):
        """Persiste los datos en la base de datos."""
        database.session.add(self.tabla(**self.data))
        if self.detalle:
            order = 0
            for i in self.detalle:
                order += 1
                i["idx"] = order
                database.session.add(self.tabla_detalle(*i))

        database.session.commit()
