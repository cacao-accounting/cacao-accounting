# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Hidratación del formulario de nueva reposición (#2033).

Escenario de negocio: la tesorera llega al formulario de reposición desde la
lista con un fondo preseleccionado en la URL. El formulario debe abrirse con
la compañía, el fondo y la moneda ya resueltos, y mostrar los gastos
pendientes de ese fondo; sin query params los controles deben quedar vacíos.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Book,
    Currency,
    Entity,
    Modules,
    PettyCashAccount,
    PettyCashExpense,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

CONTRASENA = "caja-reposicion-hidrata-2026"
FECHA = date(2026, 11, 14)


@pytest.fixture
def caja_reposicion_hidratacion():
    """Fondo con gastos pendientes y anulados para el formulario de reposición."""
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
                Modules(module="cash", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao Comercial",
                    company_name="Cacao Comercial SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="solicitante-reposicion",
                    user="solicitante-reposicion",
                    name="Solicitante de Reposicion",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                ),
            ]
        )
        database.session.flush()
        database.session.add(
            Book(
                entity="cacao",
                code="DEFAULT_BOOK",
                name="Libro principal",
                status="activo",
                currency="NIO",
                is_primary=True,
            )
        )
        database.session.flush()
        database.session.add(UserCompanyAccess(user_id="solicitante-reposicion", company_code="cacao"))
        database.session.flush()
        rol_solicitante = Roles(name="cash-crea-reposiciones", note="Crea solicitudes de reposicion")
        database.session.add(rol_solicitante)
        database.session.flush()
        modulo_caja = database.session.execute(database.select(Modules).filter_by(module="cash")).scalar_one()
        database.session.add(
            RolesAccess(rol_id=rol_solicitante.id, module_id=modulo_caja.id, access=True, create=True, view=True)
        )
        database.session.add(RolesUser(user_id="solicitante-reposicion", role_id=rol_solicitante.id, active=True))
        database.session.flush()
        cuenta = Accounts(
            code="1.01.05.001",
            name="Caja Chica Reposicion",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="petty_cash",
        )
        database.session.add(cuenta)
        database.session.flush()
        fondo = PettyCashAccount(
            company="cacao",
            account_id=cuenta.id,
            name="Fondo Hidratacion Reposicion",
            currency="NIO",
            float_amount=Decimal("1000"),
            is_default=True,
            is_active=True,
        )
        database.session.add(fondo)
        database.session.flush()
        database.session.add_all(
            [
                PettyCashExpense(
                    company="cacao",
                    petty_cash_id=fondo.id,
                    concept="Taxi aeropuerto cliente",
                    expense_account_code="5.01.01.001",
                    amount=Decimal("45.50"),
                    posting_date=FECHA,
                    docstatus=1,
                    transaction_currency="NIO",
                ),
                PettyCashExpense(
                    company="cacao",
                    petty_cash_id=fondo.id,
                    concept="Gasto anulado no disponible",
                    expense_account_code="5.01.01.001",
                    amount=Decimal("10"),
                    posting_date=FECHA,
                    docstatus=2,
                    transaction_currency="NIO",
                ),
            ]
        )
        database.session.commit()
        ids = {"fondo": fondo.id}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _iniciar(client) -> None:
    response = client.post("/login", data={"usuario": "solicitante-reposicion", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200


def test_reposicion_nueva_hidrata_compania_fondo_y_gastos(caja_reposicion_hidratacion):
    """Los query params preseleccionan compañía, fondo, moneda y gastos pendientes."""
    application, ids = caja_reposicion_hidratacion
    client = application.test_client()
    _iniciar(client)

    response = client.get(f"/cash_management/petty-cash-replenishment/new?petty_cash_id={ids['fondo']}&company=cacao")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert re.search(r'initialValue:\s*"cacao"', cuerpo)
    assert re.search(r'initialLabel:\s*"cacao - Cacao Comercial"', cuerpo)
    assert re.search(rf'initialValue:\s*"{re.escape(ids["fondo"])}"', cuerpo)
    assert re.search(r'initialLabel:\s*"cacao - Fondo Hidratacion Reposicion"', cuerpo)
    assert re.search(r'id="pc_currency"[^>]*value="NIO"', cuerpo)
    assert "Taxi aeropuerto cliente" in cuerpo
    assert "45.50" in cuerpo


def test_reposicion_nueva_sin_query_params_deja_controles_vacios(caja_reposicion_hidratacion):
    """Sin query params el formulario abre en blanco y sin gastos listados."""
    application, ids = caja_reposicion_hidratacion
    client = application.test_client()
    _iniciar(client)

    response = client.get("/cash_management/petty-cash-replenishment/new")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert re.search(r'initialValue:\s*""', cuerpo)
    assert not re.search(rf'initialValue:\s*"{re.escape(ids["fondo"])}"', cuerpo)
    assert not re.search(r'initialValue:\s*"cacao"', cuerpo)
    assert re.search(r'id="pc_currency"[^>]*value=""', cuerpo)
    assert "Taxi aeropuerto cliente" not in cuerpo


def test_reposicion_nueva_no_lista_gastos_anulados(caja_reposicion_hidratacion):
    """Solo los gastos posteados y libres se ofrecen para reponer."""
    application, ids = caja_reposicion_hidratacion
    client = application.test_client()
    _iniciar(client)

    response = client.get(f"/cash_management/petty-cash-replenishment/new?petty_cash_id={ids['fondo']}&company=cacao")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Taxi aeropuerto cliente" in cuerpo
    assert "Gasto anulado no disponible" not in cuerpo
