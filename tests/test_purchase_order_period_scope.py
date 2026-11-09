# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Alcance multi-módulo del filtro de período en órdenes de compra.

Escenario de negocio: un usuario autorizado en Compras para ``alpha`` y en
Inventario para ``beta`` debe conservar ambas compañías al filtrar por período.
El listado no puede escoger silenciosamente la compañía del primer módulo.
"""

from __future__ import annotations

from datetime import date

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    Entity,
    Modules,
    PurchaseOrder,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre

CONTRASENA = "periodo-compras-2026"
FECHA = date(2026, 10, 15)


@pytest.fixture
def ordenes_por_modulo():
    """Compras en alpha e Inventario en beta para el mismo usuario."""
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
                Modules(module="purchases", default=False, enabled=True),
                Modules(module="inventory", default=False, enabled=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Entity(
                    code="beta",
                    name="Beta",
                    company_name="Beta SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                User(
                    id="mixto",
                    user="mixto",
                    name="Usuario Mixto",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
                UserCompanyAccess(user_id="mixto", company_code="alpha"),
                UserCompanyAccess(user_id="mixto", company_code="beta"),
                AccountingPeriod(
                    entity="alpha",
                    name="2026-10",
                    start=date(2026, 10, 1),
                    end=date(2026, 10, 31),
                    enabled=True,
                    is_closed=False,
                ),
                AccountingPeriod(
                    entity="beta",
                    name="2026-10",
                    start=date(2026, 10, 1),
                    end=date(2026, 10, 31),
                    enabled=True,
                    is_closed=False,
                ),
                PurchaseOrder(
                    company="alpha",
                    posting_date=FECHA,
                    docstatus=1,
                    document_no="PO-ALPHA",
                    supplier_name="Proveedor Alpha",
                ),
                PurchaseOrder(
                    company="beta",
                    posting_date=FECHA,
                    docstatus=1,
                    document_no="PO-BETA",
                    supplier_name="Proveedor Beta",
                ),
            ]
        )
        database.session.flush()
        rol_compras = Roles(name="compras_alpha", note="Compras alpha")
        rol_inventario = Roles(name="inventario_beta", note="Inventario beta")
        database.session.add_all([rol_compras, rol_inventario])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(
                    rol_id=rol_compras.id,
                    module_id=obtener_id_modulo_por_nombre("purchases"),
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
                    rol_id=rol_inventario.id,
                    module_id=obtener_id_modulo_por_nombre("inventory"),
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
                RolesUser(user_id="mixto", role_id=rol_compras.id, active=True),
                RolesUser(user_id="mixto", role_id=rol_inventario.id, active=True),
            ]
        )
        database.session.commit()
        periods = {row.entity: row.id for row in database.session.execute(database.select(AccountingPeriod)).scalars()}
    yield application, periods
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client) -> None:
    response = client.post("/login", data={"usuario": "mixto", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def test_listado_conserva_ambas_companias_sin_filtro(ordenes_por_modulo):
    """El selector y la consulta incluyen Compras e Inventario."""
    application, _ = ordenes_por_modulo
    client = application.test_client()
    _iniciar(client)

    response = client.get("/buying/purchase-order/list")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "PO-ALPHA" in cuerpo
    assert "PO-BETA" in cuerpo
    assert "list-company" in cuerpo


def test_selector_une_companias_de_ambos_modulos(ordenes_por_modulo):
    """El selector conserva la unión de compañías de Compras e Inventario."""
    application, _ = ordenes_por_modulo
    from flask_login import current_user, login_user

    from cacao_accounting.database import User
    from cacao_accounting.list_filters import company_choices_for_modules

    with application.test_request_context("/buying/purchase-order/list"):
        login_user(database.session.get(User, "mixto"))
        choices = company_choices_for_modules(("purchases", "inventory"), current_user=current_user)

    assert {code for code, _ in choices} == {"", "alpha", "beta"}


def test_filtro_de_periodo_exige_compania_si_el_alcance_es_ambiguo(ordenes_por_modulo):
    """Con dos compañías autorizadas no se escoge la del primer módulo."""
    application, periods = ordenes_por_modulo
    client = application.test_client()
    _iniciar(client)

    response = client.get(
        "/buying/purchase-order/list",
        query_string={
            "accounting_period_from": periods["alpha"],
            "accounting_period_to": periods["alpha"],
        },
    )

    assert response.status_code == 400


def test_filtro_de_periodo_respeta_la_compania_de_inventario(ordenes_por_modulo):
    """Con compañía explícita, beta sigue visible por el alcance de Inventario."""
    application, periods = ordenes_por_modulo
    client = application.test_client()
    _iniciar(client)

    response = client.get(
        "/buying/purchase-order/list",
        query_string={
            "company": "beta",
            "accounting_period_from": periods["beta"],
            "accounting_period_to": periods["beta"],
        },
    )

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "PO-BETA" in cuerpo
    assert "PO-ALPHA" not in cuerpo
