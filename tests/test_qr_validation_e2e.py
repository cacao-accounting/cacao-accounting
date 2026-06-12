# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

from datetime import date
from decimal import Decimal
import pytest
from cacao_accounting import create_app
from cacao_accounting.database import (
    Accounts,
    CacaoConfig,
    ComprobanteContable,
    ComprobanteContableDetalle,
    Entity,
    PaymentEntry,
    PaymentReference,
    SalesInvoice,
    SalesInvoiceItem,
    database,
)
from cacao_accounting.contabilidad.journal_service import submit_journal
from cacao_accounting.printing import admin_routes
from cacao_accounting.printing.models import PublicDocumentValidation
from cacao_accounting.printing.settings import (
    DEFAULT_VALIDATION_BASE_URL,
    external_validation_base_url,
    external_validation_enabled,
    save_external_validation_settings,
)
from cacao_accounting.printing.validation import VALIDATION_STATUS_INVALID, VALIDATION_STATUS_VALID, ValidationService


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SECRET_KEY": "test",
            "WTF_CSRF_ENABLED": False,
        }
    )
    with app.app_context():
        database.create_all()
        yield app
        database.session.remove()
        database.drop_all()


def test_qr_validation_lifecycle(app):
    """Test the full lifecycle of QR validation for a document."""
    with app.app_context():
        # 1. Setup company and accounts
        entity = Entity(
            code="VALTEST",
            company_name="Validation Test Co",
            tax_id="J123456789",
            currency="NIO",
            enabled=True,
        )
        database.session.add(entity)

        acc1 = Accounts(entity="VALTEST", code="1101", name="Cash", account_type="asset", enabled=True)
        acc2 = Accounts(
            entity="VALTEST",
            code="4101",
            name="Income",
            account_type="income",
            enabled=True,
        )
        database.session.add_all([acc1, acc2])
        database.session.commit()

        # 2. Create a journal entry (Draft)
        journal = ComprobanteContable(
            entity="VALTEST",
            date=date(2026, 5, 26),
            status="draft",
            voucher_type="journal_entry",
            transaction_currency="NIO",
        )
        database.session.add(journal)
        database.session.flush()

        l1 = ComprobanteContableDetalle(
            transaction_id=journal.id,
            account="1101",
            value=Decimal("100"),
            order=1,
            entity="VALTEST",
            transaction="journal_entry",
        )
        l2 = ComprobanteContableDetalle(
            transaction_id=journal.id,
            account="4101",
            value=Decimal("-100"),
            order=2,
            entity="VALTEST",
            transaction="journal_entry",
        )
        database.session.add_all([l1, l2])
        database.session.commit()

        # Check: No validation record should exist for draft
        val_rec = database.session.execute(
            database.select(PublicDocumentValidation).filter_by(document_id=journal.id)
        ).scalar_one_or_none()
        assert val_rec is None

        # 3. Submit journal (Trigger token generation)
        submit_journal(journal.id)

        val_rec = database.session.execute(
            database.select(PublicDocumentValidation).filter_by(document_id=journal.id)
        ).scalar_one_or_none()

        assert val_rec is not None
        assert val_rec.document_status == "posted"
        assert val_rec.public_token is not None
        token = val_rec.public_token

        # 4. Verify public validation
        val_service = ValidationService()
        result = val_service.validate_token(token)
        assert result["status"] == VALIDATION_STATUS_VALID
        assert result["record"].id == val_rec.id
        assert result["data"]["company_name"] == "Validation Test Co"
        assert result["data"]["line_count"] == 2
        assert result["data"]["grand_total"] == 200.0

        # 5. Simulate document alteration
        l1.value = Decimal("200")
        database.session.commit()

        # Public validation should now detect inconsistency
        result = val_service.validate_token(token)
        assert result["status"] == VALIDATION_STATUS_INVALID

        # 6. Global configuration check
        cfg = CacaoConfig(key="external_document_validation_enabled", value="false")
        database.session.add(cfg)
        database.session.commit()

        with app.test_client() as client:
            resp = client.get(f"/public/validate_doc/{token}")
            assert resp.status_code == 403
            assert b"Validation unavailable" in resp.data

        # Re-enable and check success
        cfg.value = "true"
        database.session.commit()
        resp = client.get(f"/public/validate_doc/{token}")
        assert resp.status_code == 200
        assert b"Validation Test Co" in resp.data


