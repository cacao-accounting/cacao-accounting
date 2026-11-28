# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1808: la numeración bancaria usa la serie propia de cada transacción."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import inspect, select

from cacao_accounting.bancos.services import _resolve_payment_numbering
from cacao_accounting.database import (
    Bank,
    BankAccount,
    BankAccountNumberingConfig,
    NamingSeries,
    PaymentEntry,
    Sequence,
    SeriesSequenceMap,
    User,
    database,
)
from cacao_accounting.document_identifiers import assign_document_identifier

PAYMENT_SERIES = (
    ("pay", "bank_payment"),
    ("receive", "bank_receipt"),
    ("internal_transfer", "bank_transfer"),
    ("debit_note", "bank_debit_note"),
    ("credit_note", "bank_credit_note"),
)


def _cliente(env):
    """Autentica al administrador de la aplicación aislada."""
    client = env.app.test_client()
    with env.app.app_context():
        admin_id = database.session.execute(select(User).filter_by(user="admin")).scalar_one().id
    with client.session_transaction() as session:
        session["_user_id"] = str(admin_id)
        session["_fresh"] = True
    return client


@pytest.mark.parametrize(("payment_type", "entity_type"), PAYMENT_SERIES)
def test_defaults_incompatibles_se_ignoran_y_config_especifica_se_usa(entorno_contable_aislado, payment_type, entity_type):
    """Una serie payment_entry legada no bloquea la numeración del tipo bancario."""
    env = entorno_contable_aislado
    suffix = uuid4().hex[:6]
    with env.app.app_context():
        legacy = NamingSeries(
            name=f"Legacy {suffix}",
            entity_type="payment_entry",
            company="cacao",
            prefix_template="LEG-",
            is_active=True,
        )
        correct = NamingSeries(
            name=f"Correcta {entity_type} {suffix}",
            entity_type=entity_type,
            company="cacao",
            prefix_template=f"{entity_type.upper()}-",
            is_active=True,
        )
        bank = Bank(name=f"Banco {suffix}", is_active=True)
        database.session.add_all([legacy, correct, bank])
        database.session.flush()
        sequence = Sequence(name=f"Secuencia {entity_type} {suffix}")
        database.session.add(sequence)
        database.session.flush()
        database.session.add(
            SeriesSequenceMap(
                naming_series_id=correct.id,
                sequence_id=sequence.id,
                priority=0,
            )
        )
        account = BankAccount(
            bank_id=bank.id,
            company="cacao",
            account_name=f"Cuenta {suffix}",
            account_no=f"CTA-{suffix}",
            currency="NIO",
            default_naming_series_id=legacy.id,
            is_active=True,
        )
        database.session.add(account)
        database.session.commit()
        account_id = str(inspect(account).identity[0])
        legacy_id = legacy.id
        correct_id = correct.id

        payment = PaymentEntry(
            company="cacao",
            bank_account_id=account_id,
            payment_type=payment_type,
            docstatus=0,
        )
        series, _counter = _resolve_payment_numbering({}, payment, "transfer")
        assert series is None

        config = BankAccountNumberingConfig(
            bank_account_id=account_id,
            payment_type=payment_type,
            naming_series_id=legacy_id,
            use_external_counter=False,
        )
        database.session.add(config)
        database.session.commit()
        series, _counter = _resolve_payment_numbering({}, payment, "transfer")
        assert series is None

        config.naming_series_id = correct_id
        database.session.commit()
        series, _counter = _resolve_payment_numbering({}, payment, "transfer")
        assert series == correct_id

        database.session.add(payment)
        database.session.flush()
        assign_document_identifier(
            document=payment,
            entity_type=entity_type,
            posting_date_raw="2026-05-15",
            naming_series_id=series,
        )
        assert payment.naming_series_id == correct_id
        assert payment.document_no is not None
        assert payment.document_no.startswith(f"{entity_type.upper()}-")
        database.session.commit()


@pytest.mark.parametrize(
    ("path", "entity_type"),
    (
        ("/cash_management/payment/debit-note/new", "bank_debit_note"),
        ("/cash_management/payment/credit-note/new", "bank_credit_note"),
        ("/cash_management/payment/transfer/new", "bank_transfer"),
    ),
)
def test_formularios_bancarios_filtran_por_entity_type_real(entorno_contable_aislado, path, entity_type):
    """Los selectores de nota y transferencia no ofrecen series payment_entry."""
    response = _cliente(entorno_contable_aislado).get(path)

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert entity_type in html
    assert 'entity_type: "payment_entry"' not in html
    assert '"entity_type": "payment_entry"' not in html


def test_formulario_de_pago_actualiza_la_serie_al_cambiar_el_tipo(entorno_contable_aislado):
    """Pago y cobro filtran bank_payment/bank_receipt y recargan al cambiar el tipo."""
    response = _cliente(entorno_contable_aislado).get("/cash_management/payment/new")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "bank_payment" in html
    assert "bank_receipt" in html
    assert 'id="payment_type"' in html
    assert 'filterSources: ["#company_val", "#payment_type"]' in html
    assert 'entity_type: function() { return "payment_entry" }' not in html
