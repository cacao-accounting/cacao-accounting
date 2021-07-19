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
Una transacción es el reflejo en el sistema de una accion realizada por un usuario, normalmente:
  - Crear: Toda transacción grabada en el sistema debe grabarse es estado borrador.
  - Actualizar: Las transacciones en estado borrador pueden ser editadas sin cambiar el estado.
  - Validar: Según el flujo de trabajo de una transacción puede requerir revisión por un usuario distinto de
    quien la genero.
  - Autorizar: Solo las transacciones autorizadas tienen efecto en los reportes.
  - Anular: Una puede ser anulada en cualquier momento sin adminitir cambios de estado posteriores.
  - Cerrar: Una transacción cerrada no puede ser vinculada a otras transacciones.
"""

from collections import namedtuple


Transaccion = namedtuple(
    "Transaccion",
    [
        # Uno de: princinpal, secundario, transaccional.
        "tipo",
        # Uno de: crear, actualizar, validar, autorizar, anular, cerrar, consultar.
        "accion",
        # Tipo de registro sobre el que se realiza la transaccion.
        "registro",
        # Estado actual de la transacción, vacio para nuevos registros.
        "estatus_actual",
        # Estatus del documento al llevar a cabo la accion ejecutada por el usuario.
        "nuevo_estatus",
        # Identificador unico en la base de datos del registro.
        "uuid",
        # Un registro puede tener otros registros relacionados en otros tablas del sistema.
        "relaciones",
        # Una cadena de texto que el usuario pueda identificar para identificar la transaccion.
        "relacion_id",
        # Un diccionario con los datos principales de la transacción.
        "datos",
        # Una lista de transacciones secundarias relacionadas al registro principal.
        "datos_detalle",
    ],
)
