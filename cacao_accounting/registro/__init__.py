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
from cacao_accounting.exception import ERROR1, ERROR2, ERROR3, IntegrityError, OperationalError


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

    def crear(self, datos=None, datos_detalle=None):
        """
        Utilizar este metodo para insertar registros maestros comunes a toda la instalación.
        Ejemplo:
         - Entidades
         - Proveedores
         - Clientes
        """
        if datos:
            if self.tabla:
                self.database.session.add(self.tabla(**datos))
                self.database.session.commit()
                if datos_detalle and self.tabla_detalle:
                    pass
            else:
                raise OperationalError(ERROR2)
        else:
            raise OperationalError(ERROR1)

    def crear_registro(self, datos=None, datos_detalle=None, entidad_madre=None):
        """
        Utilizar este metodo para crear registros que estan relacionados a una entidad madre, por ejemplo
         - Unidades de Negocio
         - Cuentas Contables
         - Centro de Costos
        """
        if datos and entidad_madre:
            datos["entidad"] = entidad_madre
            if self.tabla:
                self.database.session.add(self.tabla(**datos))
                self.database.session.commit()
            else:
                raise OperationalError(ERROR2)
        else:
            raise OperationalError(ERROR1)

    def cambiar_estado(self, identificador=None, status_objetivo=None):
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

    def eliminar(self, identificador=None):
        """
        Usar con precaucion, en el mayor de los casos es preferible anular que elimar, este metodo solo esta
        disponible para datos registros.
        """
        if self.tabla:
            if identificador:
                try:
                    self.tabla.query.filter(self.tabla.id == identificador).delete()
                    self.database.session.commit()
                    ELIMINADO = True
                except:  # noqa: E722
                    ELIMINADO = False
            else:
                raise IntegrityError(ERROR3)
        else:
            raise OperationalError(ERROR2)
        return ELIMINADO
