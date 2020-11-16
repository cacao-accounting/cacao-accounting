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

"""
Base para las transacciones registradas en el sistema.

En contabilidad normalmente las transacciones registradas estas soportadas por un documento fisico
o la intención de la transacción es imprimirse para sevir de soporte para futuro o ante terceros,
por tal motivo en Cacao Accounting implementamos el concepto de REGISTRO para el ingreso de transacciones
en el sistema de.

Un registro:
 - Tiene una tabla en la base de datos para registrar las operaciones manejada por SQLAlchemy en el modelo de datos.
 - Tiene un formulario administrado por WTForms.
   - Los formularios deben tener controles y validaciones que conforman la inteligencia del negocio que aporte el sistema.
 - Tiene una vista para que el usuario interactue con el registro controlado por Flask.
   - La vista tiene tres estados:
     - Vista consulta con las datos registrados en la base de datos.
     - Vista nuevo registro mostrando el formulario en blanco.
     - Vista modificación registro mostrando los datos actuales en el sistema permitiendo al usuario cambiarlos.
 - Un registro tiene estados, estos estados van a depender del documento.
"""

from cacao_accounting.database import db


class Registros:
    """
    Interfaz comun para la administración de registros.
    Las relaciones entre registros son la base de la integridad de datos en el sistema.
    """

    database = db

    @classmethod
    def crear(tabla=None, datos=None, tabla_detalle=None, datos_detalle=None):
        """
        Utileria para uniformar la creación de transacciones en la base de datos.
        """
        pass

    @classmethod
    def eliminar(id_registro=None, tabla=None, tabla_detalle=None):
        """
        Utileria para uniformar la eliminación de transacciones en la base de datos.
        """
        pass

    @classmethod
    def actualizar(id_registro=None, tabla=None, datos=None, tabla_detalle=None, datos_detalle=None):
        """
        Utileria para uniformar la actualización de transacciones en la base de datos.
        """

    @classmethod
    def consulta_tabla(tabla=None, tabla_detalle=None):
        """
        Obtiene la lista  completa de una tabla y sus detalles.
        """
        pass

    @classmethod
    def consulta_por_id(identificador=None, tabla=None, tabla_detalle=None):
        """
        Obtiene la lista  completa de una tabla y sus detalles.
        """
        pass

    @classmethod
    def actualiza_tabla_registros(operacion=None, tipo=None, identiciador=None):
        """
        Actualiza registro consolidado de registros.
        """
        pass

    @classmethod
    def cambiar_estado(identificador=None, tabla=None):
        """
        Cambia el estado de un registro.
        """
        pass

    @classmethod
    def vincula_registros(registro1=None, registro2=None):
        pass

    @classmethod
    def desvincula_registros(registro1=None, registro2=None):
        pass
