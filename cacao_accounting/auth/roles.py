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

"""Definicion de Roles para regular el acceso al sistema de los usuarios."""

from cacao_accounting.loggin import log
from cacao_accounting.transaccion import Transaccion
from cacao_accounting.registro import Registro


class RegistroRol(Registro):
    """Adminisración de Roles de Usuario."""

    def __init__(self):
        """Adminisración de Roles de Usuario."""
        from cacao_accounting.database import Roles

        self.tabla = Roles


class RegistroRolUsuario(Registro):
    """Administración de roles de usuario."""

    def __init__(self) -> None:
        """Administración de roles de usuario."""
        from cacao_accounting.database import RolesUsuario

        self.tabla = RolesUsuario  # type: ignore[assignment]


ADMINISTRADOR = {
    "name": "admin",
    "detalle": "Administrador del Sistema",
}

COMPRAS_SENIOR = {
    "name": "purchasing_manager",
    "detalle": "Jefe de Compras",
}

COMPRAS_JUNIOR = {
    "name": "purchasing_auxiliar",
    "detalle": "Auxiliar de Compras",
}

COMPRAS_USER = {
    "name": "purchasing_user",
    "detalle": "Usuario de Compras",
}

INVENTARIO_SENIOR = {
    "name": "inventory_manager",
    "detalle": "Jefe de Inventarios",
}

INVENTARIO_JUNIOR = {
    "name": "inventory_auxiliar",
    "detalle": "Auxiliar de Inventarios",
}

INVENTARIO_USER = {
    "name": "inventory_user",
    "detalle": "Usuario de Inventarios",
}

VENTAS_SENIOR = {
    "name": "sales_manager",
    "detalle": "Jefe de Ventas",
}

VENTAS_JUNIOR = {
    "name": "sales_auxiliar",
    "detalle": "Auxiliar de Ventas",
}

VENTAS_USER = {
    "name": "sales_user",
    "detalle": "Usuario de Ventas",
}

TESORERIA_SENIOR = {
    "name": "head_of_treasury",
    "detalle": "Jefe de tesoreria",
}


TESORERIA_JUNIOR = {
    "name": "auxiliar_of_treasury",
    "detalle": "Auxiliar de tesoreria",
}

TESORERIA_USER = {
    "name": "user_of_treasury",
    "detalle": "Usario de tesoreria",
}

CONTABILIDAD_SENIOR = {
    "name": "accounting_manager",
    "detalle": "Jefe de Contabilidad",
}

CONTABILIDAD_JUNIOR = {
    "name": "accounting_auxiliar",
    "detalle": "Auxiliar de Contabilidad",
}

CONTABILIDAD_USER = {
    "name": "accounting_user",
    "detalle": "Usuario de Contabilidad",
}

COMPTROLLER = {
    "name": "comptroller",
    "detalle": "Auditor Interno",
}

BUSINESS_ANALYST = {
    "name": "business_analyst",
    "detalle": "Analista de Negocios",
}


ROLES_PREDETERMINADOS = [
    ADMINISTRADOR,
    COMPRAS_SENIOR,
    COMPRAS_JUNIOR,
    COMPRAS_USER,
    CONTABILIDAD_SENIOR,
    CONTABILIDAD_JUNIOR,
    CONTABILIDAD_USER,
    INVENTARIO_SENIOR,
    INVENTARIO_JUNIOR,
    INVENTARIO_USER,
    TESORERIA_SENIOR,
    TESORERIA_JUNIOR,
    TESORERIA_USER,
    VENTAS_SENIOR,
    VENTAS_JUNIOR,
    VENTAS_USER,
    COMPTROLLER,
    BUSINESS_ANALYST,
]


def crea_roles_predeterminados() -> None:
    """Carga roles predeterminados a la base de datos."""
    log.debug("Iniciando creacion de Roles predeterminados.")
    for ROL in ROLES_PREDETERMINADOS:
        REGISTRO = RegistroRol()
        REGISTRO.ejecutar_transaccion(
            Transaccion(
                registro="Rol",
                tipo="principal",
                estatus_actual=None,
                nuevo_estatus=None,
                uuid=None,
                accion="crear",
                datos=ROL,
                datos_detalle=None,
                relaciones=None,
                relacion_id=None,
            )
        )


def asigna_rol_a_usuario(usuario: str, rol: str) -> None:
    """Asigna un rol determinado al usuario establecido."""
    from cacao_accounting.database import Usuario, Roles

    USUARIO = Usuario.query.filter_by(usuario=usuario).first()
    ROL = Roles.query.filter_by(name=rol).first()
    ROL_USUARIO = RegistroRolUsuario()
    ROL_USUARIO.ejecutar_transaccion(
        Transaccion(
            registro="Rol Usuario",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={"user_id": USUARIO.id, "role_id": ROL.id},
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )


def obtener_roles_por_usuario(usuario: str) -> tuple:
    """Obtiene los roles de usuario de la base de datos."""
    from cacao_accounting.database import database, Usuario, RolesUsuario, Roles

    USUARIO = Usuario.query.filter_by(usuario=usuario).first()
    ROLES_DE_USUARIO = (
        # pylint: disable=E1101
        database.session.query(RolesUsuario, Roles, Usuario)
        .join(Roles)
        .join(Usuario)
        .filter(RolesUsuario.user_id == USUARIO.id)
    )
    return ROLES_DE_USUARIO
