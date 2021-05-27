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
# pylint: disable=not-callable
from cacao_accounting.database import db
from cacao_accounting.exception import ERROR2, ERROR3, IntegrityError, OperationalError


class Registro:
    """
    Interfaz comun para la administración de registros.

    Las relaciones entre registros son la base de la integridad de datos en el sistema.

    """

    database = db
    tabla = None
    tabla_detalle = None
    estatus = None
    validaciones = None

    def crear_registro_principal(self, datos: None):
        """
        Un registro principal no depende de otros, ejemplos de registros principales son:
         Registros maestros como:
          - Una entidad
          - Un cliente
          - Un proveedor
        Registros principales de una transaccion como:
          - Una factura
          - Un comprobante de pago
          - Un comprobante de diario
        """
        if self.tabla:
            self.database.session.add(self.tabla(**datos))
            self.database.session.commit()

    def crear_registro_secundario(self, registro_principal=None, datos_detalle=None):
        """
        Un registro secundario proporciona información adicional a un registro principal como:
          - La lista de items de una factura.
          - La lista de cuentas afectadas en un comprobantes de diario.
        """

    def cambiar_estado_registro_principal(self, identificador=None, status_actual=None, status_objetivo=None):
        """
        Actualiza el status de un registro.
        """
        if self.tabla:
            if identificador:
                registro = self.tabla.query.filter(self.tabla.id == identificador)
                registro.status = status_objetivo
                self.database.session.commit()
            else:
                raise IntegrityError(ERROR3)
        else:
            raise OperationalError(ERROR2)

    def eliminar_registros_dependientes(self, identificador=None):
        """
        Elimina un registro de la base de datos.
        """

    def eliminar_registro_principal(self, identificador=None):
        """
        Elimina un registro de la base de datos.
        """
        if self.tabla_detalle:
            self.eliminar_registros_dependientes(identificador=identificador)
        else:
            pass