def test_managed_external_validation_settings(app):
    """Validation settings are stored in CacaoConfig with a safe URL fallback."""
    with app.app_context():
        assert external_validation_enabled() is True
        assert external_validation_base_url() == DEFAULT_VALIDATION_BASE_URL

        save_external_validation_settings(False, "https://validacion.example.test/")

        assert external_validation_enabled() is False
        assert external_validation_base_url() == "https://validacion.example.test"


def test_validation_settings_admin_screen(app):
    """Admin screen updates external validation settings in CacaoConfig."""
    with app.app_context():
        with app.test_request_context("/admin/print-templates/settings", method="GET"):
            response = admin_routes.validation_settings.__wrapped__()
            assert isinstance(response, str)
            assert len(response) > 0
        with app.test_request_context(
            "/admin/print-templates/settings",
            method="POST",
            data={
                "external_document_validation_enabled": "on",
                "external_document_validation_base_url": "https://docs.example.test/",
            },
        ):
            save = admin_routes.validation_settings.__wrapped__()
            assert save.status_code == 302

    with app.app_context():
        assert external_validation_enabled() is True
        assert external_validation_base_url() == "https://docs.example.test"


def test_validation_settings_admin_screen_uses_default_fallback(app):
    """Empty URL in admin screen uses hardcoded default fallback."""
    with app.app_context():
        save_external_validation_settings(True, "https://persisted.example.test")
        with app.test_request_context(
            "/admin/print-templates/settings",
            method="POST",
            data={},
        ):
            save = admin_routes.validation_settings.__wrapped__()
            assert save.status_code == 302

    with app.app_context():
        assert external_validation_enabled() is False
        assert external_validation_base_url() == DEFAULT_VALIDATION_BASE_URL


def test_draft_never_updates_existing_validation(app):
    """A document returning to draft must not refresh a previous public token."""
    with app.app_context():
        entity = Entity(code="DRAFT", company_name="Draft Co", tax_id="J000", currency="NIO", enabled=True)
        database.session.add(entity)
        journal = ComprobanteContable(
            id="draft-journal",
            entity="DRAFT",
            date=date(2026, 5, 26),
            status="draft",
            voucher_type="journal_entry",
            transaction_currency="NIO",
        )
        database.session.add(journal)
        existing = PublicDocumentValidation(
            public_token="draft-token",
            company_code="DRAFT",
            document_type="journal_entry",
            document_id=journal.id,
            document_number="JE-1",
            document_date=date(2026, 5, 26),
            document_status="posted",
            validation_hash="old-hash",
            is_enabled=True,
        )
        database.session.add(existing)
        database.session.commit()

        result = ValidationService().update_validation_from_document(journal)

        database.session.refresh(existing)
        assert result is None
        assert existing.validation_hash == "old-hash"
        assert existing.document_status == "posted"


def test_line_summary_for_invoice_and_payment_aliases(app):
    """Canonical validation data uses real line tables and payment aliases."""
    with app.app_context():
        entity = Entity(code="LINES", company_name="Lines Co", tax_id="J111", currency="NIO", enabled=True)
        database.session.add(entity)
        invoice = SalesInvoice(
            id="si-lines",
            company="LINES",
            posting_date=date(2026, 5, 26),
            document_no="SI-1",
            docstatus=1,
            document_type="sales_credit_note",
            transaction_currency="NIO",
        )
        database.session.add(invoice)
        database.session.add_all(
            [
                SalesInvoiceItem(sales_invoice_id=invoice.id, item_code="A", qty=1, amount=Decimal("10.00")),
                SalesInvoiceItem(sales_invoice_id=invoice.id, item_code="B", qty=2, amount=Decimal("30.00")),
            ]
        )
        transfer = PaymentEntry(
            id="pay-transfer",
            company="LINES",
            posting_date=date(2026, 5, 26),
            document_no="BT-1",
            docstatus=1,
            payment_type="internal_transfer",
            currency="NIO",
            paid_amount=Decimal("75.00"),
        )
        database.session.add(transfer)
        database.session.add(
            PaymentReference(
                payment_id=transfer.id,
                reference_type="bank_transfer",
                reference_id="target",
                allocated_amount=Decimal("75.00"),
            )
        )
        database.session.commit()

        service = ValidationService()
        invoice_data = service.extract_document_data(invoice)
        transfer_data = service.extract_document_data(transfer)

        assert invoice_data is not None
        assert invoice_data["document_type"] == "sales_credit_note"
        assert invoice_data["line_count"] == 2
        assert invoice_data["grand_total"] == 40.0
        assert transfer_data is not None
        assert transfer_data["document_type"] == "bank_transfer"
        assert transfer_data["line_count"] == 1
        assert transfer_data["grand_total"] == 75.0
