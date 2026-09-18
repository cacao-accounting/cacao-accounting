"""Regresión de aislamiento para borradores de factura de compra."""

from decimal import Decimal
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask_babel import Babel, force_locale

from cacao_accounting.compras import purchase_invoice_draft_service as draft_service
from cacao_accounting.compras.purchase_invoice_draft_service import (
    PurchaseInvoiceDraftCommand,
    PurchaseInvoiceDraftError,
    PurchaseInvoiceDraftLine,
    _assert_expected_total,
    _build_draft_invoice,
    _persist_draft_lines,
    _relate_line_to_source,
    _resolve_idempotent_replay,
    _validate_idempotency_replay,
    _validate_line,
    _validate_sources,
    create_purchase_invoice_draft,
)
from cacao_accounting.database import CompanyParty, Entity, Party, PurchaseInvoice, PurchaseInvoiceItem
from cacao_accounting.document_flow import DocumentFlowError
from sqlalchemy import select

TRANSLATIONS_DIR = Path(__file__).resolve().parent.parent / "cacao_accounting" / "translations"


@pytest.mark.parametrize(
    ("existing_company", "existing_supplier", "command_company", "command_supplier"),
    [
        ("company-a", "supplier-a", "company-b", "supplier-a"),
        ("company-a", "supplier-a", "company-a", "supplier-b"),
    ],
)
def test_idempotency_replay_rejects_cross_tenant_or_supplier_invoice(
    existing_company: str,
    existing_supplier: str,
    command_company: str,
    command_supplier: str,
) -> None:
    """Una clave global no puede convertirse en acceso a otra factura."""
    existing = cast(PurchaseInvoice, SimpleNamespace(company=existing_company, supplier_id=existing_supplier))
    command = cast(PurchaseInvoiceDraftCommand, SimpleNamespace(company_id=command_company, supplier_id=command_supplier))

    with pytest.raises(PurchaseInvoiceDraftError) as exc_info:
        _validate_idempotency_replay(existing, command)

    assert exc_info.value.code == "IDEMPOTENCY_KEY_CONFLICT"


def test_idempotency_replay_returns_same_tenant_and_supplier_invoice() -> None:
    """Un retry legítimo conserva la semántica idempotente original."""
    existing = cast(PurchaseInvoice, SimpleNamespace(company="company-a", supplier_id="supplier-a"))
    command = cast(PurchaseInvoiceDraftCommand, SimpleNamespace(company_id="company-a", supplier_id="supplier-a"))

    assert _validate_idempotency_replay(existing, command) is existing


def test_non_po_invoice_requires_supplier_permission_without_receipt() -> None:
    """NON_PO drafts require both no-order and no-receipt supplier permissions."""
    command = cast(
        PurchaseInvoiceDraftCommand,
        SimpleNamespace(
            matching_mode="NON_PO_INVOICE",
            purchase_order_id=None,
            purchase_receipt_id=None,
        ),
    )
    settings = cast(
        CompanyParty,
        SimpleNamespace(
            allow_purchase_invoice_without_order=True,
            allow_purchase_invoice_without_receipt=False,
        ),
    )

    with pytest.raises(PurchaseInvoiceDraftError) as exc_info:
        _validate_sources(command, settings)

    assert exc_info.value.code == "RECEIPT_REQUIRED"


def test_non_po_invoice_accepts_both_supplier_permissions() -> None:
    """NON_PO drafts are accepted when both source bypasses are configured."""
    command = cast(
        PurchaseInvoiceDraftCommand,
        SimpleNamespace(
            matching_mode="NON_PO_INVOICE",
            purchase_order_id=None,
            purchase_receipt_id=None,
        ),
    )
    settings = cast(
        CompanyParty,
        SimpleNamespace(
            allow_purchase_invoice_without_order=True,
            allow_purchase_invoice_without_receipt=True,
        ),
    )

    _validate_sources(command, settings)


