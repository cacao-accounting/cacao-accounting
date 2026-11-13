# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Tipos y referencias de cuentas de catálogo e inventario.

Escenario de negocio (paraguas #1717):
- #1914: el tipo purchase_settlement_variance no estaba en el selector.
- #1826: la validación rechazaba cuentas COGS/ajuste reales del catálogo.
- #2174: la bodega aceptaba cuentas inactivas, deshabilitadas o de grupo.
"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Accounts, Currency, Entity, Modules, User, database
from cacao_accounting.inventario.service import _validate_item_account
from cacao_accounting.inventario.services import _validate_warehouse_company_rows


def _crear_app():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
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
                Modules(module="inventory", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
            ]
        )
        database.session.flush()
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao SA",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        database.session.add_all(
            [
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                Accounts(
                    entity="cacao",
                    code="5203",
                    name="Variación de liquidación",
                    account_type="purchase_settlement_variance",
                    active=True,
                    enabled=True,
                    group=False,
                ),
                Accounts(
                    entity="cacao",
                    code="5101",
                    name="Costo de ventas",
                    account_type="cost_of_goods_sold",
                    active=True,
                    enabled=True,
                    group=False,
                ),
                Accounts(
                    entity="cacao",
                    code="5102",
                    name="Ajuste de inventario",
                    account_type="inventory_adjustment",
                    active=True,
                    enabled=True,
                    group=False,
                ),
                Accounts(
                    entity="cacao",
                    code="1101",
                    name="Inventario activo",
                    account_type="inventory",
                    active=True,
                    enabled=True,
                    group=False,
                ),
                Accounts(
                    entity="cacao",
                    code="1102",
                    name="Inventario inactivo",
                    account_type="inventory",
                    active=False,
                    enabled=True,
                    group=False,
                ),
                Accounts(
                    entity="cacao",
                    code="1103",
                    name="Inventario grupo",
                    account_type="inventory",
                    active=True,
                    enabled=True,
                    group=True,
                ),
                Accounts(
                    entity="cacao",
                    code="1104",
                    name="Inventario deshabilitado",
                    account_type="inventory",
                    active=True,
                    enabled=False,
                    group=False,
                ),
            ]
        )
        database.session.commit()
        ids = {account.code: account.id for account in database.session.execute(database.select(Accounts)).scalars().all()}
    return application, ids


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_edita_cuenta_con_tipo_de_variacion_de_liquidacion():
    """#1914: el tipo del catálogo se conserva al editar la cuenta."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/accounting/account/cacao/5203/edit",
            data={
                "code": "5203",
                "name": "Variación de liquidación",
                "entidad": "cacao",
                "account_type": "purchase_settlement_variance",
                "activo": "on",
            },
        )

        assert respuesta.status_code == 302
        with application.app_context():
            cuenta = database.session.get(Accounts, ids["5203"])
            assert cuenta is not None and cuenta.account_type == "purchase_settlement_variance"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize(
    ("account_code", "expected_type"),
    [
        ("5101", "cogs"),
        ("5102", "stock_adjustment"),
    ],
)
def test_acepta_los_tipos_reales_del_catalogo(account_code, expected_type):
    """#1826: COGS y ajuste usan los tipos que siembra el catálogo."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            _validate_item_account("cacao", ids[account_code], expected_type, "cuenta de inventario")
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_rechaza_un_tipo_incompatible_para_cogs():
    """#1826: la alineación no convierte cualquier cuenta en COGS."""
    from cacao_accounting.inventario.service import InventoryServiceError

    application, ids = _crear_app()
    try:
        with application.app_context():
            with pytest.raises(InventoryServiceError):
                _validate_item_account("cacao", ids["1101"], "cogs", "costo de venta")
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize(
    ("account_code", "mensaje"),
    [
        ("1102", "activa, habilitada y ser una cuenta hoja"),
        ("1103", "activa, habilitada y ser una cuenta hoja"),
        ("1104", "activa, habilitada y ser una cuenta hoja"),
    ],
)
def test_bodega_rechaza_cuentas_no_imputables(account_code, mensaje):
    """#2174: la bodega aplica vigencia y hoja antes de persistir."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            with pytest.raises(ValueError, match=mensaje):
                _validate_warehouse_company_rows([{"company": "cacao", "inventory_account_id": ids[account_code]}])
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_bodega_acepta_cuenta_imputable():
    """#2174: la cuenta activa, habilitada y hoja sigue siendo válida."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            _validate_warehouse_company_rows([{"company": "cacao", "inventory_account_id": ids["1101"]}])
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
