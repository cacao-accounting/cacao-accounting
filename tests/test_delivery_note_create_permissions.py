# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Regresión #2052: crear notas de entrega exige permisos de ventas e inventario a la vez."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from sqlalchemy import func, select

from cacao_accounting.auth import proteger_passwd
from cacao_accounting.database import (
    DeliveryNote,
    Party,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre

FECHA = date(2026, 5, 15)
CONTRASENA = "entrega-2052"
CTA_NUEVA_ENTREGA = 'href="/sales/delivery-note/new"'
TITULO_LISTADO = "Listado de Remisiones de Mercadería Vendida"


def _crear_usuario_con_permisos(entorno_contable, permisos: dict[str, set[str]]) -> str:
    """Crea un usuario con acceso a cacao y un rol dedicado con los permisos indicados.

    ``permisos`` mapea nombre de módulo al conjunto de acciones ("access", "view", "create").
    """
    with entorno_contable.app.app_context():
        usuario = User(
            user=f"entrega-{uuid4().hex[:10]}",
            name="Usuario de Entregas",
            password=proteger_passwd(CONTRASENA),
            active=True,
            company="cacao",
        )
        database.session.add(usuario)
        database.session.flush()
        database.session.add(UserCompanyAccess(user_id=usuario.id, company_code="cacao"))
        rol = Roles(name=f"rol-entrega-{uuid4().hex[:10]}", note="Rol dedicado de la prueba #2052")
        database.session.add(rol)
        database.session.flush()
        for modulo, acciones in permisos.items():
            module_id = obtener_id_modulo_por_nombre(modulo)
            assert module_id, f"El módulo {modulo} debe existir."
            database.session.add(
                RolesAccess(
                    rol_id=rol.id,
                    module_id=module_id,
                    access="access" in acciones,
                    view="view" in acciones,
                    create="create" in acciones,
                )
            )
        database.session.add(RolesUser(user_id=usuario.id, role_id=rol.id, active=True))
        database.session.commit()
        return usuario.id


def _cliente_como(app, usuario_id: str):
    """Devuelve un cliente HTTP autenticado como el usuario indicado."""
    cliente = app.test_client()
    with cliente.session_transaction() as sesion:
        sesion["_user_id"] = str(usuario_id)
        sesion["_fresh"] = True
    return cliente


def _datos_formulario(entorno_contable, marcador: str) -> dict[str, str]:
    """Construye el POST de alta de nota de entrega con una línea válida."""
    with entorno_contable.app.app_context():
        cliente_id = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one().id
    return {
        "company": "cacao",
        "currency": "NIO",
        "posting_date": FECHA.isoformat(),
        "customer_id": cliente_id,
        "remarks": marcador,
        "item_code_0": "ART01",
        "item_name_0": "Articulo Comercial",
        "qty_0": "1",
        "rate_0": "10",
        "uom_0": "UND",
        "from_warehouse": "BOD01",
    }


def _entregas_con_marcador(entorno_contable, marcador: str) -> int:
    """Cuenta notas de entrega persistidas con el marcador único de la prueba."""
    with entorno_contable.app.app_context():
        return database.session.execute(
            select(func.count()).select_from(DeliveryNote).where(DeliveryNote.remarks == marcador)
        ).scalar_one()
