# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Scripts de numeración bancaria en el detalle de cuenta.

Escenario de negocio: la edición de numeración de una cuenta bancaria usa
Alpine y depende de ``numberingConfig()``. El layout base debe consumir el
bloque ``scripts`` del template hijo para que la función llegue al navegador.
"""

from __future__ import annotations

import pytest

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import Bank, BankAccount, Currency, Entity, Modules, User, database

CONTRASENA = "numeracion-banco-2026"


@pytest.fixture
def cuenta_bancaria():
    """Compañía con una cuenta bancaria y usuario administrador."""
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
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
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
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=proteger_passwd(CONTRASENA),
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.commit()
        banco = Bank(name="Banco de Prueba", swift_code="TESTNI2N", is_active=True)
        database.session.add(banco)
        database.session.flush()
        cuenta = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name="Cuenta Cacao",
            account_no="CA-1",
            currency="NIO",
            is_active=True,
        )
        database.session.add(cuenta)
        database.session.commit()
        cuenta_id = cuenta.id
    yield application, cuenta_id
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_detalle_incluye_el_script_de_numeracion(cuenta_bancaria):
    """El bloque scripts del template hijo llega al HTML renderizado."""
    application, cuenta_id = cuenta_bancaria
    client = application.test_client()
    response = client.post("/login", data={"usuario": "admin", "acceso": CONTRASENA}, follow_redirects=True)
    assert response.status_code == 200

    response = client.get(f"/cash_management/bank-account/{cuenta_id}")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert "function numberingConfig()" in cuerpo
    assert "async save()" in cuerpo
