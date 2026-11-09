# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La conciliación bancaria exige una compañía explícita.

Escenario de negocio (issue #2038): el GET general sin ``company`` mostraba
transacciones de todas las compañías y enviaba un hidden vacío; el POST
respondía 400 porque no puede inferir una compañía única. El formulario
inicial era inutilizable para usuarios multiempresa.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Bank,
    BankAccount,
    BankTransaction,
    Entity,
    Modules,
    User,
    database,
)


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
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                Bank(name="Banco de Prueba", swift_code="TESTNI2N", is_active=True),
            ]
        )
        database.session.flush()
        banco = database.session.execute(database.select(Bank)).scalar_one()
        for codigo, descripcion in (("cacao", "RETIRO-CACAO"), ("beta", "RETIRO-BETA")):
            cuenta = BankAccount(
                company=codigo,
                bank_id=banco.id,
                account_name=f"Cuenta {codigo}",
                account_no=f"CTA-{codigo}",
                currency="NIO",
                is_active=True,
            )
            database.session.add(cuenta)
            database.session.flush()
            database.session.add(
                BankTransaction(
                    bank_account_id=cuenta.id,
                    identity_key=f"tx-{codigo}",
                    posting_date=date.today(),
                    withdrawal=10,
                    description=descripcion,
                )
            )
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_sin_compania_no_agrega_transacciones_de_varias_empresas():
    """El GET inicial muestra el selector y no filtra filas ajenas."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.get("/cash_management/bank-reconciliation")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert "Seleccione una compañía para conciliar transacciones." in html
        assert "RETIRO-CACAO" not in html
        assert "RETIRO-BETA" not in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_la_compania_seleccionada_filtra_y_se_conserva():
    """Elegir compañía limita las filas y queda seleccionada en el control."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.get("/cash_management/bank-reconciliation?company=beta")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert "RETIRO-BETA" in html
        assert "RETIRO-CACAO" not in html
        assert 'value="beta" selected' in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
