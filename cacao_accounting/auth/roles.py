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
Definicion de Roles para regular el acceso al sistema de los usuarios.
"""

from cacao_accounting.loggin import log
from cacao_accounting.transaccion import Transaccion
from cacao_accounting.registro import Registro


class RegistroRol(Registro):
    def __init__(self):
        from cacao_accounting.database import Roles

        self.tabla = Roles


class RegistroRolUsuario(Registro):
    def __init__(self) -> None:
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

VENTAS_SENIOR = {
    "name": "sales_manager",
    "detalle": "Jefe de Ventas",
}

VENTAS_JUNIOR = {
    "name": "sales_auxiliar",
    "detalle": "Auxiliar de Ventas",
}


TESORERIA_SENIOR = {
    "name": "head_of_treasury",
    "detalle": "Jefe de tesoreria",
}


TESORERIA_JUNIOR = {
    "name": "junior_of_treasury",
    "detalle": "Auxiliar de tesoreria",
}

CONTABILIDAD_SENIOR = {
    "name": "accounting_manager",
    "detalle": "Jefe de Contabilidad",
}

CONTABILIDAD_JUNIOR = {
    "name": "accounting_auxiliar",
    "detalle": "Auxiliar de Contabilidad",
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
    INVENTARIO_SENIOR,
    INVENTARIO_JUNIOR,
    TESORERIA_SENIOR,
    TESORERIA_JUNIOR,
    VENTAS_SENIOR,
    VENTAS_JUNIOR,
    COMPTROLLER,
    BUSINESS_ANALYST,
]


def crea_roles_predeterminados() -> None:
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
    from cacao_accounting.database import db, Usuario, RolesUsuario, Roles

    USUARIO = Usuario.query.filter_by(usuario=usuario).first()
    ROLES_DE_USUARIO = (
        db.session.query(RolesUsuario, Roles, Usuario).join(Roles).join(Usuario).filter(RolesUsuario.user_id == USUARIO.id)
    )
    return ROLES_DE_USUARIO