def test_non_purchasable_line_translates_template_before_interpolation() -> None:
    """El código de artículo se interpola después de resolver el catálogo inglés."""
    app = Flask(__name__)
    app.config["BABEL_TRANSLATION_DIRECTORIES"] = str(TRANSLATIONS_DIR)
    Babel(app, locale_selector=lambda: "es")
    query = MagicMock()
    query.where.return_value = query
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = None
    database_stub = SimpleNamespace(
        select=MagicMock(return_value=query),
        session=SimpleNamespace(execute=MagicMock(return_value=query_result)),
    )
    line = PurchaseInvoiceDraftLine(
        item_code="CACAO-01",
        quantity=Decimal("1"),
        rate=Decimal("1"),
        amount=Decimal("1"),
    )

    with (
        app.test_request_context(),
        force_locale("en"),
        patch("cacao_accounting.compras.purchase_invoice_draft_service.database", database_stub),
        pytest.raises(PurchaseInvoiceDraftError) as exc_info,
    ):
        _validate_line(line)

    assert exc_info.value.code == "LINE_UNRESOLVED"
    assert str(exc_info.value) == "Item 'CACAO-01' is not purchasable."


def test_assert_expected_total_accepts_none_and_matching():
    """An absent observed total is ignored; a matching one passes."""
    _assert_expected_total(cast(PurchaseInvoiceDraftCommand, SimpleNamespace(expected_total=None)), Decimal("200"))
    _assert_expected_total(cast(PurchaseInvoiceDraftCommand, SimpleNamespace(expected_total=Decimal("100"))), Decimal("100"))


def test_assert_expected_total_rejects_mismatch():
    """A divergence beyond the cent tolerance is a math mismatch."""
    with pytest.raises(PurchaseInvoiceDraftError) as exc_info:
        _assert_expected_total(
            cast(PurchaseInvoiceDraftCommand, SimpleNamespace(expected_total=Decimal("100"))), Decimal("200")
        )
    assert exc_info.value.code == "MATH_MISMATCH"


def test_resolve_idempotent_replay_without_key_returns_none():
    """No idempotency key short-circuits the replay lookup."""
    command = cast(PurchaseInvoiceDraftCommand, SimpleNamespace(idempotency_key=None))
    assert _resolve_idempotent_replay(command) is None


def test_resolve_idempotent_replay_returns_existing_invoice():
    """A key that matches the same tenant and supplier returns the document."""
    existing = cast(PurchaseInvoice, SimpleNamespace(company="company-a", supplier_id="supplier-a"))
    command = cast(
        PurchaseInvoiceDraftCommand,
        SimpleNamespace(idempotency_key="KEY", company_id="company-a", supplier_id="supplier-a"),
    )
    database_stub = SimpleNamespace(
        select=select, session=SimpleNamespace(execute=lambda _query: SimpleNamespace(scalar_one_or_none=lambda: existing))
    )
    with patch("cacao_accounting.compras.purchase_invoice_draft_service.database", database_stub):
        assert _resolve_idempotent_replay(command) is existing


def test_resolve_idempotent_replay_conflict_raises():
    """A key owned by another tenant must never return that document."""
    existing = cast(PurchaseInvoice, SimpleNamespace(company="company-b", supplier_id="supplier-a"))
    command = cast(
        PurchaseInvoiceDraftCommand,
        SimpleNamespace(idempotency_key="KEY", company_id="company-a", supplier_id="supplier-a"),
    )
    database_stub = SimpleNamespace(
        select=select, session=SimpleNamespace(execute=lambda _query: SimpleNamespace(scalar_one_or_none=lambda: existing))
    )
    with patch("cacao_accounting.compras.purchase_invoice_draft_service.database", database_stub):
        with pytest.raises(PurchaseInvoiceDraftError) as exc_info:
            _resolve_idempotent_replay(command)
    assert exc_info.value.code == "IDEMPOTENCY_KEY_CONFLICT"


def test_relate_line_to_source_requires_receipt_item_for_three_way():
    """A 3-way line without a receipt item is unresolved."""
    command = cast(PurchaseInvoiceDraftCommand, SimpleNamespace(matching_mode="THREE_WAY_MATCH", purchase_receipt_id="REC"))
    line = cast(PurchaseInvoiceDraftLine, SimpleNamespace(purchase_receipt_item_id=None))
    with pytest.raises(PurchaseInvoiceDraftError) as exc_info:
        _relate_line_to_source(
            cast(PurchaseInvoice, SimpleNamespace(id="INV")),
            cast(PurchaseInvoiceItem, SimpleNamespace(id="LI", uom="UN")),
            line,
            command,
        )
    assert exc_info.value.code == "LINE_UNRESOLVED"


