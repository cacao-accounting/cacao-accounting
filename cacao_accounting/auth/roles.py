# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Definicion de Roles para regular el acceso al sistema de los usuarios."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from collections.abc import Iterable

from cacao_accounting.logs import log


from cacao_accounting.i18n import _

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

CUSTOMER = {
    "name": "customer",
    "detalle": "Portal de Cliente",
}

SUPPLIER = {
    "name": "supplier",
    "detalle": "Portal de Proveedor",
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
    CUSTOMER,
    SUPPLIER,
]


def tiene_rol(user_id: str, role_name: str) -> bool:
    """Verifica si un usuario tiene un rol determinado."""
    from cacao_accounting.database import Roles, RolesUser, database

    res = database.session.execute(
        database.select(RolesUser.id)
        .join(Roles, Roles.id == RolesUser.role_id)
        .filter(RolesUser.user_id == user_id, Roles.name == role_name, RolesUser.active.is_(True))
    ).scalar_one_or_none()
    return res is not None


def crea_roles_predeterminados() -> None:
    """Carga roles predeterminados sin duplicar nombres existentes."""
    log.debug("Creando Roles Predeterminados.")
    from cacao_accounting.database import Roles, database

    existing_names = {name for (name,) in database.session.execute(database.select(Roles.name)).all()}
    for r in ROLES_PREDETERMINADOS:
        if r.get("name") in existing_names:
            continue
        rol = Roles(name=r.get("name"), note=r.get("detalle"))
        database.session.add(rol)
        existing_names.add(r.get("name"))
    database.session.commit()


def asigna_rol_a_usuario(usuario: str, rol: str) -> None:
    """Asigna un rol determinado al usuario establecido."""
    from cacao_accounting.database import Roles, RolesUser, User, database

    USUARIO = database.session.execute(database.select(User).filter_by(user=usuario)).scalar_one_or_none()
    ROL = database.session.execute(database.select(Roles).filter_by(name=rol)).scalar_one_or_none()

    if USUARIO is None or ROL is None:
        raise ValueError(_("Usuario o rol no encontrado"))

    existing_assignment = database.session.execute(
        database.select(RolesUser).filter_by(user_id=USUARIO.id, role_id=ROL.id)
    ).scalar_one_or_none()
    if existing_assignment is not None:
        if existing_assignment.active is True:
            return
        existing_assignment.active = True
        database.session.commit()
        return

    rol = RolesUser(user_id=USUARIO.id, role_id=ROL.id, active=True)

    database.session.add(rol)
    database.session.commit()


def replace_user_roles(user_id: str, role_ids: Iterable[str] | None) -> None:
    """Reemplaza las asignaciones de un usuario sin borrar evidencia.

    La fila del usuario se bloquea antes de leer las asignaciones, de modo que
    dos administradores concurrentes no mezclan sus selecciones. Los roles
    retirados quedan con ``active=False`` y se conserva la fila (#1682, #2006).
    """
    from cacao_accounting.database import Roles, RolesUser, User, database

    selected = {str(role_id) for role_id in (role_ids or []) if role_id}
    if database.engine.dialect.name == "sqlite":
        connection = database.session.connection()
        raw_connection = connection.connection.driver_connection
        if raw_connection is not None and not raw_connection.in_transaction:
            connection.exec_driver_sql("BEGIN IMMEDIATE")

    locked = database.session.execute(
        database.select(User.id).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if locked is None:
        raise ValueError(_("Usuario no encontrado."))

    if selected:
        existing_role_ids = set(database.session.execute(database.select(Roles.id).where(Roles.id.in_(selected))).scalars())
        if existing_role_ids != selected:
            raise ValueError(_("Uno de los roles seleccionados no existe."))

    assignments = list(
        database.session.execute(
            database.select(RolesUser).filter_by(user_id=user_id).execution_options(populate_existing=True)
        ).scalars()
    )
    by_role = {assignment.role_id: assignment for assignment in assignments}
    for role_id, assignment in by_role.items():
        assignment.active = role_id in selected
    for role_id in selected.difference(by_role):
        database.session.add(RolesUser(user_id=user_id, role_id=role_id, active=True))
    database.session.flush()


def obtener_roles_por_usuario(usuario: str):
    """Obtiene los roles de usuario de la base de datos."""
    from cacao_accounting.database import Roles, RolesUser, User, database

    USUARIO = User.query.filter_by(user=usuario).first()
    if USUARIO is None:
        return []

    ROLES_DE_USUARIO = (
        database.session.query(RolesUser, Roles, User).join(Roles).join(User).filter(RolesUser.user_id == USUARIO.id)
    )
    return ROLES_DE_USUARIO
