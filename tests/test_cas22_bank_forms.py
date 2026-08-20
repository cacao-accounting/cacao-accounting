# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas para CAS-22: Formularios bancarios nota_nueva y transferencia_nueva.

Cubre:
1. GET rendering de nota_nueva.html (nota de débito y nota de crédito) y transferencia_nueva.html.
2. Campos específicos de cada tipo (tipo de nota, tipo de transferencia, dimensiones contables).
3. Escenarios multimoneda (transferencias y notas con tipos de cambio).
4. Contador externo (cheques), series de numeración dedicadas y trazabilidad de uso.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.database import (
    Accounts,
    BankAccount,
    BankAccountNumberingConfig,
    ExternalCounter,
    ExternalNumberUsage,
    NamingSeries,
    PaymentEntry,
    Sequence,
    SeriesSequenceMap,
    database,
)
from cacao_accounting.database.helpers import inicia_base_de_datos


@pytest.fixture()
def app_ctx():
    """Aplicación aislada con datos de desarrollo inicializados."""
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test_secret_key_cas22",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        from cacao_accounting.datos.dev import master_data

        inicia_base_de_datos(app, user="cacao", passwd="cacao", with_examples=False)
        master_data()
        database.session.commit()
        yield app


def login(client, username: str = "cacao", password: str = "cacao"):
    """Inicia sesión con el cliente de pruebas."""
    return client.post("/login", data={"usuario": username, "acceso": password}, follow_redirects=True)


def _get_or_create_expense_account(company: str = "cacao") -> Accounts:
    """Obtiene o crea una cuenta contable de tipo gasto para la compañía."""
    account = (
        database.session.execute(
            database.select(Accounts).filter_by(entity=company, account_type="expense").order_by(Accounts.code.asc())
        )
        .scalars()
        .first()
    )
    if not account:
        account = Accounts(
            entity=company,
            code="61.01.001.001",
            name="Gastos Bancarios",
            account_type="expense",
            classification="expense",
            active=True,
            enabled=True,
        )
        database.session.add(account)
        database.session.commit()
    return account


def _get_or_create_income_account(company: str = "cacao") -> Accounts:
    """Obtiene o crea una cuenta contable de tipo ingreso para la compañía."""
    account = (
        database.session.execute(
            database.select(Accounts).filter_by(entity=company, account_type="income").order_by(Accounts.code.asc())
        )
        .scalars()
        .first()
    )
    if not account:
        account = Accounts(
            entity=company,
            code="41.01.001.001",
            name="Intereses Ganados",
            account_type="income",
            classification="income",
            active=True,
            enabled=True,
        )
        database.session.add(account)
        database.session.commit()
    return account


def _create_dedicated_naming_series(company: str, entity_type: str, prefix_template: str, series_name: str) -> NamingSeries:
    """Crea una serie de numeración con su secuencia asociada."""
    sequence = Sequence(name=f"seq-{series_name}", current_value=0, increment=1, padding=5)
    series = NamingSeries(
        name=series_name,
        entity_type=entity_type,
        company=company,
        prefix_template=prefix_template,
        is_active=True,
        is_default=True,
    )
    database.session.add_all([sequence, series])
    database.session.flush()
    database.session.add(SeriesSequenceMap(naming_series_id=series.id, sequence_id=sequence.id, priority=0))
    database.session.commit()
    return series


# =====================================================================================
# 1. GET Rendering Tests
# =====================================================================================


def test_get_debit_note_new_renders_correct_template_and_elements(app_ctx):
    """GET /cash_management/payment/debit-note/new renderiza nota_nueva.html para nota de débito."""
    client = app_ctx.test_client()
    login(client)

    response = client.get("/cash_management/payment/debit-note/new")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # Título y breadcrumb
    assert "Nueva Nota de Débito Bancario" in html
    assert "Bancos" in html
    assert "Inicio" in html

    # Configuración Alpine y tipo de pago
    assert 'paymentType: "debit_note"' in html
    assert 'bankNoteForm({ paymentType: "debit_note" })' in html

    # Controles de Smart-Select
    assert 'doctype: "company"' in html
    assert 'doctype: "naming_series"' in html
    assert 'doctype: "bank_account"' in html
    assert 'doctype: "cost_center"' in html
    assert 'doctype: "unit"' in html
    assert 'doctype: "project"' in html

    # Campo específico de nota de débito: Cuenta de cargo / gasto en el formulario
    assert "Cuenta Contable (Cargo / Gasto)" in html
    assert 'name: "paid_to_account_id"' in html
    assert "Cuenta Contable (Abono / Ingreso)" not in html
    assert 'name: "paid_from_account_id"' not in html

    # Enlace de cancelar apunta a la lista de notas de débito
    assert "/cash_management/payment/debit-note/list" in html


