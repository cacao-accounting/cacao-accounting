# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes
"""El KPI de comprobantes pendientes exige permiso de consulta de caja (#2072).

Escenario de negocio: el dashboard ejecutivo expone ``pending_vouchers``
(comprobantes de pago en borrador) dentro de la sección contable. Ese KPI solo
debe computarse para usuarios con permiso de consulta del módulo de caja; sin
ese permiso la respuesta omite el KPI aunque la sección contable siga siendo
visible.
"""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.database import (
    PaymentEntry,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre


def _crear_pagos_borrador(app, cantidad: int) -> list[str]:
    """Crea comprobantes de pago en borrador (docstatus=0) con numeración única."""
    sufijo = uuid4().hex[:8]
    with app.app_context():
        identificadores = []
        for indice in range(cantidad):
            pago = PaymentEntry(
                payment_type="pay",
                company="cacao",
                document_no=f"PV-{sufijo}-{indice}",
                docstatus=0,
            )
            database.session.add(pago)
            database.session.flush()
            identificadores.append(pago.id)
        database.session.commit()
        return identificadores


def _crear_usuario_solo_contabilidad(app) -> str:
    """Crea un usuario con acceso de consulta a contabilidad pero sin permiso de caja."""
    sufijo = uuid4().hex[:8]
    with app.app_context():
        usuario = User(
            id=f"usr-{uuid4().hex[:21]}",
            user=f"soloconta{sufijo}",
            name="Solo Contabilidad",
            password=b"x",
            active=True,
            classification="user",
        )
        rol = Roles(name=f"contador {sufijo}", note="rol con consulta de contabilidad únicamente")
        database.session.add_all([usuario, rol])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(
                    rol_id=rol.id,
                    module_id=obtener_id_modulo_por_nombre("accounting"),
                    access=True,
                    view=True,
                ),
                RolesUser(user_id=usuario.id, role_id=rol.id, active=True),
                UserCompanyAccess(user_id=usuario.id, company_code="cacao"),
            ]
        )
        database.session.commit()
        return usuario.id


def _cliente_como(app, user_id: str):
    """Devuelve un cliente HTTP autenticado con el usuario indicado."""
    cliente = app.test_client()
    with cliente.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    return cliente


def test_usuario_con_permiso_caja_recibe_pending_vouchers(app, authenticated_client):
    """El administrador ve el conteo de comprobantes en borrador en la sección contable."""
    _crear_pagos_borrador(app, 2)

    respuesta = authenticated_client().get("/api/dashboard/data?company=cacao")

    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    contabilidad = datos["sections"]["accounting"]
    assert contabilidad["visible"] is True
    kpis = contabilidad["kpis"]
    assert "pending_vouchers" in kpis
    assert kpis["pending_vouchers"]["format"] == "count"
    assert kpis["pending_vouchers"]["value"] >= 2