def test_relate_line_to_source_creates_receipt_relation():
    """A 3-way line creates the receipt-to-invoice relation."""
    calls: list[dict] = []
    command = cast(PurchaseInvoiceDraftCommand, SimpleNamespace(matching_mode="THREE_WAY_MATCH", purchase_receipt_id="REC"))
    line = cast(
        PurchaseInvoiceDraftLine,
        SimpleNamespace(purchase_receipt_item_id="RI", quantity=Decimal("1"), rate=Decimal("2"), amount=Decimal("2")),
    )
    with patch(
        "cacao_accounting.compras.purchase_invoice_draft_service.create_document_relation", lambda **kw: calls.append(kw)
    ):
        _relate_line_to_source(
            cast(PurchaseInvoice, SimpleNamespace(id="INV")),
            cast(PurchaseInvoiceItem, SimpleNamespace(id="LI", uom="UN")),
            line,
            command,
        )
    assert calls[0]["source_type"] == "purchase_receipt"
    assert calls[0]["source_id"] == "REC"
    assert calls[0]["target_id"] == "INV"
    assert calls[0]["target_item_id"] == "LI"


def test_relate_line_to_source_requires_order_item_for_two_way():
    """A 2-way line without an order item is unresolved."""
    command = cast(PurchaseInvoiceDraftCommand, SimpleNamespace(matching_mode="TWO_WAY_MATCH", purchase_order_id="PO"))
    line = cast(PurchaseInvoiceDraftLine, SimpleNamespace(purchase_order_item_id=None))
    with pytest.raises(PurchaseInvoiceDraftError) as exc_info:
        _relate_line_to_source(
            cast(PurchaseInvoice, SimpleNamespace(id="INV")),
            cast(PurchaseInvoiceItem, SimpleNamespace(id="LI", uom="UN")),
            line,
            command,
        )
    assert exc_info.value.code == "LINE_UNRESOLVED"


def test_relate_line_to_source_creates_order_relation():
    """A 2-way line creates the order-to-invoice relation with its values."""
    calls: list[dict] = []
    command = cast(PurchaseInvoiceDraftCommand, SimpleNamespace(matching_mode="TWO_WAY_MATCH", purchase_order_id="PO"))
    line = cast(
        PurchaseInvoiceDraftLine,
        SimpleNamespace(purchase_order_item_id="OI", quantity=Decimal("3"), rate=Decimal("2.5"), amount=Decimal("7.5")),
    )
    with patch(
        "cacao_accounting.compras.purchase_invoice_draft_service.create_document_relation",
        lambda **kwargs: calls.append(kwargs),
    ):
        _relate_line_to_source(
            cast(PurchaseInvoice, SimpleNamespace(id="INV")),
            cast(PurchaseInvoiceItem, SimpleNamespace(id="LI", uom="BOX")),
            line,
            command,
        )

    assert calls == [
        {
            "source_type": "purchase_order",
            "source_id": "PO",
            "source_item_id": "OI",
            "target_type": "purchase_invoice",
            "target_id": "INV",
            "target_item_id": "LI",
            "qty": Decimal("3"),
            "uom": "BOX",
            "rate": Decimal("2.5"),
            "amount": Decimal("7.5"),
        }
    ]


def test_persist_draft_lines_preserves_values_for_each_line():
    """Every resolved line is persisted with converted amounts and related."""
    added: list[SimpleNamespace] = []
    relations: list[tuple[SimpleNamespace, SimpleNamespace, SimpleNamespace, SimpleNamespace]] = []
    command = cast(
        PurchaseInvoiceDraftCommand,
        SimpleNamespace(
            matching_mode="NON_PO_INVOICE",
            lines=(
                SimpleNamespace(
                    quantity=Decimal("2"), rate=Decimal("4"), amount=Decimal("8"), uom=None, expense_account_id="EXP-1"
                ),
                SimpleNamespace(
                    quantity=Decimal("1"), rate=Decimal("5"), amount=Decimal("5"), uom="BOX", expense_account_id=None
                ),
            ),
        ),
    )
    invoice = SimpleNamespace(id="INV")
    validated = [
        SimpleNamespace(code="ITEM-1", name="Primer ítem", purchase_uom="EA", default_uom="UNIT"),
        SimpleNamespace(code="ITEM-2", name="Segundo ítem", purchase_uom=None, default_uom="UNIT"),
    ]

    def build_line(**values):
        line = SimpleNamespace(id=f"LI-{len(added) + 1}", **values)
        return line

    database_stub = SimpleNamespace(session=SimpleNamespace(add=added.append, flush=lambda: None))
    with (
        patch("cacao_accounting.compras.purchase_invoice_draft_service.database", database_stub),
        patch("cacao_accounting.compras.purchase_invoice_draft_service.PurchaseInvoiceItem", build_line),
        patch(
            "cacao_accounting.compras.purchase_invoice_draft_service._relate_line_to_source",
            lambda *args: relations.append(args),
        ),
    ):
        _persist_draft_lines(invoice, command, validated, Decimal("1.5"))

    assert [line.item_code for line in added] == ["ITEM-1", "ITEM-2"]
    assert [line.uom for line in added] == ["EA", "BOX"]
    assert [line.base_rate for line in added] == [Decimal("6.0000"), Decimal("7.5000")]
    assert [line.base_amount for line in added] == [Decimal("12.0000"), Decimal("7.5000")]
    assert [line.expense_account_id for line in added] == ["EXP-1", None]
    assert [(relation[1].id, relation[2].amount) for relation in relations] == [
        ("LI-1", Decimal("8")),
        ("LI-2", Decimal("5")),
    ]


