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

"""Mapeo de Registros a sus tablas."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from collections import namedtuple

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.database import (
    CentroCosto,
    ComprobanteContable,
    ComprobanteContableDetalle,
    Cuentas,
    Roles,
    RolesPermisos,
    RolesUsuario,
    Serie,
    Usuario,
)

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------


# Named Tuple para almacer mapping de un registro a sus tablas relacionadas.
DOCUMENTO_TABLA = namedtuple("DOCUMENTO_TABLA", ["t_principal", "requiere_detalle", "t_detalle", "filter_by"])


# Roles y Permisos
PERMISOS_DOC = DOCUMENTO_TABLA(t_principal=RolesPermisos, requiere_detalle=None, t_detalle=None, filter_by="id")
ROL_DOC = DOCUMENTO_TABLA(t_principal=Roles, requiere_detalle=None, t_detalle=None, filter_by="id")
ROL_USUARIO_DOC = DOCUMENTO_TABLA(t_principal=RolesUsuario, requiere_detalle=None, t_detalle=None, filter_by="id")
USUARIO_DOC = DOCUMENTO_TABLA(t_principal=Usuario, requiere_detalle=None, t_detalle=None, filter_by="id")

# Maestros contables
CUENTA_DOC = DOCUMENTO_TABLA(t_principal=Cuentas, requiere_detalle=None, t_detalle=None, filter_by="codigo")
CCOSTO_DOC = DOCUMENTO_TABLA(t_principal=CentroCosto, requiere_detalle=None, t_detalle=None, filter_by="codigo")
ENTIDAD_DOC = DOCUMENTO_TABLA(t_principal=CentroCosto, requiere_detalle=None, t_detalle=None, filter_by="entidad")

# Registros Contables
JOURNAL_DOC = DOCUMENTO_TABLA(
    t_principal=ComprobanteContable,
    requiere_detalle=True,
    t_detalle=ComprobanteContableDetalle,
    filter_by="registro_id",
)
SERIE_DOC = DOCUMENTO_TABLA(t_principal=Serie, requiere_detalle=False, t_detalle=False, filter_by=id)


def mapping_documentos_a_tablas() -> dict:
    """Devuelve un mapeo de tipos de documentos y sus asociaciones con sus respectivas tablas."""

    DOC_MAPPING = {
        # Usuarios y Permisos
        "rol": ROL_DOC,
        "usuario": USUARIO_DOC,
        "rol_usuario": ROL_USUARIO_DOC,
        "permiso": PERMISOS_DOC,
        # Maestros Contabilidad
        "cuenta": CUENTA_DOC,
        "ccosto": CCOSTO_DOC,
        # Registros contables
        "journal": JOURNAL_DOC,
        "serie": SERIE_DOC,
    }

    # Fixme
    # Pendiente logica para cargar documentos de modulos adicionales

    return DOC_MAPPING
