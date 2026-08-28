"""Regresiones de la política común de anulación del issue #761."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion


@pytest.fixture()
def app_ctx():
    """Aplicación aislada con períodos abiertos para validar cancelaciones."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with app.app_context():
        from cacao_accounting.database import AccountingPeriod, Book, Entity, User, database

        database.create_all()
        database.session.add_all(
            [
                Entity(code="cacao", name="Cacao", company_name="Cacao", tax_id="J0001", currency="NIO"),
                Book(code="PRIMARY", name="Libro principal", entity="cacao", currency="NIO", status="activo", is_primary=True),
                User(user="cancellation-actor", name="Actor", classification="admin", active=True, password=b"x"),
                AccountingPeriod(
                    entity="cacao",
                    name="01-2026",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 1, 1),
                    end=date(2026, 1, 31),
                ),
                AccountingPeriod(
                    entity="cacao",
                    name="02-2026",
                    enabled=True,
                    is_closed=False,
                    start=date(2026, 2, 1),
                    end=date(2026, 2, 28),
                ),
                AccountingPeriod(
                    entity="cacao", name="03-2026", enabled=True, is_closed=True, start=date(2026, 3, 1), end=date(2026, 3, 31)
                ),
            ]
        )
        database.session.commit()
        yield app


def _seed_invoice():
    """Crea una factura y sus dos líneas GL originales dentro de enero."""
    from cacao_accounting.database import (
        AccountingPeriod,
        Accounts,
        Book,
        GLEntry,
        SalesInvoice,
        SalesInvoiceItem,
        User,
        database,
    )

    cash = Accounts(entity="cacao", code="TEST-CASH", name="Caja", active=True, enabled=True, classification="asset")
    income = Accounts(entity="cacao", code="TEST-INCOME", name="Ventas", active=True, enabled=True, classification="income")
    database.session.add_all([cash, income])
    database.session.flush()
    invoice = SalesInvoice(company="cacao", posting_date=date(2026, 1, 3), docstatus=1, grand_total=Decimal("100.00"))
    database.session.add(invoice)
    database.session.flush()
    database.session.add(
        SalesInvoiceItem(
            sales_invoice_id=invoice.id,
            item_code="SERVICE-761",
            item_name="Servicio",
            qty=Decimal("1"),
            rate=Decimal("100"),
            amount=Decimal("100"),
            income_account_id=income.id,
        )
    )
    period = database.session.execute(database.select(AccountingPeriod).filter_by(name="01-2026")).scalar_one()
    book = database.session.execute(database.select(Book).filter_by(code="PRIMARY")).scalar_one()
    database.session.add_all(
        [
            GLEntry(
                company="cacao",
                ledger_id=book.id,
                account_id=cash.id,
                account_code=cash.code,
                posting_date=date(2026, 1, 3),
                debit=Decimal("100"),
                credit=Decimal("0"),
                account_currency="NIO",
                company_currency="NIO",
                exchange_rate=Decimal("1.2345"),
                voucher_type="sales_invoice",
                voucher_id=invoice.id,
                accounting_period_id=period.id,
            ),
            GLEntry(
                company="cacao",
                ledger_id=book.id,
                account_id=income.id,
                account_code=income.code,
                posting_date=date(2026, 1, 3),
                debit=Decimal("0"),
                credit=Decimal("100"),
                account_currency="NIO",
                company_currency="NIO",
                exchange_rate=Decimal("1.2345"),
                voucher_type="sales_invoice",
                voucher_id=invoice.id,
                accounting_period_id=period.id,
            ),
        ]
    )
    database.session.commit()
    actor = database.session.execute(database.select(User).filter_by(user="cancellation-actor")).scalar_one()
    return invoice, actor


