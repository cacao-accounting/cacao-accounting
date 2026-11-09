# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Las cuentas bancarias rechazan referencias inactivas.

Escenario de negocio (paraguas #1716): el selector ofrecía solo registros
activos, pero el POST aceptaba una moneda, banco, cuenta GL, serie o chequera
desactivada y la persistía.

Cubre los hijos #1979 (moneda), #1982 (numeración), #2086 (banco) y #2088
(cuenta GL).
"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Bank,
    BankAccount,
    BankAccountNumberingConfig,
    Currency,
    Entity,
    ExternalCounter,
    Modules,
    NamingSeries,
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
                Modules(module="admin", default=False, enabled=True),
                Modules(module="cash", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Currency(code="OFF", name="Moneda inactiva", decimals=2, active=False, default=False),
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
                    password=b"x",
                    active=True,
                    classification="admin",
                    company="cacao",
                ),
                Bank(name="Banco activo", is_active=True),
                Bank(name="Banco inactivo", is_active=False),
                Accounts(
                    entity="cacao",
                    code="110101",
                    name="Banco activo",
                    account_type="bank",
                    active=True,
                    enabled=True,
                    group=False,
                ),
                Accounts(
                    entity="cacao",
                    code="110102",
                    name="Banco inactivo",
                    account_type="bank",
                    active=False,
                    enabled=True,
                    group=False,
                ),
                NamingSeries(
                    name="Pagos activos",
                    entity_type="payment_entry",
                    company="cacao",
                    prefix_template="PAGO-",
                    is_active=True,
                ),
                NamingSeries(
                    name="Pagos inactivos",
                    entity_type="payment_entry",
                    company="cacao",
                    prefix_template="OFF-",
                    is_active=False,
                ),
                ExternalCounter(
                    company="cacao",
                    name="Chequera activa",
                    counter_type="checkbook",
                    is_active=True,
                ),
                ExternalCounter(
                    company="cacao",
                    name="Chequera inactiva",
                    counter_type="checkbook",
                    is_active=False,
                ),
            ]
        )
        database.session.commit()
        return application, _ids()


def _ids() -> dict[str, str]:
    """Identificadores estables de las referencias activas e inactivas."""
    return {
        "bank_active": database.session.execute(database.select(Bank).filter_by(is_active=True)).scalar_one().id,
        "bank_inactive": database.session.execute(database.select(Bank).filter_by(is_active=False)).scalar_one().id,
        "gl_active": database.session.execute(database.select(Accounts).filter_by(code="110101")).scalar_one().id,
        "gl_inactive": database.session.execute(database.select(Accounts).filter_by(code="110102")).scalar_one().id,
        "series_inactive": database.session.execute(database.select(NamingSeries).filter_by(is_active=False)).scalar_one().id,
        "counter_inactive": database.session.execute(database.select(ExternalCounter).filter_by(is_active=False))
        .scalar_one()
        .id,
    }


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def _formulario(ids: dict[str, str], **overrides) -> dict[str, str]:
    datos = {
        "bank_id": ids["bank_active"],
        "company": "cacao",
        "account_name": "Cuenta operativa",
        "account_no": "CTA-001",
        "currency": "NIO",
        "gl_account_id": ids["gl_active"],
    }
    datos.update(overrides)
    return datos


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("bank_id", "bank_inactive"),
        ("currency", "OFF"),
        ("gl_account_id", "gl_inactive"),
    ],
)
def test_rechaza_referencias_inactivas(campo, valor):
    """Ni el banco, ni la moneda, ni la cuenta GL inactivos se persisten."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        datos = _formulario(ids, **{campo: ids[valor] if valor in ids else valor})

        respuesta = client.post("/cash_management/bank-account/new", data=datos)

        assert respuesta.status_code == 200
        with application.app_context():
            assert database.session.execute(database.select(BankAccount)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_crea_con_referencias_activas():
    """La combinación vigente crea la cuenta bancaria."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post("/cash_management/bank-account/new", data=_formulario(ids))

        assert respuesta.status_code == 302
        with application.app_context():
            cuenta = database.session.execute(database.select(BankAccount)).scalar_one()
            assert cuenta.bank_id == ids["bank_active"]
            assert cuenta.currency == "NIO"
            assert cuenta.gl_account_id == ids["gl_active"]
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_guarda_numeracion_rechaza_serie_inactiva():
    """#1982: una serie desactivada no se guarda en la configuración."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        creacion = client.post("/cash_management/bank-account/new", data=_formulario(ids))
        assert creacion.status_code == 302
        with application.app_context():
            cuenta = database.session.execute(database.select(BankAccount)).scalar_one()
            account_id = cuenta.id

        respuesta = client.post(
            f"/cash_management/bank-account/{account_id}/numbering-config",
            json={
                "configs": [
                    {
                        "payment_type": "pay",
                        "naming_series_id": ids["series_inactive"],
                        "use_external_counter": False,
                    }
                ]
            },
        )

        assert respuesta.status_code == 400
        with application.app_context():
            config = database.session.execute(
                database.select(BankAccountNumberingConfig).filter_by(
                    bank_account_id=account_id,
                    payment_type="pay",
                )
            ).scalar_one()
            assert config.naming_series_id is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_la_guardia_detecta_desactivacion_concurrente():
    """Si la referencia se desactiva entre el GET y el POST, el servidor la rechaza."""
    from cacao_accounting.bancos.services import (
        IdentifierConfigurationError,
        _validate_bank_account_references,
    )

    application, ids = _crear_app()
    try:
        with application.app_context():
            banco = database.session.get(Bank, ids["bank_active"])
            banco.is_active = False
            database.session.commit()

            with pytest.raises(IdentifierConfigurationError, match="banco activo"):
                _validate_bank_account_references(
                    company="cacao",
                    bank_id=ids["bank_active"],
                    currency="NIO",
                    gl_account_id=ids["gl_active"],
                )
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_guarda_numeracion_rechaza_chequera_inactiva():
    """#1982: una chequera desactivada no se guarda como contador externo."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        creacion = client.post("/cash_management/bank-account/new", data=_formulario(ids))
        assert creacion.status_code == 302
        with application.app_context():
            cuenta = database.session.execute(database.select(BankAccount)).scalar_one()
            account_id = cuenta.id

        respuesta = client.post(
            f"/cash_management/bank-account/{account_id}/numbering-config",
            json={
                "configs": [
                    {
                        "payment_type": "pay",
                        "use_external_counter": True,
                        "external_counter_id": ids["counter_inactive"],
                    }
                ]
            },
        )

        assert respuesta.status_code == 400
        with application.app_context():
            config = database.session.execute(
                database.select(BankAccountNumberingConfig).filter_by(
                    bank_account_id=account_id,
                    payment_type="pay",
                )
            ).scalar_one()
            assert config.external_counter_id is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
