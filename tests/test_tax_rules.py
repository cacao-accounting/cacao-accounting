"""Tests for persisted fiscal rules and admin CRUD."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest
from flask import Flask

from cacao_accounting import create_app
from cacao_accounting.accounting_engine.document_builders import _build_payment_context, _document_tax_rules
from cacao_accounting.compras import _validate_purchase_tax_template
from cacao_accounting.config import configuracion
from cacao_accounting.fiscal_persistence_service import (
    build_tax_rule_contexts_from_snapshot,
    load_document_fiscal_lines,
    persist_document_fiscal_snapshot,
)
from cacao_accounting.fiscal_preview_service import fiscal_preview, get_fiscal_document_profile
from cacao_accounting.tax_rule_service import build_tax_rule_contexts


@pytest.fixture()
def app_ctx() -> Iterator[Flask]:
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SECRET_KEY": "test-tax-rules-secret",
        }
    )
    with app.app_context():
        from cacao_accounting.database import CacaoConfig, Currency, Entity, Modules, User, database

        database.create_all()
        database.session.add_all(
            [
                CacaoConfig(key="SETUP_COMPLETE", value="True"),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Currency(code="USD", name="US Dollar", decimals=2, active=True, default=False),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="admin", default=True, enabled=True),
                User(user="admin", name="Admin", password=b"x", classification="admin", active=True),
            ]
        )
        database.session.commit()
        yield app


@pytest.fixture()
def client(app_ctx: Flask):
    return app_ctx.test_client()


def _login_admin(client) -> None:
    from cacao_accounting.database import User

    admin = User.query.filter_by(user="admin").first()
    assert admin is not None
    with client.session_transaction() as session:
        session["_user_id"] = admin.id
        session["_fresh"] = True


@pytest.mark.parametrize(
    ("document_type", "payment_type", "expected_profile", "applies_to"),
    [
        ("purchase_request", None, "purchase_request", "purchase"),
        ("purchase_order", None, "purchase_order", "purchase"),
        ("purchase_receipt", None, "purchase_receipt", "purchase"),
        ("purchase_invoice", None, "purchase_invoice", "purchase"),
        ("import_landed_cost", None, "import_landed_cost", "purchase"),
        ("sales_request", None, "sales_request", "sales"),
        ("sales_order", None, "sales_order", "sales"),
        ("delivery_note", None, "delivery_note", "sales"),
        ("sales_invoice", None, "sales_invoice", "sales"),
        ("stock_entry", None, "stock_entry", "purchase"),
        ("payment_entry", "pay", "payment_entry", "purchase"),
        ("payment_entry", "receive", "payment_entry", "sales"),
        ("payment_entry", "debit_note", "bank_debit_note", "purchase"),
        ("payment_entry", "credit_note", "bank_credit_note", "sales"),
        ("payment_entry", "internal_transfer", "bank_transfer", "both"),
    ],
)
def test_fiscal_preview_supports_each_mvp_document_profile(
    app_ctx: Flask,
    document_type: str,
    payment_type: str | None,
    expected_profile: str,
    applies_to: str,
) -> None:
    """Each fiscal MVP profile must produce a server-side preview."""
    preview = fiscal_preview(
        {
            "document_type": document_type,
            "payment_type": payment_type,
            "company": "cacao",
            "currency": "NIO",
            "posting_date": "2026-05-01",
            "party_id": "PARTY-001",
            "purpose": "material_receipt",
            "purchase_invoice_id": "PINV-001",
            "lines": [{"uid": "LINE-001", "item_code": "ITEM-001", "qty": "2", "rate": "10"}],
        }
    )

    assert preview["profile"]["document_type"] == expected_profile
    assert preview["profile"]["applies_to"] == applies_to
    assert preview["summary"]["subtotal"] == "20"


def test_fiscal_preview_rejects_unknown_document_profile(app_ctx: Flask) -> None:
    """Unsupported document types must not silently receive a fiscal profile."""
    with pytest.raises(ValueError, match="no soportado"):
        fiscal_preview({"document_type": "unknown_document", "company": "cacao", "posting_date": "2026-05-01"})


def test_purchase_tax_template_validation_uses_template_type_and_applies_to(app_ctx: Flask) -> None:
    """Purchase templates require buying type and purchase/both applicability."""
    from cacao_accounting.database import TaxTemplate, database

    valid = TaxTemplate(
        name="Compras ambas",
        company="cacao",
        template_type="buying",
        currency="NIO",
        is_active=True,
    )
    selling = TaxTemplate(
        name="Ventas",
        company="cacao",
        template_type="selling",
        is_active=True,
    )
    database.session.add_all([valid, selling])
    database.session.commit()

    _validate_purchase_tax_template("cacao", valid.id, "NIO")
    with pytest.raises(ValueError, match="no corresponde a compras"):
        _validate_purchase_tax_template("cacao", selling.id, "NIO")


def test_admin_tax_rule_crud(client) -> None:
    """The admin module should create, edit and delete fiscal rules."""
    from cacao_accounting.database import TaxRule, database

    _login_admin(client)

    response = client.post(
        "/settings/tax-rules",
        data={
            "name": "IVA Venta",
            "company": "cacao",
            "concept": "IVA",
            "applies_to": "sales",
            "level": "transaction",
            "tax_type": "tax",
            "calculation_method": "percentage",
            "rate": "15",
            "amount": "0",
            "base_mode": "goods",
            "include_concepts": "goods",
            "exclude_concepts": "",
            "sequence": "10",
            "accounting_treatment": "separate_tax_account",
            "recognition_event": "invoice",
            "currency": "USD",
            "country": "NI",
            "affects_document_total": "on",
            "is_active": "on",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    created_rule = database.session.execute(database.select(TaxRule)).scalar_one()
    assert created_rule.name == "IVA Venta"


    assert created_rule.include_concepts == "goods"

    response = client.post(
        f"/settings/tax-rules/{created_rule.id}/edit",
        data={
            "name": "IVA Venta Actualizado",
            "company": "cacao",
            "concept": "IVA",
            "applies_to": "sales",
            "level": "transaction",
            "tax_type": "tax",
            "calculation_method": "percentage",
            "rate": "13",
            "amount": "0",
            "base_mode": "goods",
            "include_concepts": "goods, ISC",
            "exclude_concepts": "",
            "sequence": "20",
            "accounting_treatment": "separate_tax_account",
            "recognition_event": "invoice",
            "currency": "USD",
            "country": "NI",
            "affects_document_total": "on",
            "participates_in_next_base": "on",
            "is_active": "on",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    database.session.refresh(created_rule)
    assert created_rule.name == "IVA Venta Actualizado"
    assert created_rule.sequence == 20
    assert created_rule.participates_in_next_base is True

    response = client.post(f"/settings/tax-rules/{created_rule.id}/delete", follow_redirects=True)
    assert response.status_code == 200
    assert database.session.get(TaxRule, created_rule.id) is None


def test_admin_ledger_mapping_rule_create_and_deactivate(client) -> None:
    """System administrators can manage auditable multi-ledger mappings."""
    from cacao_accounting.database import Accounts, Book, LedgerMappingRule, database

    _login_admin(client)
    source_account = Accounts(
        id="ACC-MAP-SOURCE",
        entity="cacao",
        code="ACC-MAP-SOURCE",
        name="Cuenta origen",
        active=True,
        enabled=True,
        group=False,
    )
    target_account = Accounts(
        id="ACC-MAP-TARGET",
        entity="cacao",
        code="ACC-MAP-TARGET",
        name="Cuenta destino",
        active=True,
        enabled=True,
        group=False,
    )
    database.session.add_all(
        [
            Book(code="MAP-PRIMARY", name="Principal", entity="cacao", is_primary=True),
            Book(code="MAP-IFRS", name="IFRS", entity="cacao", is_primary=False),
            source_account,
            target_account,
        ]
    )
    database.session.commit()
    response = client.post(
        "/settings/ledger-mapping-rules",
        data={
            "source_book": "MAP-PRIMARY",
            "target_book": "MAP-IFRS",
            "source_account_id": source_account.id,
            "target_account_id": target_account.id,
            "description": "Depreciación IFRS",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    rule = database.session.execute(database.select(LedgerMappingRule)).scalar_one()
    assert rule.is_active is True
    assert b"Reglas de Mapeo entre Libros" in response.data
    response = client.post(f"/settings/ledger-mapping-rules/{rule.id}/deactivate", follow_redirects=True)
    assert response.status_code == 200
    database.session.refresh(rule)
    assert rule.is_active is False


def test_ledger_mapping_rule_transforms_secondary_ledger_entries(app_ctx: Flask) -> None:
    """Posting maps only the configured account in the secondary ledger."""
    from cacao_accounting.contabilidad.ledger_mapping_service import apply_ledger_mappings, create_ledger_mapping_rule
    from cacao_accounting.database import Accounts, Book, GLEntry, database

    source_account = Accounts(
        id="ACC-MAP-POSTING-SOURCE",
        entity="cacao",
        code="ACC-MAP-POSTING-SOURCE",
        name="Cuenta origen posting",
        active=True,
        enabled=True,
        group=False,
    )
    target_account = Accounts(
        id="ACC-MAP-POSTING-TARGET",
        entity="cacao",
        code="ACC-MAP-POSTING-TARGET",
        name="Cuenta destino posting",
        active=True,
        enabled=True,
        group=False,
    )
    primary_book = Book(code="POST-PRIMARY", name="Principal", entity="cacao", is_primary=True)
    secondary_book = Book(code="POST-IFRS", name="IFRS", entity="cacao", is_primary=False)
    database.session.add_all([primary_book, secondary_book, source_account, target_account])
    database.session.commit()
    create_ledger_mapping_rule(
        source_book=primary_book.code,
        target_book=secondary_book.code,
        source_account_id=source_account.id,
        target_account_id=target_account.id,
    )

    entry = GLEntry(
        posting_date=date(2026, 5, 1),
        company="cacao",
        ledger_id=secondary_book.id,
        account_id=source_account.id,
        account_code=source_account.code,
        debit=Decimal("10.00"),
        credit=Decimal("0"),
    )

    mapped = apply_ledger_mappings([entry])

    assert mapped == [entry]
    assert entry.account_id == target_account.id
    assert entry.account_code == target_account.code
    assert entry.debit == Decimal("10.00")
    assert entry.credit == Decimal("0")


def test_tax_rule_service_builds_contexts_from_db(app_ctx: Flask) -> None:
    """Persisted fiscal rules should be converted into engine contexts."""
    from cacao_accounting.database import TaxRule, database

    database.session.add(
        TaxRule(
            company="cacao",
            name="DAI Importación",
            applies_to="purchase",
            level="transaction",
            concept="DAI",
            tax_type="tax",
            calculation_method="percentage",
            rate=Decimal("5"),
            amount=Decimal("0"),
            base_mode="accumulated",
            include_concepts="goods, Flete",
            sequence=5,
            accounting_treatment="capitalizable_inventory_cost",
            recognition_event="purchase_invoice_confirmed",
            currency="USD",
            valid_from=date(2026, 1, 1),
            is_active=True,
        )
    )
    database.session.commit()

    contexts = build_tax_rule_contexts(
        company="cacao",
        applies_to="purchase",
        currency="USD",
        at_date=date(2026, 5, 1),
        recognition_event="purchase_invoice_confirmed",
    )

    assert len(contexts) == 1
    assert contexts[0].concept == "DAI"
    assert contexts[0].include_concepts == ["goods", "Flete"]
    assert contexts[0].accounting_treatment == "capitalizable_inventory_cost"


def test_fiscal_preview_reuses_canonical_rules_after_recalculation(app_ctx: Flask) -> None:
    """Repeated previews must not degrade cascaded persisted rule metadata."""
    from cacao_accounting.database import TaxRule, database

    database.session.add_all(
        [
            TaxRule(
                company="cacao",
                name="DAI Importación",
                applies_to="purchase",
                level="transaction",
                concept="DAI",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("5"),
                amount=Decimal("0"),
                base_mode="goods",
                sequence=10,
                accounting_treatment="capitalizable_inventory_cost",
                recognition_event="purchase_invoice_confirmed",
                currency="USD",
                valid_from=date(2026, 1, 1),
                is_active=True,
                participates_in_next_base=True,
            ),
            TaxRule(
                company="cacao",
                name="IVA Importación",
                applies_to="purchase",
                level="transaction",
                concept="IVA",
                tax_type="tax",
                calculation_method="percentage",
                rate=Decimal("15"),
                amount=Decimal("0"),
                base_mode="accumulated",
                include_concepts="goods, DAI",
                sequence=20,
                accounting_treatment="separate_tax_account",
                recognition_event="purchase_invoice_confirmed",
                currency="USD",
                valid_from=date(2026, 1, 1),
                is_active=True,
            ),
        ]
    )
    database.session.commit()
    payload = {
        "document_type": "purchase_invoice",
        "company": "cacao",
        "currency": "USD",
        "posting_date": "2026-05-19",
        "party_type": "supplier",
        "party_id": "SUPP-DEMO",
        "lines": [{"uid": "L-1", "item_code": "ITEM-1", "item_name": "Item 1", "qty": 1, "rate": 100, "amount": 100}],
    }

    first_preview = fiscal_preview(payload)
    second_preview = fiscal_preview({**payload, "tax_lines": first_preview["tax_lines"]})

    assert [line["concept"] for line in second_preview["tax_lines"]] == ["DAI", "IVA"]
    assert second_preview["tax_lines"][1]["base_amount"] == "105.00"
    assert second_preview["tax_lines"][1]["amount"] == "15.75"


def test_fiscal_preview_appends_manual_charges_to_canonical_rules(app_ctx: Flask) -> None:
    """Manual fiscal lines from the form should coexist with configured rules."""
    from cacao_accounting.database import TaxRule, database

    database.session.add(
        TaxRule(
            company="cacao",
            name="IVA Compra",
            applies_to="purchase",
            level="transaction",
            concept="IVA",
            tax_type="tax",
            calculation_method="percentage",
            rate=Decimal("15"),
            amount=Decimal("0"),
            base_mode="goods",
            sequence=10,
            accounting_treatment="separate_tax_account",
            recognition_event="purchase_invoice_confirmed",
            currency="USD",
            valid_from=date(2026, 1, 1),
            is_active=True,
        )
    )
    database.session.commit()

    preview = fiscal_preview(
        {
            "document_type": "purchase_invoice",
            "company": "cacao",
            "currency": "USD",
            "posting_date": "2026-05-19",
            "party_type": "supplier",
            "party_id": "SUPP-DEMO",
            "lines": [{"uid": "L-1", "item_code": "ITEM-1", "item_name": "Item 1", "qty": 1, "rate": 100, "amount": 100}],
            "tax_lines": [
                {
                    "source_rule_id": "MANUAL-FREIGHT",
                    "manual": True,
                    "concept": "Flete",
                    "type": "charge",
                    "calculation_method": "manual",
                    "amount": "12.50",
                    "accounting_treatment": "capitalizable_inventory_cost",
                    "allocation_method": "by_value",
                    "affects_document_total": True,
                }
            ],
        }
    )

    assert [line["concept"] for line in preview["tax_lines"]] == ["IVA", "Flete"]
    assert preview["tax_lines"][1]["manual"] is True
    assert preview["tax_lines"][1]["allocation_method"] == "by_value"
    assert preview["summary"]["document_tax_total"] == "27.50"
    assert preview["summary"]["capitalizable_tax_total"] == "12.50"


def test_receive_payment_profile_uses_collection_event(app_ctx: Flask) -> None:
    """Normal incoming payments must resolve to the collection fiscal profile."""
    profile = get_fiscal_document_profile("payment_entry", "receive")

    assert profile.document_type == "payment_entry"
    assert profile.applies_to == "sales"
    assert profile.recognition_event == "collection_confirmed"


def test_document_tax_snapshot_is_persisted_and_loaded_for_invoice(app_ctx: Flask) -> None:
    """Persisted fiscal lines must be loaded as immutable rules for invoice posting."""
    from cacao_accounting.database import PurchaseInvoice, database

    invoice = PurchaseInvoice(company="cacao", posting_date=date(2026, 5, 1), document_type="purchase_invoice", docstatus=0)
    database.session.add(invoice)
    database.session.flush()
    persist_document_fiscal_snapshot(
        company="cacao",
        document_type="purchase_invoice",
        document_id=invoice.id,
        currency="USD",
        tax_lines=[
            {
                "source_rule_id": "MANUAL-SNAPSHOT-001",
                "manual": True,
                "concept": "IVA",
                "type": "tax",
                "base_amount": "100.00",
                "rate": "15",
                "amount": "15.00",
                "accounting_treatment": "separate_tax_account",
                "account_id": "",
                "affects_inventory": False,
                "included_in_price": False,
                "notes": "snapshot line",
            }
        ],
        tax_summary={"subtotal": "100.00", "document_tax_total": "15.00", "grand_total": "115.00"},
    )
    rules = _document_tax_rules(
        invoice,
        [],
        company="cacao",
        applies_to="purchase",
        event_type="purchase_invoice_confirmed",
    )
    assert len(rules) == 1
    assert rules[0].calculation_method == "manual"
    assert rules[0].amount == Decimal("15.00")
    assert rules[0].concept == "IVA"
    persisted_lines = load_document_fiscal_lines("purchase_invoice", invoice.id)
    assert persisted_lines[0].account_id is None


def test_sales_invoice_tax_snapshot_is_persisted_for_sales_posting(app_ctx: Flask) -> None:
    """Sales invoices retain canonical fiscal lines for their posting event."""
    from cacao_accounting.database import SalesInvoice, database

    invoice = SalesInvoice(company="cacao", posting_date=date(2026, 5, 1), document_type="sales_invoice", docstatus=0)
    database.session.add(invoice)
    database.session.flush()
    persist_document_fiscal_snapshot(
        company="cacao",
        document_type="sales_invoice",
        document_id=invoice.id,
        currency="NIO",
        tax_lines=[
            {
                "source_rule_id": "MANUAL-SALES-IVA-001",
                "manual": True,
                "concept": "IVA",
                "type": "tax",
                "base_amount": "100.00",
                "rate": "15",
                "amount": "15.00",
                "accounting_treatment": "separate_tax_account",
                "account_id": "",
                "affects_inventory": False,
                "included_in_price": False,
                "notes": "snapshot venta",
            }
        ],
        tax_summary={"subtotal": "100.00", "document_tax_total": "15.00", "grand_total": "115.00"},
    )

    rules = _document_tax_rules(
        invoice,
        [],
        company="cacao",
        applies_to="sales",
        event_type="sales_invoice_confirmed",
    )

    assert len(rules) == 1
    assert rules[0].concept == "IVA"
    assert rules[0].amount == Decimal("15.00")
    persisted_lines = load_document_fiscal_lines("sales_invoice", invoice.id)
    assert persisted_lines[0].notes == "snapshot venta"


def test_collection_tax_snapshot_is_persisted_for_payment_posting(app_ctx: Flask) -> None:
    """Incoming payments retain fiscal lines for the collection event."""
    from cacao_accounting.database import PaymentEntry, database

    payment = PaymentEntry(
        company="cacao",
        posting_date=date(2026, 5, 1),
        payment_type="receive",
        received_amount=Decimal("98.00"),
        base_received_amount=Decimal("98.00"),
        party_type="customer",
        party_id="",
        docstatus=0,
    )
    database.session.add(payment)
    database.session.flush()
    persist_document_fiscal_snapshot(
        company="cacao",
        document_type="payment_entry",
        document_id=payment.id,
        currency="NIO",
        tax_lines=[
            {
                "source_rule_id": "MANUAL-COLLECTION-WHT-001",
                "manual": True,
                "concept": "Retención",
                "type": "withholding",
                "base_amount": "100.00",
                "rate": "2",
                "amount": "2.00",
                "accounting_treatment": "separate_tax_account",
                "account_id": "",
                "affects_inventory": False,
                "included_in_price": False,
                "notes": "snapshot cobro",
            }
        ],
        tax_summary={"subtotal": "100.00", "document_tax_total": "-2.00", "grand_total": "98.00"},
    )

    context = _build_payment_context(payment)

    assert context is not None
    assert len(context.tax_rules) == 1
    assert context.tax_rules[0].tax_type == "withholding"
    assert context.tax_rules[0].amount == Decimal("2.00")
    persisted_lines = load_document_fiscal_lines("payment_entry", payment.id)
    assert persisted_lines[0].notes == "snapshot cobro"


def test_document_tax_snapshot_uses_canonical_rule_values(app_ctx: Flask) -> None:
    """Browser values cannot replace a stored rule's amount, rate, or account."""
    from cacao_accounting.database import Accounts, PurchaseInvoice, TaxRule, database

    account = Accounts(
        id="ACC-TAX-CANONICAL",
        entity="cacao",
        code="ACC-TAX-CANONICAL",
        name="Impuesto canónico",
        active=True,
        enabled=True,
        group=False,
    )
    rule = TaxRule(
        company="cacao",
        name="IVA canónico",
        concept="IVA",
        tax_type="tax",
        calculation_method="percentage",
        rate=Decimal("15"),
        amount=Decimal("0"),
        base_mode="goods",
        accounting_treatment="separate_tax_account",
        recognition_event="purchase_invoice_confirmed",
        account_id=account.id,
        is_active=True,
    )
    invoice = PurchaseInvoice(company="cacao", posting_date=date(2026, 5, 3), document_type="purchase_invoice")
    database.session.add_all([account, rule, invoice])
    database.session.flush()

    persist_document_fiscal_snapshot(
        company="cacao",
        document_type="purchase_invoice",
        document_id=invoice.id,
        currency="NIO",
        tax_lines=[
            {
                "source_rule_id": rule.id,
                "concept": "Manipulado",
                "base_amount": "999",
                "rate": "99",
                "amount": "999",
                "account_id": "ACCOUNT-ATTACK",
                "rule_snapshot": {"rate": "999", "account_id": "ACCOUNT-ATTACK"},
            }
        ],
        tax_summary={"subtotal": "999", "grand_total": "1998"},
        server_subtotal=Decimal("100"),
        server_total=Decimal("115"),
    )

    persisted_line = load_document_fiscal_lines("purchase_invoice", invoice.id)[0]
    assert persisted_line.concept == "IVA"
    assert persisted_line.base_amount == Decimal("100.000000000")
    assert persisted_line.rate == Decimal("15.000000000")
    assert persisted_line.amount == Decimal("15.0000")
    assert persisted_line.account_id == account.id
    assert '"rate": "15"' in persisted_line.rule_snapshot_json


