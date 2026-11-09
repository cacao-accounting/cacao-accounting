# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El dashboard no filtra pagos pendientes sin permiso de Caja.

Escenario de negocio: un contador puede ver la sección de Contabilidad, pero no
debe inferir cuántos pagos pendientes existen si no tiene acceso al módulo de
Caja. El KPI se calcula solo para usuarios autorizados.
"""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Entity,
    Modules,
    PaymentEntry,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre

CONTRASENA = "dashboard-pagos-2026"
FECHA = date(2026, 10, 20)


@pytest.fixture
def dashboard_pagos():
    """Contador sin Caja y tesorero con ambos módulos."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="accounting", default=False, enabled=True),
                Modules(module="cash", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="contador",
                    name="Contador",
                    user="contador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                User(
                    id="tesorero",
                    name="Tesorero",
                    user="tesorero",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                UserCompanyAccess(user_id="contador", company_code="cacao"),
                UserCompanyAccess(user_id="tesorero", company_code="cacao"),
                PaymentEntry(
                    company="cacao",
                    payment_type="pay",
                    posting_date=FECHA,
                    docstatus=0,
                ),
            ]
        )
        database.session.flush()
        rol_contador = Roles(name="solo_contabilidad", note="Contabilidad sin caja")
        rol_tesorero = Roles(name="contabilidad_y_caja", note="Contabilidad y caja")
        database.session.add_all([rol_contador, rol_tesorero])
        database.session.flush()
        accounting_id = obtener_id_modulo_por_nombre("accounting")
        cash_id = obtener_id_modulo_por_nombre("cash")
        database.session.add_all(
            [
                RolesAccess(
                    rol_id=rol_contador.id,
                    module_id=accounting_id,
                    access=True,
                    update=False,
                    set_null=False,
                    approve=False,
                    bi=False,
                    close=False,
                    setup=False,
                    view=True,
                    create=False,
                    edit=False,
                    delete=False,
                    import_=False,
                    report=False,
                    request=False,
                    validate=False,
                ),
                RolesAccess(
                    rol_id=rol_tesorero.id,
                    module_id=accounting_id,
                    access=True,
                    update=False,
                    set_null=False,
                    approve=False,
                    bi=False,
                    close=False,
                    setup=False,
                    view=True,
                    create=False,
                    edit=False,
                    delete=False,
                    import_=False,
                    report=False,
                    request=False,
                    validate=False,
                ),
                RolesAccess(
                    rol_id=rol_tesorero.id,
                    module_id=cash_id,
                    access=True,
                    update=False,
                    set_null=False,
                    approve=False,
                    bi=False,
                    close=False,
                    setup=False,
                    view=True,
                    create=False,
                    edit=False,
                    delete=False,
                    import_=False,
                    report=False,
                    request=False,
                    validate=False,
                ),
                RolesUser(user_id="contador", role_id=rol_contador.id, active=True),
                RolesUser(user_id="tesorero", role_id=rol_tesorero.id, active=True),
            ]
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client, usuario: str) -> None:
    response = client.post("/login", data={"usuario": usuario, "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def test_contador_no_infiere_pagos_sin_permiso_de_caja(dashboard_pagos):
    """La sección contable no expone el KPI de pagos sin acceso a Caja."""
    client = dashboard_pagos.test_client()
    _iniciar(client, "contador")

    response = client.get("/api/dashboard/data?company=cacao")

    assert response.status_code == 200
    accounting = response.get_json()["sections"]["accounting"]
    assert accounting["visible"] is True
    assert "pending_vouchers" not in accounting["kpis"]


def test_tesorero_ve_pagos_pendientes_con_permiso_de_caja(dashboard_pagos):
    """Control positivo: con acceso a Caja el KPI se calcula."""
    client = dashboard_pagos.test_client()
    _iniciar(client, "tesorero")

    response = client.get("/api/dashboard/data?company=cacao")

    assert response.status_code == 200
    sections = response.get_json()["sections"]
    assert sections["accounting"]["kpis"]["pending_vouchers"]["value"] == 1
    assert sections["banks"]["visible"] is True
