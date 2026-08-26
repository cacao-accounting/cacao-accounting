"""Regression tests for supplier withholding lifecycle and fiscal reporting."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    CacaoConfig,
    Currency,
    Entity,
    Modules,
    Party,
    PaymentEntry,
    User,
    WithholdingCertificate,
    database,
)
from cacao_accounting.reportes.services import get_monthly_withholding_report
from cacao_accounting.withholding_service import create_withholding_certificate


@pytest.fixture()
def withholding_app():
    """Create an isolated schema for withholding lifecycle tests."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "withholding-test-secret",
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                CacaoConfig(key="SETUP_COMPLETE", value="True"),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="J0001", currency="NIO", enabled=True),
                User(user="admin", name="Admin", password=b"x", classification="admin", active=True),
                Modules(module="purchases", default=True, enabled=True),
                Modules(module="accounting", default=True, enabled=True),
            ]
        )
        database.session.commit()
        yield app
        database.session.remove()


def _payment_and_supplier() -> tuple[PaymentEntry, Party]:
    """Persist the minimum supplier payment fixture."""
    supplier = Party(code="SUP-001", name="Proveedor Test", tax_id="J-001", is_supplier=True, is_active=True)
    payment = PaymentEntry(
        company="cacao",
        payment_type="pay",
        party_type="supplier",
        party_name=supplier.name,
        currency="NIO",
        paid_amount=Decimal("980"),
        posting_date=date(2026, 8, 26),
        document_no="PAY-001",
        docstatus=1,
    )
    database.session.add_all([supplier, payment])
    database.session.flush()
    payment.party_id = supplier.id
    database.session.flush()
    return payment, supplier


def test_withholding_certificate_preserves_lines_and_qr_record(withholding_app):
    """A posted supplier withholding creates an immutable printable certificate."""
    from cacao_accounting.printing.models import PublicDocumentValidation

    payment, supplier = _payment_and_supplier()
    settlement = SimpleNamespace(
        gross_settlement_amount=Decimal("1000"),
        withholding_amount=Decimal("20"),
        cash_amount=Decimal("980"),
        settlement_lines=[
            SimpleNamespace(
                type="withholding",
                concept="renta",
                base_amount=Decimal("1000"),
                rate=Decimal("2"),
                amount=Decimal("20"),
                account_id="tax-account",
            )
        ],
    )
    certificate = create_withholding_certificate(payment, settlement)
    assert certificate is not None
    assert certificate.supplier_id == supplier.id
    assert certificate.withheld_amount == Decimal("20")
    assert json.loads(certificate.lines_json)[0]["concept"] == "renta"
    validation = database.session.query(PublicDocumentValidation).filter_by(document_id=certificate.id).one()
    assert validation.document_type == "withholding_certificate"


def test_monthly_withholding_report_is_fiscal_detail(withholding_app):
    """The monthly report includes applied lines and excludes another month."""
    payment, supplier = _payment_and_supplier()
    certificate = WithholdingCertificate(
        company="cacao",
        payment_id=payment.id,
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        certificate_no="RET-001",
        posting_date=date(2026, 8, 26),
        currency="NIO",
        gross_amount=Decimal("1000"),
        withheld_amount=Decimal("20"),
        cash_amount=Decimal("980"),
        lines_json=json.dumps([{"concept": "renta", "base_amount": "1000", "rate": "2", "amount": "20"}]),
        status="issued",
        docstatus=1,
    )
    database.session.add(certificate)
    database.session.commit()
    report = get_monthly_withholding_report("cacao", 2026, 8)
    assert report.total_rows == 1
    assert report.rows[0].values["certificate_no"] == "RET-001"
    assert report.totals["withheld_amount"] == Decimal("20")
    assert get_monthly_withholding_report("cacao", 2026, 7).total_rows == 0