def test_manual_tax_snapshot_rejects_cross_company_account(app_ctx: Flask) -> None:
    """Manual fiscal lines cannot post to an account outside their company."""
    from cacao_accounting.database import Accounts, Entity, PurchaseInvoice, database

    other_entity = Entity(
        code="cafe",
        name="Cafe",
        company_name="Cafe",
        tax_id="J0002",
        currency="NIO",
        enabled=True,
    )
    other_account = Accounts(
        id="ACC-TAX-CAFE",
        entity="cafe",
        code="ACC-TAX-CAFE",
        name="Impuesto Cafe",
        active=True,
        enabled=True,
        group=False,
    )
    database.session.add_all([other_entity, other_account])
    invoice = PurchaseInvoice(company="cacao", posting_date=date(2026, 5, 4), document_type="purchase_invoice")
    database.session.add(invoice)
    database.session.flush()

    with pytest.raises(ValueError, match="pertenecer a la compañía"):
        persist_document_fiscal_snapshot(
            company="cacao",
            document_type="purchase_invoice",
            document_id=invoice.id,
            currency="NIO",
            tax_lines=[
                {
                    "source_rule_id": "MANUAL-FREIGHT",
                    "manual": True,
                    "concept": "Flete",
                    "amount": "10",
                    "account_id": other_account.id,
                }
            ],
            tax_summary={"subtotal": "100", "grand_total": "110"},
        )