def test_cancellation_uses_effective_date_and_preserves_historical_amounts(app_ctx):
    """La contrapartida usa la fecha efectiva y copia la tasa histórica."""
    from cacao_accounting.contabilidad.posting import cancel_document
    from cacao_accounting.database import Book, DocumentTransition, GLEntry, database
    from cacao_accounting.reportes.services import _movement_detail_row_values

    invoice, actor = _seed_invoice()
    cancel_document(
        invoice,
        cancellation_date=date(2026, 1, 20),
        actor_user_id=actor.id,
        reason="Corrección aprobada",
        requested_at=datetime(2026, 1, 10, 9, 30),
    )
    database.session.commit()

    entries = database.session.execute(database.select(GLEntry).where(GLEntry.voucher_id == invoice.id)).scalars().all()
    originals = [entry for entry in entries if not entry.is_reversal]
    reversals = [entry for entry in entries if entry.is_reversal]
    transition = database.session.execute(
        database.select(DocumentTransition).filter_by(source_id=invoice.id, transition_type="cancellation")
    ).scalar_one()

    assert all(entry.is_cancelled for entry in originals)
    assert {entry.posting_date for entry in reversals} == {date(2026, 1, 20)}
    assert {entry.exchange_rate for entry in reversals} == {Decimal("1.234500000")}
    assert all(not entry.is_cancelled for entry in reversals)
    assert transition.posting_date == date(2026, 1, 20)
    assert transition.accounting_period_id is not None
    assert transition.actor_user_id == actor.id
    assert transition.reason == "Corrección aprobada"
    assert transition.requested_at == datetime(2026, 1, 10, 9, 30)
    assert invoice.cancel_reason == "Corrección aprobada"
    audit_row = _movement_detail_row_values(
        originals[0],
        None,
        None,
        None,
        database.session.get(Book, originals[0].ledger_id),
        Decimal("0"),
        False,
        True,
    )
    assert audit_row["cancellation_date"] == date(2026, 1, 20)
    assert audit_row["cancellation_actor"] == actor.id
    assert audit_row["cancellation_reason"] == "Corrección aprobada"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"actor_user_id": None, "reason": "ok"}, "usuario"),
        ({"actor_user_id": "actor", "reason": " "}, "motivo"),
        ({"actor_user_id": "actor", "reason": "ok", "cancellation_date": date(2025, 12, 31)}, "anterior"),
        ({"actor_user_id": "actor", "reason": "ok", "cancellation_date": date(2026, 2, 1)}, "mismo periodo"),
    ],
)
def test_cancellation_policy_rejects_invalid_requests(app_ctx, kwargs, message):
    """Fecha, período, actor y motivo se validan antes de tocar el ledger."""
    from cacao_accounting.contabilidad.posting import PostingError, cancel_document
    from cacao_accounting.database import database

    invoice, actor = _seed_invoice()
    kwargs = {**kwargs, "actor_user_id": actor.id if kwargs.get("actor_user_id") == "actor" else kwargs.get("actor_user_id")}
    with pytest.raises(PostingError, match=message):
        cancel_document(invoice, **kwargs)

    database.session.refresh(invoice)
    assert invoice.docstatus == 1


def test_cancellation_policy_rejects_closed_period(app_ctx):
    """Un período que se cierra antes de ejecutar la operación bloquea la anulación."""
    from cacao_accounting.contabilidad.posting import PostingError, cancel_document
    from cacao_accounting.database import AccountingPeriod, database

    invoice, actor = _seed_invoice()
    period = database.session.execute(database.select(AccountingPeriod).filter_by(name="01-2026")).scalar_one()
    period.is_closed = True
    database.session.commit()

    with pytest.raises(PostingError, match="cerrado"):
        cancel_document(invoice, actor_user_id=actor.id, reason="Corrección")