def test_build_draft_invoice_sets_totals_and_identifier():
    """The header carries totals, base amounts and the assigned identifier."""
    added: list = []
    identifiers: list[dict] = []
    command = cast(
        PurchaseInvoiceDraftCommand,
        SimpleNamespace(
            company_id="cacao",
            supplier_id="SUP",
            supplier_invoice_no=" F-1 ",
            idempotency_key=None,
            posting_date=date(2026, 1, 1),
            transaction_currency="NIO",
            purchase_order_id=None,
            purchase_receipt_id=None,
            tax_template_id=None,
            remarks="rem",
        ),
    )
    database_stub = SimpleNamespace(session=SimpleNamespace(add=added.append, flush=lambda: None))
    with (
        patch("cacao_accounting.compras.purchase_invoice_draft_service.database", database_stub),
        patch(
            "cacao_accounting.compras.purchase_invoice_draft_service.assign_document_identifier",
            lambda **kw: identifiers.append(kw),
        ),
    ):
        invoice = _build_draft_invoice(
            command,
            "user-1",
            cast(Entity, SimpleNamespace(currency="NIO")),
            cast(Party, SimpleNamespace(name="Proveedor")),
            Decimal("1"),
            Decimal("100"),
            Decimal("15"),
            Decimal("115"),
        )

    assert invoice.supplier_invoice_no == "F-1"
    assert invoice.supplier_name == "Proveedor"
    assert invoice.total == Decimal("100")
    assert invoice.tax_total == Decimal("15")
    assert invoice.grand_total == Decimal("115")
    assert invoice.base_grand_total == Decimal("115")
    assert invoice.outstanding_amount == Decimal("115")
    assert invoice.docstatus == 0
    assert added == [invoice]
    assert identifiers[0]["document"] is invoice


def _orchestration_monkeypatch(monkeypatch, invoice):
    """Patch the creation pipeline dependencies to isolate the orchestrator."""
    monkeypatch.setattr(draft_service, "_require_actor_can_create", lambda _actor, _company: None)
    monkeypatch.setattr(
        draft_service,
        "_validate_header",
        lambda _command: (SimpleNamespace(currency="NIO"), SimpleNamespace(name="Proveedor"), SimpleNamespace()),
    )
    monkeypatch.setattr(draft_service, "_resolve_idempotent_replay", lambda _command: None)
    monkeypatch.setattr(draft_service, "_validate_duplicate", lambda _command: None)
    monkeypatch.setattr(draft_service, "_validate_sources", lambda _command, _settings: None)
    monkeypatch.setattr(
        draft_service,
        "_validate_line",
        lambda _line: SimpleNamespace(code="IT", name="Item", purchase_uom=None, default_uom="UN"),
    )
    monkeypatch.setattr(draft_service, "_exchange_rate", lambda _company, _command: Decimal("1"))
    monkeypatch.setattr(draft_service, "_resolve_tax_total", lambda _command, _total: Decimal("15"))
    monkeypatch.setattr(draft_service, "_build_draft_invoice", lambda *_args, **_kwargs: invoice)
    monkeypatch.setattr(draft_service, "refresh_source_caches_for_target", lambda *_args: None)
    monkeypatch.setattr(draft_service, "log_create", lambda _invoice: None)


def _draft_command(**overrides):
    values = {
        "company_id": "cacao",
        "supplier_id": "SUP",
        "lines": (SimpleNamespace(amount=Decimal("100")),),
        "matching_mode": "NON_PO_INVOICE",
        "expected_total": None,
        "idempotency_key": None,
    }
    values.update(overrides)
    return cast(PurchaseInvoiceDraftCommand, SimpleNamespace(**values))


