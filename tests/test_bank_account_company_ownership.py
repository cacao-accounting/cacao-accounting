"""Cross-company dimensions are rejected at journal and payment boundaries."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cacao_accounting.api.line_import import (
    _validate_bank_account_reference,
    _validate_project_reference,
    _validate_unit_reference,
)
from cacao_accounting.contabilidad.journal_service import (
    JournalValidationError,
    _normalize_journal_payload,
    _validate_journal_line,
)
from cacao_accounting.contabilidad.posting_service import (
    PostingError,
    _validate_manual_journal_dimensions,
    post_payment_entry,
)
from cacao_accounting.database import Bank, BankAccount, Entity, GLEntry, PaymentEntry, Project, Unit, User, database
from cacao_accounting.document_flow.payment import _resolve_payment_target_gl_accounts
from cacao_accounting.document_flow.service import DocumentFlowError
from cacao_accounting.approval_engine import approved_execution
from cacao_accounting.internal_control_service import audit_actor


def _foreign_company() -> None:
    """Ensure a second company exists for ownership isolation scenarios."""
    if database.session.query(Entity).filter_by(code="alpha").one_or_none() is not None:
        return
    database.session.add(
        Entity(
            code="alpha",
            name="Alpha",
            company_name="Alpha SA",
            tax_id=f"J-{uuid4().hex[:8]}",
            currency="NIO",
            enabled=True,
            status="default",
        )
    )
    database.session.flush()


def _foreign_reference(dimension: str) -> str:
    """Create a valid bank or analytical reference owned by a second company."""
    _foreign_company()
    suffix = uuid4().hex[:8]
    if dimension == "bank_account":
        bank = Bank(name=f"Banco {suffix}")
        database.session.add(bank)
        database.session.flush()
        reference = BankAccount(company="alpha", bank_id=bank.id, account_name=f"Cuenta {suffix}")
    elif dimension == "unit":
        reference = Unit(code=f"U{suffix}", name="Sucursal Alpha", entity="alpha")
    else:
        reference = Project(code=f"P{suffix}", name="Proyecto Alpha", entity="alpha")
    database.session.add(reference)
    database.session.flush()
    return str(reference.id) if dimension == "bank_account" else reference.code


@pytest.mark.parametrize("company", ["cacao", None])
def test_pago_destino_rechaza_cuenta_sin_propiedad_verificable(entorno_contable, company):
    """A payment rejects a foreign bank account or missing company context."""
    with entorno_contable.app.app_context():
        account_id = _foreign_reference("bank_account")

        with pytest.raises(DocumentFlowError, match="cuenta bancaria"):
            _resolve_payment_target_gl_accounts(company, {"payment_type": "receive", "bank_account_id": account_id})


@pytest.mark.parametrize("dimension", ["bank_account", "unit", "project"])
def test_diario_rechaza_dimensiones_ajenas_al_validar_linea(entorno_contable, dimension):
    """Manual journal draft validation enforces company ownership per line."""
    with entorno_contable.app.app_context():
        value = _foreign_reference(dimension)
        journal = _normalize_journal_payload(
            {
                "company": "cacao",
                "posting_date": "2026-05-15",
                "transaction_currency": "NIO",
                "lines": [
                    {"account": "1101", "debit": "10", "credit": "0", dimension: value},
                    {"account": "4101", "debit": "0", "credit": "10"},
                ],
            }
        )

        with pytest.raises(JournalValidationError, match="compañía del comprobante"):
            _validate_journal_line("cacao", journal.lines[0], {})


@pytest.mark.parametrize("dimension", ["bank_account", "unit", "project"])
def test_importacion_de_diario_rechaza_dimension_ajena(entorno_contable, dimension):
    """The import validator reports foreign references on the affected row."""
    with entorno_contable.app.app_context():
        value = _foreign_reference(dimension)
        row = {dimension: value}
        errors: list[dict] = []
        if dimension == "bank_account":
            _validate_bank_account_reference(row, row.copy(), 2, "cacao", errors)
        elif dimension == "unit":
            _validate_unit_reference(row, 2, "cacao", errors)
        else:
            _validate_project_reference(row, 2, "cacao", errors)

        assert len(errors) == 1
        assert errors[0]["row"] == 2
        assert errors[0]["field"] == dimension


@pytest.mark.parametrize("dimension", ["bank_account", "unit", "project"])
def test_posting_defense_de_diario_rechaza_dimension_ajena(entorno_contable, dimension):
    """The GL posting boundary blocks legacy or bypassed invalid journal lines."""
    with entorno_contable.app.app_context():
        value = _foreign_reference(dimension)
        field = {"bank_account": "bank_account_id", "unit": "unit", "project": "project"}[dimension]

        with pytest.raises(PostingError, match="compañía del comprobante"):
            _validate_manual_journal_dimensions("cacao", [SimpleNamespace(**{field: value})])


@pytest.mark.parametrize("field", ["bank_account_id", "target_bank_account_id"])
def test_post_payment_entry_rechaza_cuenta_ajena_antes_de_generar_gl(entorno_contable, field):
    """Posted payments and transfers cannot publish a foreign bank dimension."""
    with entorno_contable.app.app_context():
        account_id = _foreign_reference("bank_account")
        payment_data = {
            "company": "cacao",
            "payment_type": "pay" if field == "bank_account_id" else "internal_transfer",
            "posting_date": date(2026, 5, 15),
            "docstatus": 1,
            "paid_amount": Decimal("10"),
            "received_amount": Decimal("10"),
            "bank_account_id": None,
            "target_bank_account_id": None,
        }
        payment_data[field] = account_id
        payment = PaymentEntry(**payment_data)
        database.session.add(payment)
        database.session.flush()
        actor_id = str(database.session.query(User.id).filter_by(user="admin").scalar())

        with audit_actor(actor_id, "Administrador"), approved_execution(payment, actor_id):
            with pytest.raises(PostingError, match="compañía del pago"):
                post_payment_entry(payment)

        assert database.session.query(GLEntry).filter_by(voucher_id=payment.id, voucher_type="payment_entry").count() == 0
