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


def comprueba_lista_validaciones(lista_a_validar: list = None) -> bool:
    """
    Para que una transacción pueda ser registrada debe pasar una serie de validaciones, las validaciones
    se deben poder espeficiar al momento de iniciar la instancia de clase.

    Las validaciones deben retornar un boleano.
    """
    VERIFICACION_TIPO_LISTA = lista_a_validar is not None and isinstance(lista_a_validar, list)
    if VERIFICACION_TIPO_LISTA:
        LISTA_EJECUTABLES = True
        while LISTA_EJECUTABLES:
            for v in lista_a_validar:  # type: ignore[union-attr]
                LISTA_EJECUTABLES = callable(v)
            break
    return VERIFICACION_TIPO_LISTA and LISTA_EJECUTABLES


class Registro:
    """
    Interfaz comun para la administración de registros.

    Las relaciones entre registros son la base de la integridad de datos en el sistema.

    """

    database = db
    tabla = None
    tabla_detalle = None
    estatus = None
    lista_validaciones = None
    validaciones_verificadas = comprueba_lista_validaciones(lista_a_validar=lista_validaciones)

    def crear_registro_maestro(self, datos: None):
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

        Por defecto los registros principales siempre deben crearse como borrador.
        """
        if self.tabla:
            self.database.session.add(self.tabla(**datos))
            self.database.session.commit()

    def elimar_registro_maestro(self, id=None):
        """
        Eliminar un registro solo puede ser realizado por un usuario administrador, normalmente
        un usuario de sistema se limita a cancelar o anular una operacion.
        """
        from sqlalchemy.exc import OperationalError

        if self.tabla:
            self.database.session.begin()
            self.database.session.query(self.tabla).filter(self.identidad == id).delete()
            try:
                self.database.session.commit()
            except OperationalError:
                self.database.session.rollback()

    def crear_registro_transaccion(self, transaccion=None, transaccion_detalle=None):
        """
        Un registro secundario proporciona información adicional a un registro principal como:
          - La lista de items de una factura.
          - La lista de cuentas afectadas en un comprobantes de diario.
        """

        if self.tabla and self.tabla_detalle:
            self.database.session.add(self.tabla(**transaccion))
            self.database.session.commit()
            for i in transaccion_detalle:
                self.database.session.add(self.tabla_detalle(**i))
                self.database.session.commit()

    def elimar_registro_transaccion(self, id=None):
        """
        Eliminar un registro solo puede ser realizado por un usuario administrador, normalmente
        un usuario de sistema se limita a cancelar o anular una operacion.
        """
        from sqlalchemy.exc import OperationalError

        if self.tabla and self.tabla_detalle:
            self.database.session.begin()
            self.database.session.query(self.tabla_detalle).filter(self.padre == id).delete()
            self.database.session.query(self.tabla).filter(self.identidad == id).delete()
            try:
                self.database.session.commit()
            except OperationalError:
                self.database.session.rollback()

    def _ejecuta_validacion_cambio_estado(self, **kwargs):
        if self.lista_validaciones and self.validaciones_verificadas and self._validaciones_predefinidas():
            TRANSACCION_VALIDADA = True
            while TRANSACCION_VALIDADA:
                for validacion in self.lista_validaciones:  # pylint: disable=E1133
                    TRANSACCION_VALIDADA = validacion(**kwargs)
                break
        else:
            # Toda transacción deberia tener al menos una validacion.
            TRANSACCION_VALIDADA = False
        return TRANSACCION_VALIDADA

    def cambiar_estado_registro_principal(self, **kwargs):
        """
        Actualiza el status de un registro.
        """
        if self._ejecuta_validacion_cambio_estado(**kwargs):
            pass