@pytest.mark.parametrize(("commit", "transactions"), [(True, [True]), (False, [])])
def test_create_draft_orchestrates_and_commits(monkeypatch, commit, transactions):
    """The happy path persists lines, refreshes caches, logs and commits."""
    invoice = SimpleNamespace(id="INV-1")
    persisted: list = []
    commits: list[bool] = []
    _orchestration_monkeypatch(monkeypatch, invoice)
    monkeypatch.setattr(draft_service, "_persist_draft_lines", lambda inv, _command, _validated, _rate: persisted.append(inv))
    monkeypatch.setattr(
        draft_service,
        "database",
        SimpleNamespace(session=SimpleNamespace(commit=lambda: commits.append(True), rollback=lambda: commits.append(False))),
    )

    result = create_purchase_invoice_draft(_draft_command(), "user-1", commit=commit)

    assert result is invoice
    assert persisted == [invoice]
    assert commits == transactions


def test_create_draft_rolls_back_on_domain_error(monkeypatch):
    """A domain error rolls back the transaction when commit is enabled."""
    _orchestration_monkeypatch(monkeypatch, SimpleNamespace(id="INV-1"))

    def _raise(_actor, _company):
        raise PurchaseInvoiceDraftError("AUTHORIZATION_REVOKED", "x")

    monkeypatch.setattr(draft_service, "_require_actor_can_create", _raise)
    rolled: list[bool] = []
    monkeypatch.setattr(
        draft_service,
        "database",
        SimpleNamespace(session=SimpleNamespace(commit=lambda: None, rollback=lambda: rolled.append(True))),
    )

    with pytest.raises(PurchaseInvoiceDraftError):
        create_purchase_invoice_draft(_draft_command(), "user-1")

    assert rolled == [True]


def test_create_draft_does_not_rollback_without_commit(monkeypatch):
    """A caller-managed transaction owns rollback after a domain failure."""
    _orchestration_monkeypatch(monkeypatch, SimpleNamespace(id="INV-1"))

    def raise_authorization_error(_actor, _company):
        """Simulate an authorization failure before persistence starts."""
        raise PurchaseInvoiceDraftError("AUTHORIZATION_REVOKED", "x")

    monkeypatch.setattr(
        draft_service,
        "_require_actor_can_create",
        raise_authorization_error,
    )
    rolled: list[bool] = []
    monkeypatch.setattr(
        draft_service,
        "database",
        SimpleNamespace(session=SimpleNamespace(commit=lambda: None, rollback=lambda: rolled.append(True))),
    )

    with pytest.raises(PurchaseInvoiceDraftError):
        create_purchase_invoice_draft(_draft_command(), "user-1", commit=False)

    assert rolled == []


def test_create_draft_idempotent_replay_does_not_commit(monkeypatch):
    """An idempotent retry returns the original draft without another commit."""
    invoice = SimpleNamespace(id="INV-1")
    _orchestration_monkeypatch(monkeypatch, invoice)
    monkeypatch.setattr(draft_service, "_resolve_idempotent_replay", lambda _command: invoice)
    committed: list[bool] = []
    monkeypatch.setattr(
        draft_service,
        "database",
        SimpleNamespace(session=SimpleNamespace(commit=lambda: committed.append(True), rollback=lambda: None)),
    )

    assert create_purchase_invoice_draft(_draft_command(), "user-1") is invoice
    assert committed == []


def test_create_draft_translates_document_flow_error(monkeypatch):
    """A document flow over-allocation becomes a controlled quantity error."""
    _orchestration_monkeypatch(monkeypatch, SimpleNamespace(id="INV-1"))

    def _raise(*_args, **_kwargs):
        raise DocumentFlowError("exceeds")

    monkeypatch.setattr(draft_service, "_persist_draft_lines", _raise)
    monkeypatch.setattr(
        draft_service,
        "database",
        SimpleNamespace(session=SimpleNamespace(commit=lambda: None, rollback=lambda: None)),
    )

    with pytest.raises(PurchaseInvoiceDraftError) as exc_info:
        create_purchase_invoice_draft(_draft_command(matching_mode="THREE_WAY_MATCH"), "user-1")

    assert exc_info.value.code == "QUANTITY_EXCEEDS_RECEIPT"