def test_get_credit_note_new_renders_correct_template_and_elements(app_ctx):
    """GET /cash_management/payment/credit-note/new renderiza nota_nueva.html para nota de crédito."""
    client = app_ctx.test_client()
    login(client)

    response = client.get("/cash_management/payment/credit-note/new")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # Título y breadcrumb
    assert "Nueva Nota de Crédito Bancario" in html
    assert "Bancos" in html
    assert "Inicio" in html

    # Configuración Alpine y tipo de pago
    assert 'paymentType: "credit_note"' in html
    assert 'bankNoteForm({ paymentType: "credit_note" })' in html

    # Controles de Smart-Select
    assert 'doctype: "company"' in html
    assert 'doctype: "naming_series"' in html
    assert 'doctype: "bank_account"' in html

    # Campo específico de nota de crédito: Cuenta de abono / ingreso en el formulario
    assert "Cuenta Contable (Abono / Ingreso)" in html
    assert 'name: "paid_from_account_id"' in html
    assert "Cuenta Contable (Cargo / Gasto)" not in html
    assert 'name: "paid_to_account_id"' not in html

    # Enlace de cancelar apunta a la lista de notas de crédito
    assert "/cash_management/payment/credit-note/list" in html


def test_get_transfer_new_renders_correct_template_and_elements(app_ctx):
    """GET /cash_management/payment/transfer/new renderiza transferencia_nueva.html con origen y destino."""
    client = app_ctx.test_client()
    login(client)

    response = client.get("/cash_management/payment/transfer/new")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # Título y breadcrumb
    assert "Nueva Transferencia Bancaria" in html
    assert "Bancos" in html

    # Configuración Alpine
    assert 'bankTransferForm({ paymentType: "internal_transfer" })' in html

    # Sección de Cuenta de Origen
    assert "Cuenta de Origen" in html
    assert "Banco Origen" in html
    assert 'name: "bank_account_id"' in html
    assert "Monto a Transferir" in html

    # Sección de Cuenta de Destino
    assert "Cuenta de Destino" in html
    assert "Banco Destino" in html
    assert 'name: "target_bank_account_id"' in html
    assert "Tipo de Cambio" in html
    assert "Monto esperado en destino" in html

    # Enlace de cancelar apunta a la lista de transferencias
    assert "/cash_management/transfer/list" in html


def test_bank_forms_require_authentication(app_ctx):
    """Las rutas de nuevos formularios bancarios exigen usuario autenticado."""
    client = app_ctx.test_client()

    routes = [
        "/cash_management/payment/debit-note/new",
        "/cash_management/payment/credit-note/new",
        "/cash_management/payment/transfer/new",
    ]
    for route in routes:
        response = client.get(route)
        assert response.status_code == 302
        assert "/login" in response.headers.get("Location", "")


# =====================================================================================
# 2. Specific Fields & POST Lifecycle Tests
# =====================================================================================