def test_active_document_relation_blocks_cancellation_but_reverted_relation_does_not(app_ctx):
    """Solo relaciones activas son efectos bloqueantes; las históricas se ignoran."""
    from cacao_accounting.contabilidad.posting import PostingError, cancel_document
    from cacao_accounting.database import DocumentRelation, database

    invoice, actor = _seed_invoice()
    relation = DocumentRelation(
        source_type="sales_invoice",
        source_id=invoice.id,
        target_type="payment_entry",
        target_id="PAYMENT-761",
        company="cacao",
        qty=Decimal("1"),
        relation_type="payment",
        status="active",
    )
    database.session.add(relation)
    database.session.commit()

    with pytest.raises(PostingError, match="efectos activos"):
        cancel_document(invoice, actor_user_id=actor.id, reason="Corrección")

    relation.status = "reverted"
    database.session.commit()
    cancel_document(invoice, actor_user_id=actor.id, reason="Corrección")


def test_cancellation_policy_covers_invalid_metadata_and_period_resolution(app_ctx):
    """La política rechaza estados, actores, fechas y períodos no resolubles."""
    from cacao_accounting.contabilidad.cancellation_service import CancellationRequest, resolve_cancellation
    from cacao_accounting.contabilidad.posting import PostingError, cancel_document
    from cacao_accounting.database import SalesInvoice, database

    invoice, actor = _seed_invoice()
    with pytest.raises(PostingError, match="motivo"):
        cancel_document(invoice, actor_user_id=actor.id, reason=" ")

    with pytest.raises(PostingError, match="no existe"):
        cancel_document(invoice, actor_user_id="missing", reason="Corrección")

    with pytest.raises(PostingError, match="invalida"):
        cancel_document(invoice, actor_user_id=actor.id, reason="Corrección", cancellation_date="invalid")

    invoice.docstatus = 0
    with pytest.raises(PostingError, match="aprobado"):
        cancel_document(invoice, actor_user_id=actor.id, reason="Corrección")
    invoice.docstatus = 1
    database.session.commit()

    with pytest.raises(ValueError, match="compania"):
        resolve_cancellation(
            CancellationRequest(SimpleNamespace(docstatus=1), None, actor.id, "Corrección"),
            source_type="sales_invoice",
            source_id="missing",
        )

    no_date = SalesInvoice(company="cacao", docstatus=1)
    database.session.add(no_date)
    database.session.commit()
    with pytest.raises(ValueError, match="fecha"):
        resolve_cancellation(
            CancellationRequest(no_date, None, actor.id, "Corrección"),
            source_type="sales_invoice",
            source_id=no_date.id,
        )

    outside_period = SalesInvoice(company="cacao", posting_date=date(2027, 1, 1), docstatus=1)
    database.session.add(outside_period)
    database.session.commit()
    with pytest.raises(ValueError, match="periodo"):
        resolve_cancellation(
            CancellationRequest(outside_period, None, actor.id, "Corrección"),
            source_type="sales_invoice",
            source_id=outside_period.id,
        )


def test_cancellation_dependency_catalog_checks_payment_bank_purchase_and_stock(app_ctx):
    """La consulta común recorre los efectos específicos de cada familia."""
    from cacao_accounting.contabilidad.cancellation_service import active_cancellation_dependencies
    from cacao_accounting.database import (
        BankTransaction,
        PaymentEntry,
        PaymentReference,
        PurchaseInvoice,
        StockEntry,
        database,
    )

    documents = [
        PaymentEntry(company="cacao", payment_type="pay", docstatus=1),
        BankTransaction(bank_account_id="BANK-761", posting_date=date(2026, 1, 3), deposit=Decimal("1")),
        PurchaseInvoice(company="cacao", posting_date=date(2026, 1, 3), docstatus=1),
        StockEntry(company="cacao", posting_date=date(2026, 1, 3), docstatus=1),
    ]
    for document in documents:
        active_cancellation_dependencies(document, document.__tablename__, document.id or "missing")

    payment = documents[0]
    database.session.add(payment)
    database.session.flush()
    database.session.add(
        PaymentReference(
            payment_id=payment.id,
            reference_type="sales_invoice",
            reference_id="INVOICE-761",
            allocated_amount=Decimal("1"),
        )
    )
    database.session.commit()
    dependencies = active_cancellation_dependencies(payment, "payment_entry", payment.id)
    assert not any(dependency.detail == "payment_reference" for dependency in dependencies)
