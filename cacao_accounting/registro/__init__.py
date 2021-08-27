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

# pylint: disable=no-member

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
from typing import Union
from flask_login import current_user
from cacao_accounting.database import database
from cacao_accounting.exceptions import OperationalError, TransactionError
from cacao_accounting.exceptions.mensajes import ERROR3, ERROR4
from cacao_accounting.transaccion import Transaccion
from cacao_accounting.validaciones import VALIDACIONES_PREDETERMINADAS


class Registro:
    """
    Define la clase principal para administrar registros en la base de datos.

    Las transacciones ejecutadas por los usuarios deben tener acceso en la base de datos, esta interfaz ofrece
    una sere de metodos unificada para qe las transacciones modifiquen el estado de la base de datos.
    """

    DATABASE = database
    tabla = None
    tabla_detalle = None
    LISTA_DE_VALIDACIONES_DE_TRANSACCION = VALIDACIONES_PREDETERMINADAS

    def _ejecutar_transaccion_por_tipo(self, transaccion: Transaccion):
        if transaccion.accion == "crear":
            return self._crear_transaccion_principal_en_la_db(transaccion)
        elif (
            transaccion.accion == "actualizar"
            and transaccion.tipo == "principal"
            and transaccion.nuevo_estatus == "predeterminado"
        ):
            return self._estable_registro_maestro_como_predeterminado(transaccion)
        elif transaccion.accion == "eliminar" and transaccion.tipo == "principal":
            return self._elimar_registro_principal(transaccion)
        elif transaccion.accion == "actualizar" and transaccion.nuevo_estatus:
            return self._ejecuta_cambio_de_estatus(transaccion)
        else:
            raise TransactionError(ERROR4)

    def _ejecutar_validacion_de_transaccion(self, transaccion: Transaccion):
        for validacion in self.LISTA_DE_VALIDACIONES_DE_TRANSACCION:
            validacion(transaccion)

    def _crear_transaccion_principal_en_la_db(self, transaccion: Transaccion):
        if self.tabla:
            if current_user:
                transaccion.datos["creado_por"] = current_user.usuario
            self.DATABASE.session.add(self.tabla(**transaccion.datos))
            self.DATABASE.session.commit()
            return True
        else:
            return False

    def _ejecuta_cambio_de_estatus(self, transaccion: Transaccion) -> bool:
        if self.tabla:
            transaccion.datos.status = transaccion.nuevo_estatus
            database.session.add(transaccion.datos)
            database.session.commit()
            return True
        else:
            raise TransactionError(ERROR3)

    def _estable_registro_maestro_como_predeterminado(self, transaccion: Transaccion) -> bool:
        if self.tabla:
            # Solo puede haber un registro predeterminado, en caso de haber un registro, o mas,
            # establecidos como predeterminados establecerlos como activos.
            registros = self.tabla.query.filter_by(status="predeterminado")
            for registro in registros:
                registro.status = "activo"
                database.session.add(registro)
                database.session.commit()
            transaccion.datos.status = "predeterminado"
            database.session.add(transaccion.datos)
            database.session.commit()
            return True
        else:
            raise OperationalError(ERROR3)

    def _elimar_registro_principal(self, transaccion: Transaccion) -> bool:
        """
        Elimina una transacción de la base de datos.

        Eliminar un registro solo puede ser realizado por un usuario administrador, normalmente
        un usuario de sistema se limita a cancelar o anular una operacion.
        """
        if self.tabla:
            REGISTRO_A_ELIMINAR = self.tabla.query.filter_by(id=transaccion.uuid).one()
            database.session.delete(REGISTRO_A_ELIMINAR)
            database.session.commit()
            return True
        else:
            raise TransactionError(ERROR4)

    def ejecutar_transaccion(self, transaccion: Union[Transaccion, None] = None):
        """Ejecuta una transacción en la base de datos."""
        if transaccion:
            self._ejecutar_validacion_de_transaccion(transaccion)
            self._ejecutar_transaccion_por_tipo(transaccion)