def test_document_tax_snapshot_derives_inventory_impact_from_treatment(app_ctx: Flask) -> None:
    """Legacy inventory flags cannot override the accounting treatment."""
    from cacao_accounting.database import PurchaseInvoice, database

    invoice = PurchaseInvoice(company="cacao", posting_date=date(2026, 5, 2), document_type="purchase_invoice", docstatus=0)
    database.session.add(invoice)
    database.session.flush()
    persist_document_fiscal_snapshot(
        company="cacao",
        document_type="purchase_invoice",
        document_id=invoice.id,
        currency="USD",
        tax_lines=[
            {
                "source_rule_id": "MANUAL-EXPENSE-001",
                "manual": True,
                "concept": "Flete no capitalizable",
                "type": "charge",
                "amount": "20.00",
                "accounting_treatment": "expense",
                "affects_inventory": True,
            }
        ],
        tax_summary={"subtotal": "100.00", "document_tax_total": "20.00", "grand_total": "120.00"},
    )

    persisted_line = load_document_fiscal_lines("purchase_invoice", invoice.id)[0]
    assert persisted_line.affects_inventory is False


def test_payment_context_uses_persisted_fiscal_snapshot(app_ctx: Flask) -> None:
    """Payment posting context must consume persisted fiscal payload instead of recalculating."""
    from cacao_accounting.database import PaymentEntry, database

    payment = PaymentEntry(
        company="cacao",
        posting_date=date(2026, 5, 1),
        payment_type="pay",
        paid_amount=Decimal("120.00"),
        base_paid_amount=Decimal("120.00"),
        party_type="supplier",
        party_id="",
        docstatus=0,
    )
    database.session.add(payment)
    database.session.flush()
    persist_document_fiscal_snapshot(
        company="cacao",
        document_type="payment_entry",
        document_id=payment.id,
        currency="USD",
        tax_lines=[
            {
                "source_rule_id": "MANUAL-WHT-001",
                "manual": True,
                "concept": "RETENCION",
                "type": "withholding",
                "base_amount": "120.00",
                "rate": "2",
                "amount": "2.40",
                "accounting_treatment": "separate_tax_account",
                "account_id": None,
                "affects_inventory": False,
                "affects_document_total": True,
                "included_in_price": False,
            }
        ],
        tax_summary={"subtotal": "120.00", "document_tax_total": "2.40", "grand_total": "122.40"},
    )
    context = _build_payment_context(payment)
    assert context is not None
    assert len(context.tax_rules) == 1
    assert context.tax_rules[0].calculation_method == "manual"
    assert context.tax_rules[0].amount == Decimal("2.40")
    loaded_lines = build_tax_rule_contexts_from_snapshot(
        document_type="payment_entry",
        document_id=payment.id,
        recognition_event="payment_confirmed",
    )
    assert len(loaded_lines) == 1
