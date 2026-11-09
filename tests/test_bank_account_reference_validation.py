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
    PaymentEntry,
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
                Accounts(
                    entity="cacao",
                    code="110103",
                    name="Cuenta agrupadora",
                    account_type="bank",
                    active=True,
                    enabled=True,
                    group=True,
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
                NamingSeries(
                    name="Ventas activas",
                    entity_type="sales_invoice",
                    company="cacao",
                    prefix_template="FAC-",
                    is_active=True,
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
                ExternalCounter(
                    company="cacao",
                    name="Contador no chequera",
                    counter_type="other",
                    is_active=True,
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
        "gl_group": database.session.execute(database.select(Accounts).filter_by(code="110103")).scalar_one().id,
        "series_inactive": database.session.execute(database.select(NamingSeries).filter_by(is_active=False)).scalar_one().id,
        "series_wrong_type": database.session.execute(database.select(NamingSeries).filter_by(entity_type="sales_invoice"))
        .scalar_one()
        .id,
        "counter_inactive": database.session.execute(database.select(ExternalCounter).filter_by(is_active=False))
        .scalar_one()
        .id,
        "counter_other": database.session.execute(database.select(ExternalCounter).filter_by(counter_type="other"))
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


def test_duplicado_de_cuenta_devuelve_error_controlado():
    """#1980: repetir compañía y número devuelve formulario, no HTTP 500."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        primera = client.post("/cash_management/bank-account/new", data=_formulario(ids))
        segunda = client.post(
            "/cash_management/bank-account/new",
            data=_formulario(ids, account_name="Otra cuenta"),
        )

        assert primera.status_code == 302
        assert segunda.status_code == 200
        assert "Ya existe una cuenta bancaria con ese número" in segunda.get_data(as_text=True)
        with application.app_context():
            assert len(database.session.execute(database.select(BankAccount)).scalars().all()) == 1
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_rechaza_nombre_de_cuenta_fuera_de_limite():
    """#2087: el nombre respeta el VARCHAR(150) del modelo antes de persistir."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/cash_management/bank-account/new",
            data=_formulario(ids, account_name="A" * 151),
        )

        assert respuesta.status_code == 200
        assert "El nombre de la cuenta no puede superar los 150 caracteres." in respuesta.get_data(as_text=True)
        with application.app_context():
            assert database.session.execute(database.select(BankAccount)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def _crear_cuenta(application, ids):
    client = _cliente(application)
    assert client.post("/cash_management/bank-account/new", data=_formulario(ids)).status_code == 302
    with application.app_context():
        return database.session.execute(database.select(BankAccount)).scalar_one().id


def test_guarda_numeracion_rechaza_serie_de_otro_tipo():
    """#1983: la serie debe corresponder al entity_type del tipo de pago."""
    application, ids = _crear_app()
    try:
        account_id = _crear_cuenta(application, ids)
        client = _cliente(application)
        respuesta = client.post(
            f"/cash_management/bank-account/{account_id}/numbering-config",
            json={
                "configs": [
                    {
                        "payment_type": "pay",
                        "naming_series_id": ids["series_wrong_type"],
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


def test_guarda_numeracion_rechaza_contador_no_chequera():
    """#1983: el contador externo debe ser una chequera."""
    application, ids = _crear_app()
    try:
        account_id = _crear_cuenta(application, ids)
        client = _cliente(application)
        respuesta = client.post(
            f"/cash_management/bank-account/{account_id}/numbering-config",
            json={
                "configs": [
                    {
                        "payment_type": "pay",
                        "use_external_counter": True,
                        "external_counter_id": ids["counter_other"],
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


@pytest.mark.parametrize(("clave_cuenta", "aceptada"), [("gl_active", True), ("gl_inactive", False), ("gl_group", False)])
def test_la_cuenta_gl_del_pago_debe_ser_hoja_vigente(clave_cuenta, aceptada):
    """#2180: la validación de pagos rechaza cuentas inactivas o agrupadoras."""
    from cacao_accounting.bancos.services import _validate_payment_gl_accounts

    application, ids = _crear_app()
    try:
        with application.app_context():
            if aceptada:
                _validate_payment_gl_accounts(
                    company="cacao",
                    payment_type="debit_note",
                    bank_account_id=None,
                    target_bank_account_id=None,
                    paid_from_account_id=None,
                    paid_to_account_id=ids[clave_cuenta],
                )
            else:
                with pytest.raises(ValueError, match="activa, habilitada y ser una cuenta hoja"):
                    _validate_payment_gl_accounts(
                        company="cacao",
                        payment_type="debit_note",
                        bank_account_id=None,
                        target_bank_account_id=None,
                        paid_from_account_id=None,
                        paid_to_account_id=ids[clave_cuenta],
                    )
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_submit_revalida_la_cuenta_gl_del_pago():
    """#2180: contabilizar un borrador rechaza una cuenta ya desactivada."""
    application, ids = _crear_app()
    try:
        with application.app_context():
            pago = PaymentEntry(
                company="cacao",
                payment_type="debit_note",
                paid_from_account_id=ids["gl_active"],
                paid_to_account_id=ids["gl_inactive"],
                docstatus=0,
            )
            database.session.add(pago)
            database.session.commit()
            payment_id = pago.id

        client = _cliente(application)
        respuesta = client.post(f"/cash_management/payment/{payment_id}/submit")

        assert respuesta.status_code == 302
        with application.app_context():
            pago = database.session.get(PaymentEntry, payment_id)
            assert pago is not None and pago.docstatus == 0
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