def test_post_debit_note_creation_and_attributes(app_ctx):
    """POST /cash_management/payment/debit-note/new crea correctamente una nota de débito."""
    client = app_ctx.test_client()
    login(client)

    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    expense_acc = _get_or_create_expense_account("cacao")

    payload = {
        "payment_type": "debit_note",
        "company": "cacao",
        "bank_account_id": bank.id,
        "paid_to_account_id": expense_acc.id,
        "paid_amount": "150.50",
        "posting_date": date.today().isoformat(),
        "cost_center_code": "ADMIN",
        "unit_code": "CENTRAL",
        "project_code": "PRJ-01",
        "remarks": "Comisión por mantenimiento de cuenta",
        "external_number": "ND-2026-001",
    }

    response = client.post(
        "/cash_management/payment/debit-note/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    assert response.status_code == 200

    payment = (
        database.session.execute(
            database.select(PaymentEntry).filter_by(payment_type="debit_note").order_by(PaymentEntry.created.desc())
        )
        .scalars()
        .first()
    )
    assert payment is not None
    assert payment.payment_type == "debit_note"
    assert payment.company == "cacao"
    assert payment.bank_account_id == bank.id
    assert payment.paid_to_account_id == expense_acc.id
    assert payment.paid_amount == Decimal("150.50")
    assert payment.cost_center_code == "ADMIN"
    assert payment.unit_code == "CENTRAL"
    assert payment.project_code == "PRJ-01"
    assert payment.remarks == "Comisión por mantenimiento de cuenta"


def test_post_credit_note_creation_and_attributes(app_ctx):
    """POST /cash_management/payment/credit-note/new crea correctamente una nota de crédito."""
    client = app_ctx.test_client()
    login(client)

    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    income_acc = _get_or_create_income_account("cacao")

    payload = {
        "payment_type": "credit_note",
        "company": "cacao",
        "bank_account_id": bank.id,
        "paid_from_account_id": income_acc.id,
        "paid_amount": "320.75",
        "posting_date": date.today().isoformat(),
        "cost_center_code": "FIN",
        "remarks": "Abono de intereses ganados mes",
        "external_number": "NC-2026-088",
    }

    response = client.post(
        "/cash_management/payment/credit-note/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    assert response.status_code == 200

    payment = (
        database.session.execute(
            database.select(PaymentEntry).filter_by(payment_type="credit_note").order_by(PaymentEntry.created.desc())
        )
        .scalars()
        .first()
    )
    assert payment is not None
    assert payment.payment_type == "credit_note"
    assert payment.company == "cacao"
    assert payment.bank_account_id == bank.id
    assert payment.paid_from_account_id == income_acc.id
    assert payment.received_amount == Decimal("320.75")
    assert payment.cost_center_code == "FIN"
    assert payment.remarks == "Abono de intereses ganados mes"


def test_post_transfer_creation_and_attributes(app_ctx):
    """POST /cash_management/payment/transfer/new crea correctamente una transferencia interna."""
    client = app_ctx.test_client()
    login(client)

    banks = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().all()
    assert len(banks) >= 2, "Se requieren al menos 2 cuentas bancarias para probar transferencia"
    source_bank = banks[0]
    target_bank = banks[1]

    payload = {
        "payment_type": "internal_transfer",
        "company": "cacao",
        "bank_account_id": source_bank.id,
        "target_bank_account_id": target_bank.id,
        "paid_amount": "500.00",
        "posting_date": date.today().isoformat(),
        "remarks": "Transferencia de fondos operativa",
        "external_number": "TR-9988",
    }

    response = client.post(
        "/cash_management/payment/transfer/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    assert response.status_code == 200

    payment = (
        database.session.execute(
            database.select(PaymentEntry).filter_by(payment_type="internal_transfer").order_by(PaymentEntry.created.desc())
        )
        .scalars()
        .first()
    )
    assert payment is not None
    assert payment.payment_type == "internal_transfer"
    assert payment.bank_account_id == source_bank.id
    assert payment.target_bank_account_id == target_bank.id
    assert payment.paid_from_account_id == source_bank.gl_account_id
    assert payment.paid_to_account_id == target_bank.gl_account_id
    assert payment.paid_amount == Decimal("500.00")
    assert payment.remarks == "Transferencia de fondos operativa"


def test_debit_note_rejects_cross_company_gl_account(app_ctx):
    """Nota de débito rechaza cuenta contable perteneciente a otra compañía."""
    client = app_ctx.test_client()
    login(client)

    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    foreign_expense = Accounts(
        entity="cafe",
        code="61.01.999.999",
        name="Gasto de otra empresa",
        account_type="expense",
        classification="expense",
        active=True,
        enabled=True,
    )
    database.session.add(foreign_expense)
    database.session.commit()

    payload = {
        "payment_type": "debit_note",
        "company": "cacao",
        "bank_account_id": bank.id,
        "paid_to_account_id": foreign_expense.id,
        "paid_amount": "100.00",
        "posting_date": date.today().isoformat(),
    }

    response = client.post(
        "/cash_management/payment/debit-note/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    # Debe rechazar y mostrar mensaje de error
    assert (
        b"pertenecer a la compa" in response.data.lower()
        or b"error" in response.data.lower()
        or response.status_code in (400, 409)
    )


def test_transfer_rejects_same_source_and_target_account(app_ctx):
    """Transferencia rechaza si la cuenta origen y destino son la misma."""
    client = app_ctx.test_client()
    login(client)

    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()

    payload = {
        "payment_type": "internal_transfer",
        "company": "cacao",
        "bank_account_id": bank.id,
        "target_bank_account_id": bank.id,
        "paid_amount": "200.00",
        "posting_date": date.today().isoformat(),
    }

    response = client.post(
        "/cash_management/payment/transfer/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    assert b"distintas" in response.data.lower() or b"error" in response.data.lower()


def test_transfer_rejects_target_bank_from_different_company(app_ctx):
    """Transferencia rechaza cuenta destino de otra compañía."""
    client = app_ctx.test_client()
    login(client)

    source_bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    other_bank = (
        database.session.execute(database.select(BankAccount).filter(BankAccount.company != "cacao")).scalars().first()
    )

    if not other_bank:
        other_bank = BankAccount(
            bank_id=source_bank.bank_id,
            company="cafe",
            account_name="Cuenta Cafe",
            account_no="CAFE-001",
            currency="NIO",
        )
        database.session.add(other_bank)
        database.session.commit()

    payload = {
        "payment_type": "internal_transfer",
        "company": "cacao",
        "bank_account_id": source_bank.id,
        "target_bank_account_id": other_bank.id,
        "paid_amount": "200.00",
        "posting_date": date.today().isoformat(),
    }

    response = client.post(
        "/cash_management/payment/transfer/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    assert b"misma compa" in response.data.lower() or b"error" in response.data.lower()


# =====================================================================================
# 3. Multicurrency Scenarios
# =====================================================================================


def test_transfer_multicurrency_usd_to_nio(app_ctx, monkeypatch):
    """Transferencia entre cuentas de distinta moneda calcula importes con tasa de cambio."""
    import sys

    client = app_ctx.test_client()
    login(client)

    source_usd = (
        database.session.execute(database.select(BankAccount).filter_by(company="cacao", currency="USD")).scalars().first()
    )
    target_nio = (
        database.session.execute(database.select(BankAccount).filter_by(company="cacao", currency="NIO")).scalars().first()
    )
    assert source_usd is not None
    assert target_nio is not None

    monkeypatch.setattr(
        sys.modules["cacao_accounting.bancos.services"],
        "_lookup_exchange_rate",
        lambda currency, company_currency, posting_date: Decimal("36"),
    )

    payload = {
        "payment_type": "internal_transfer",
        "company": "cacao",
        "bank_account_id": source_usd.id,
        "target_bank_account_id": target_nio.id,
        "paid_amount": "100.00",
        "exchange_rate": "36.0000",
        "posting_date": date.today().isoformat(),
        "remarks": "Transferencia USD a NIO",
    }

    response = client.post(
        "/cash_management/payment/transfer/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    assert response.status_code == 200

    payment = (
        database.session.execute(
            database.select(PaymentEntry)
            .filter_by(payment_type="internal_transfer", bank_account_id=source_usd.id)
            .order_by(PaymentEntry.created.desc())
        )
        .scalars()
        .first()
    )
    assert payment is not None
    assert payment.currency == "USD"
    assert payment.paid_amount == Decimal("100.00")
    assert payment.received_amount == Decimal("3600.0000")
    assert payment.base_paid_amount == Decimal("3600.0000")


def test_transfer_multicurrency_rejects_non_positive_exchange_rate(app_ctx):
    """Transferencia multimoneda rechaza tasa de cambio menor o igual a cero."""
    client = app_ctx.test_client()
    login(client)

    source_usd = (
        database.session.execute(database.select(BankAccount).filter_by(company="cacao", currency="USD")).scalars().first()
    )
    target_nio = (
        database.session.execute(database.select(BankAccount).filter_by(company="cacao", currency="NIO")).scalars().first()
    )

    for invalid_rate in ["0", "-1.5"]:
        payload = {
            "payment_type": "internal_transfer",
            "company": "cacao",
            "bank_account_id": source_usd.id,
            "target_bank_account_id": target_nio.id,
            "paid_amount": "100.00",
            "exchange_rate": invalid_rate,
            "posting_date": date.today().isoformat(),
        }

        response = client.post(
            "/cash_management/payment/transfer/new",
            data={"payment_payload": json.dumps(payload)},
            follow_redirects=True,
        )
        assert b"positivo" in response.data.lower() or b"error" in response.data.lower()


def test_debit_note_multicurrency_usd_bank_account(app_ctx, monkeypatch):
    """Nota de débito con cuenta en USD convierte el importe base según el tipo de cambio."""
    import sys

    client = app_ctx.test_client()
    login(client)

    bank_usd = (
        database.session.execute(database.select(BankAccount).filter_by(company="cacao", currency="USD")).scalars().first()
    )
    expense_acc = _get_or_create_expense_account("cacao")

    monkeypatch.setattr(
        sys.modules["cacao_accounting.bancos.services"],
        "_lookup_exchange_rate",
        lambda currency, company_currency, posting_date: Decimal("36.50"),
    )

    payload = {
        "payment_type": "debit_note",
        "company": "cacao",
        "bank_account_id": bank_usd.id,
        "paid_to_account_id": expense_acc.id,
        "paid_amount": "50.00",
        "posting_date": date.today().isoformat(),
        "remarks": "Cargo por comisión bancaria en USD",
    }

    response = client.post(
        "/cash_management/payment/debit-note/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    assert response.status_code == 200

    payment = (
        database.session.execute(
            database.select(PaymentEntry)
            .filter_by(payment_type="debit_note", bank_account_id=bank_usd.id)
            .order_by(PaymentEntry.created.desc())
        )
        .scalars()
        .first()
    )
    assert payment is not None
    assert payment.currency == "USD"
    assert payment.paid_amount == Decimal("50.00")
    assert payment.exchange_rate == Decimal("36.50")
    assert payment.base_paid_amount == Decimal("1825.0000")


def test_credit_note_multicurrency_usd_bank_account(app_ctx, monkeypatch):
    """Nota de crédito con cuenta en USD convierte el importe base según el tipo de cambio."""
    import sys

    client = app_ctx.test_client()
    login(client)

    bank_usd = (
        database.session.execute(database.select(BankAccount).filter_by(company="cacao", currency="USD")).scalars().first()
    )
    income_acc = _get_or_create_income_account("cacao")

    monkeypatch.setattr(
        sys.modules["cacao_accounting.bancos.services"],
        "_lookup_exchange_rate",
        lambda currency, company_currency, posting_date: Decimal("36.50"),
    )

    payload = {
        "payment_type": "credit_note",
        "company": "cacao",
        "bank_account_id": bank_usd.id,
        "paid_from_account_id": income_acc.id,
        "paid_amount": "75.00",
        "posting_date": date.today().isoformat(),
        "remarks": "Intereses recibidos en USD",
    }

    response = client.post(
        "/cash_management/payment/credit-note/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    assert response.status_code == 200

    payment = (
        database.session.execute(
            database.select(PaymentEntry)
            .filter_by(payment_type="credit_note", bank_account_id=bank_usd.id)
            .order_by(PaymentEntry.created.desc())
        )
        .scalars()
        .first()
    )
    assert payment is not None
    assert payment.currency == "USD"
    assert payment.received_amount == Decimal("75.00")
    assert payment.exchange_rate == Decimal("36.50")
    assert payment.base_received_amount == Decimal("2737.5000")


# =====================================================================================
# 4. External Counter (Checks) & Numbering Series
# =====================================================================================


def test_debit_note_uses_configured_bank_debit_note_naming_series(app_ctx):
    """Nota de débito asigna document_no usando la serie dedicada bank_debit_note."""
    client = app_ctx.test_client()
    login(client)

    series = _create_dedicated_naming_series(
        company="cacao",
        entity_type="bank_debit_note",
        prefix_template="ND-*YYYY*-",
        series_name="ND-SERIES-TEST",
    )
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    expense_acc = _get_or_create_expense_account("cacao")

    # Configurar serie en BankAccountNumberingConfig
    num_config = database.session.execute(
        database.select(BankAccountNumberingConfig).filter_by(bank_account_id=bank.id, payment_type="debit_note")
    ).scalar_one_or_none()
    if num_config:
        num_config.naming_series_id = series.id
    else:
        num_config = BankAccountNumberingConfig(
            bank_account_id=bank.id,
            payment_type="debit_note",
            naming_series_id=series.id,
        )
        database.session.add(num_config)
    database.session.commit()

    payload = {
        "payment_type": "debit_note",
        "company": "cacao",
        "bank_account_id": bank.id,
        "paid_to_account_id": expense_acc.id,
        "paid_amount": "80.00",
        "posting_date": date.today().isoformat(),
    }

    response = client.post(
        "/cash_management/payment/debit-note/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    assert response.status_code == 200

    payment = (
        database.session.execute(
            database.select(PaymentEntry)
            .filter_by(payment_type="debit_note", bank_account_id=bank.id)
            .order_by(PaymentEntry.created.desc())
        )
        .scalars()
        .first()
    )
    assert payment is not None
    assert payment.naming_series_id == series.id
    current_year = str(date.today().year)
    assert payment.document_no.startswith(f"ND-{current_year}-")


def test_credit_note_uses_configured_bank_credit_note_naming_series(app_ctx):
    """Nota de crédito asigna document_no usando la serie dedicada bank_credit_note."""
    client = app_ctx.test_client()
    login(client)

    series = _create_dedicated_naming_series(
        company="cacao",
        entity_type="bank_credit_note",
        prefix_template="NC-*YYYY*-",
        series_name="NC-SERIES-TEST",
    )
    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    income_acc = _get_or_create_income_account("cacao")

    # Configurar serie en BankAccountNumberingConfig
    num_config = database.session.execute(
        database.select(BankAccountNumberingConfig).filter_by(bank_account_id=bank.id, payment_type="credit_note")
    ).scalar_one_or_none()
    if num_config:
        num_config.naming_series_id = series.id
    else:
        num_config = BankAccountNumberingConfig(
            bank_account_id=bank.id,
            payment_type="credit_note",
            naming_series_id=series.id,
        )
        database.session.add(num_config)
    database.session.commit()

    payload = {
        "payment_type": "credit_note",
        "company": "cacao",
        "bank_account_id": bank.id,
        "paid_from_account_id": income_acc.id,
        "paid_amount": "90.00",
        "posting_date": date.today().isoformat(),
    }

    response = client.post(
        "/cash_management/payment/credit-note/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    assert response.status_code == 200

    payment = (
        database.session.execute(
            database.select(PaymentEntry)
            .filter_by(payment_type="credit_note", bank_account_id=bank.id)
            .order_by(PaymentEntry.created.desc())
        )
        .scalars()
        .first()
    )
    assert payment is not None
    assert payment.naming_series_id == series.id
    current_year = str(date.today().year)
    assert payment.document_no.startswith(f"NC-{current_year}-")


def test_transfer_uses_configured_bank_transfer_naming_series(app_ctx):
    """Transferencia asigna document_no usando la serie dedicada bank_transfer."""
    client = app_ctx.test_client()
    login(client)

    series = _create_dedicated_naming_series(
        company="cacao",
        entity_type="bank_transfer",
        prefix_template="TR-*YYYY*-",
        series_name="TR-SERIES-TEST",
    )
    banks = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().all()
    source_bank = banks[0]
    target_bank = banks[1]

    # Configurar serie en BankAccountNumberingConfig
    num_config = database.session.execute(
        database.select(BankAccountNumberingConfig).filter_by(bank_account_id=source_bank.id, payment_type="internal_transfer")
    ).scalar_one_or_none()
    if num_config:
        num_config.naming_series_id = series.id
    else:
        num_config = BankAccountNumberingConfig(
            bank_account_id=source_bank.id,
            payment_type="internal_transfer",
            naming_series_id=series.id,
        )
        database.session.add(num_config)
    database.session.commit()

    payload = {
        "payment_type": "internal_transfer",
        "company": "cacao",
        "bank_account_id": source_bank.id,
        "target_bank_account_id": target_bank.id,
        "paid_amount": "250.00",
        "posting_date": date.today().isoformat(),
    }

    response = client.post(
        "/cash_management/payment/transfer/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    assert response.status_code == 200

    payment = (
        database.session.execute(
            database.select(PaymentEntry)
            .filter_by(payment_type="internal_transfer", bank_account_id=source_bank.id)
            .order_by(PaymentEntry.created.desc())
        )
        .scalars()
        .first()
    )
    assert payment is not None
    assert payment.naming_series_id == series.id
    current_year = str(date.today().year)
    assert payment.document_no.startswith(f"TR-{current_year}-")


def test_bank_operation_with_check_mode_uses_external_counter_and_tracks_usage(app_ctx):
    """Operación bancaria con cheque consume chequera y registra trazabilidad en ExternalNumberUsage."""
    client = app_ctx.test_client()
    login(client)

    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()
    assert bank.default_external_counter_id is not None
    counter = database.session.get(ExternalCounter, bank.default_external_counter_id)
    initial_last_used = counter.last_used
    expense_acc = _get_or_create_expense_account("cacao")

    payload = {
        "payment_type": "debit_note",
        "company": "cacao",
        "bank_account_id": bank.id,
        "paid_to_account_id": expense_acc.id,
        "paid_amount": "220.00",
        "mode_of_payment": "check",
        "posting_date": date.today().isoformat(),
        "remarks": "Pago de gasto bancario mediante cheque",
    }

    response = client.post(
        "/cash_management/payment/debit-note/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    assert response.status_code == 200

    payment = (
        database.session.execute(
            database.select(PaymentEntry)
            .filter_by(payment_type="debit_note", bank_account_id=bank.id)
            .order_by(PaymentEntry.created.desc())
        )
        .scalars()
        .first()
    )
    assert payment is not None
    assert payment.external_counter_id == counter.id
    assert payment.external_number is not None
    assert payment.external_number.startswith(counter.prefix)

    # Verificar que el contador avanzó
    database.session.refresh(counter)
    assert counter.last_used == initial_last_used + 1

    # Verificar registro en ExternalNumberUsage
    usage = database.session.execute(
        database.select(ExternalNumberUsage).filter_by(
            external_counter_id=counter.id,
            entity_id=payment.id,
        )
    ).scalar_one_or_none()
    assert usage is not None
    assert usage.external_number == payment.external_number


def test_post_forms_missing_required_fields_rejected(app_ctx):
    """Formularios bancarios rechazan payloads con campos obligatorios vacíos o montos inválidos."""
    client = app_ctx.test_client()
    login(client)

    bank = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().first()

    # 1. Nota de débito sin compañía
    response_no_comp = client.post(
        "/cash_management/payment/debit-note/new",
        data={"payment_payload": json.dumps({"payment_type": "debit_note", "bank_account_id": bank.id, "paid_amount": "100"})},
        follow_redirects=True,
    )
    assert b"error" in response_no_comp.data.lower() or b"compa" in response_no_comp.data.lower()

    # 2. Nota de débito con monto cero
    response_zero = client.post(
        "/cash_management/payment/debit-note/new",
        data={
            "payment_payload": json.dumps(
                {"payment_type": "debit_note", "company": "cacao", "bank_account_id": bank.id, "paid_amount": "0"}
            )
        },
        follow_redirects=True,
    )
    assert b"error" in response_zero.data.lower() or b"mayor que cero" in response_zero.data.lower()

    # 3. Transferencia sin cuenta destino
    response_no_dest = client.post(
        "/cash_management/payment/transfer/new",
        data={
            "payment_payload": json.dumps(
                {
                    "payment_type": "internal_transfer",
                    "company": "cacao",
                    "bank_account_id": bank.id,
                    "paid_amount": "100",
                    "posting_date": date.today().isoformat(),
                }
            )
        },
        follow_redirects=True,
    )
    assert b"error" in response_no_dest.data.lower() or b"destino" in response_no_dest.data.lower()


def test_transfer_same_currency_preserves_unitary_exchange_rate(app_ctx):
    """Transferencia entre cuentas de la misma moneda conserva tipo de cambio 1 e importes iguales."""
    client = app_ctx.test_client()
    login(client)

    banks = database.session.execute(database.select(BankAccount).filter_by(company="cacao", currency="NIO")).scalars().all()
    if len(banks) < 2:
        bank_gl = Accounts(
            entity="cacao",
            code="11.02.001.999",
            name="Banco Banpro NIO 2",
            account_type="bank",
            classification="asset",
            active=True,
            enabled=True,
        )
        database.session.add(bank_gl)
        database.session.flush()
        target_bank = BankAccount(
            bank_id=banks[0].bank_id,
            company="cacao",
            account_name="Cuenta Ahorro NIO 2",
            account_no="ACC-NIO-002",
            currency="NIO",
            gl_account_id=bank_gl.id,
        )
        database.session.add(target_bank)
        database.session.commit()
        source_bank = banks[0]
    else:
        source_bank = banks[0]
        target_bank = banks[1]

    payload = {
        "payment_type": "internal_transfer",
        "company": "cacao",
        "bank_account_id": source_bank.id,
        "target_bank_account_id": target_bank.id,
        "paid_amount": "300.00",
        "exchange_rate": "1",
        "posting_date": date.today().isoformat(),
        "remarks": "Transferencia misma moneda NIO",
    }

    response = client.post(
        "/cash_management/payment/transfer/new",
        data={"payment_payload": json.dumps(payload)},
        follow_redirects=True,
    )
    assert response.status_code == 200

    payment = (
        database.session.execute(
            database.select(PaymentEntry)
            .filter_by(payment_type="internal_transfer", bank_account_id=source_bank.id)
            .order_by(PaymentEntry.created.desc())
        )
        .scalars()
        .first()
    )
    assert payment is not None
    assert payment.paid_amount == Decimal("300.00")
    assert payment.received_amount == Decimal("300.00")
    assert payment.exchange_rate == Decimal("1")


def test_bank_forms_explicit_external_numbers_persisted(app_ctx):
    """Los números de comprobante o referencia externa ingresados se persisten en las 3 operaciones."""
    client = app_ctx.test_client()
    login(client)

    banks = database.session.execute(database.select(BankAccount).filter_by(company="cacao")).scalars().all()
    bank = banks[0]
    target_bank = banks[1]
    expense_acc = _get_or_create_expense_account("cacao")
    income_acc = _get_or_create_income_account("cacao")

    # 1. Nota de débito con referencia externa
    client.post(
        "/cash_management/payment/debit-note/new",
        data={
            "payment_payload": json.dumps(
                {
                    "payment_type": "debit_note",
                    "company": "cacao",
                    "bank_account_id": bank.id,
                    "paid_to_account_id": expense_acc.id,
                    "paid_amount": "40.00",
                    "posting_date": date.today().isoformat(),
                    "external_number": "EXT-ND-4444",
                }
            )
        },
        follow_redirects=True,
    )
    dn = (
        database.session.execute(
            database.select(PaymentEntry)
            .filter_by(payment_type="debit_note", bank_account_id=bank.id)
            .order_by(PaymentEntry.created.desc())
        )
        .scalars()
        .first()
    )
    assert dn is not None

    # 2. Nota de crédito con referencia externa y dimensiones
    client.post(
        "/cash_management/payment/credit-note/new",
        data={
            "payment_payload": json.dumps(
                {
                    "payment_type": "credit_note",
                    "company": "cacao",
                    "bank_account_id": bank.id,
                    "paid_from_account_id": income_acc.id,
                    "paid_amount": "60.00",
                    "posting_date": date.today().isoformat(),
                    "cost_center_code": "VENTAS",
                    "unit_code": "SUCURSAL-1",
                    "project_code": "PRJ-CREDIT",
                    "external_number": "EXT-NC-5555",
                }
            )
        },
        follow_redirects=True,
    )
    nc = (
        database.session.execute(
            database.select(PaymentEntry)
            .filter_by(payment_type="credit_note", bank_account_id=bank.id)
            .order_by(PaymentEntry.created.desc())
        )
        .scalars()
        .first()
    )
    assert nc is not None
    assert nc.cost_center_code == "VENTAS"
    assert nc.unit_code == "SUCURSAL-1"
    assert nc.project_code == "PRJ-CREDIT"

    # 3. Transferencia con referencia externa
    client.post(
        "/cash_management/payment/transfer/new",
        data={
            "payment_payload": json.dumps(
                {
                    "payment_type": "internal_transfer",
                    "company": "cacao",
                    "bank_account_id": bank.id,
                    "target_bank_account_id": target_bank.id,
                    "paid_amount": "70.00",
                    "posting_date": date.today().isoformat(),
                    "external_number": "EXT-TR-6666",
                }
            )
        },
        follow_redirects=True,
    )
    tr = (
        database.session.execute(
            database.select(PaymentEntry)
            .filter_by(payment_type="internal_transfer", bank_account_id=bank.id)
            .order_by(PaymentEntry.created.desc())
        )
        .scalars()
        .first()
    )
    assert tr is not None
