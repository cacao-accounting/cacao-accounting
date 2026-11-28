# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1883: las conciliaciones de caja chica identifican fondo, compañía y moneda.

La lista y el formulario de conteo deben mostrar el nombre del fondo con su
compañía y la moneda de los importes, sin exponer el ULID técnico ni cifras
nominales sin unidad monetaria. El código persistido y la conversión no cambian.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

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
    PettyCashReconciliation,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

CONTRASENA = "conciliacion-identidad-2026"


def _iniciar(client, user_id: str, app) -> None:
    """Abre la sesión del usuario sin repetir el flujo de login."""
    with app.app_context():
        usuario = database.session.get(User, user_id)
        auth_version = usuario.auth_version
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True


@pytest.fixture
def conciliacion_identificada():
    """Conciliación en cacao con un fondo con nombre y moneda NIO."""
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
    sufijo = uuid4().hex[:6]
    user_id = f"conciliador-{sufijo}"
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="cash", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
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
                    id=user_id,
                    user=user_id,
                    name="Conciliador de Caja",
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
        database.session.add(UserCompanyAccess(user_id=user_id, company_code="cacao"))
        rol = Roles(name=f"cash-conciliacion-{sufijo}", note="Conciliaciones de caja chica")
        database.session.add(rol)
        database.session.flush()
        modulo_caja = database.session.execute(database.select(Modules).filter_by(module="cash")).scalar_one()
        database.session.add_all(
            [
                RolesAccess(rol_id=rol.id, module_id=modulo_caja.id, access=True, view=True, edit=True, create=True),
                RolesUser(user_id=user_id, role_id=rol.id, active=True),
            ]
        )
        cuenta = Accounts(
            code=f"1.01.05.{sufijo[:5]}",
            name="Caja Chica Operativa",
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
            name="Fondo Operativo Norte",
            currency="NIO",
            float_amount=Decimal("500"),
            is_default=True,
            is_active=True,
        )
        database.session.add(fondo)
        database.session.flush()
        conciliacion = PettyCashReconciliation(
            company="cacao",
            petty_cash_id=fondo.id,
            reconciliation_date=date(2026, 11, 20),
            expected_cash=Decimal("100"),
            counted_cash=Decimal("95"),
            difference=Decimal("-5"),
            status="borrador",
            docstatus=0,
            transaction_currency="NIO",
        )
        database.session.add(conciliacion)
        database.session.commit()
        ids = {"user": user_id, "fondo": fondo.id, "conciliacion": conciliacion.id}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_la_lista_identifica_fondo_compania_y_moneda(conciliacion_identificada):
    """La fila muestra el fondo, su compañía y el código monetario."""
    application, ids = conciliacion_identificada
    client = application.test_client()
    _iniciar(client, ids["user"], application)

    response = client.get("/cash_management/petty-cash-reconciliation/list")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Fondo Operativo Norte" in cuerpo
    assert "(cacao)" in cuerpo
    assert "NIO" in cuerpo
    assert ids["fondo"] not in cuerpo


def test_el_formulario_de_conteo_informa_la_moneda(conciliacion_identificada):
    """La edición identifica el fondo y la unidad monetaria del conteo."""
    application, ids = conciliacion_identificada
    client = application.test_client()
    _iniciar(client, ids["user"], application)

    response = client.get(f"/cash_management/petty-cash-reconciliation/{ids['conciliacion']}/edit")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Fondo Operativo Norte" in cuerpo
    assert "NIO" in cuerpo
    assert ids["fondo"] not in cuerpo


def test_el_alta_muestra_la_moneda_de_cada_fondo(conciliacion_identificada):
    """El selector del alta anuncia la moneda del fondo antes de guardar."""
    application, ids = conciliacion_identificada
    client = application.test_client()
    _iniciar(client, ids["user"], application)

    response = client.get("/cash_management/petty-cash-reconciliation/new")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "Fondo Operativo Norte (NIO)" in cuerpo
    assert ids["fondo"] in cuerpo  # El value del selector conserva el id técnico.
