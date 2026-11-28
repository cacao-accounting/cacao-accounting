# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1147: la identidad del open item se conserva hasta el posting.

Un documento con varias líneas abiertas debe resolverse por el open item o
la línea económica elegida, no por el número documental compartido.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from cacao_accounting.api.line_import import _ledger_open_item_matches, _resolve_ledger_open_item_fallback
from cacao_accounting.contabilidad.arap_allocation import (
    ARAPOpenItem,
    AllocationRequest,
    OpenItemResolver,
    apply_allocation,
    plan_allocation,
)
from cacao_accounting.contabilidad.journal_service import create_journal_draft, submit_journal
from cacao_accounting.database import (
    ARAPLedgerEntry,
    ARAPOpenItem as ARAPOpenItemModel,
    Accounts,
    Party,
    SalesInvoice,
    User,
    database,
)

FECHA = date(2026, 5, 15)


def _customer_id() -> str:
    """Devuelve el cliente del escenario contable."""
    return str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())


def _open_items() -> tuple[ARAPOpenItem, ARAPOpenItem]:
    """Crea dos líneas abiertas del mismo documento para el motor de asignación."""
    return (
        ARAPOpenItem(
            document_id="INV-1",
            document_type="sales_invoice",
            currency="NIO",
            outstanding=Decimal("10"),
            company="cacao",
            open_item_id="open-a",
            economic_line_id="line-a",
            direction="debit",
        ),
        ARAPOpenItem(
            document_id="INV-1",
            document_type="sales_invoice",
            currency="NIO",
            outstanding=Decimal("10"),
            company="cacao",
            open_item_id="open-b",
            economic_line_id="line-b",
            direction="debit",
        ),
    )


def test_ejecutor_consume_la_linea_elegida_no_el_documento():
    """Planificar por open-b no vuelve a resolver por el documento ambiguo."""
    resolver = OpenItemResolver(_open_items())
    plan = plan_allocation(
        Decimal("5"),
        "NIO",
        [AllocationRequest(document_id="open-b", amount=Decimal("5"))],
        resolver=resolver,
    )
    line = plan.lines[0]

    assert line.open_item_id == "open-b"
    assert line.economic_line_id == "line-b"

    apply_allocation(plan, resolver=resolver, persist=lambda _line: None)

    balances = {item.open_item_id: item.outstanding for item in resolver.all()}
    assert balances == {"open-a": Decimal("10"), "open-b": Decimal("5")}


def test_huella_de_idempotencia_distingue_lineas_del_mismo_documento():
    """Dos líneas con el mismo importe no comparten huella si cambia la identidad."""
    from cacao_accounting.contabilidad.arap_allocation import allocation_fingerprint

    resolver = OpenItemResolver(_open_items())
    plan_a = plan_allocation(
        Decimal("5"), "NIO", [AllocationRequest(document_id="open-a", amount=Decimal("5"))], resolver=resolver
    )
    plan_b = plan_allocation(
        Decimal("5"), "NIO", [AllocationRequest(document_id="open-b", amount=Decimal("5"))], resolver=resolver
    )

    assert allocation_fingerprint(plan_a.lines[0]) != allocation_fingerprint(plan_b.lines[0])


def _seed_invoice_with_two_lines(party_id: str) -> tuple[str, str, str]:
    """Crea factura, aperturas de ledger y dos open items del mismo documento."""
    invoice = SalesInvoice(
        company="cacao",
        customer_id=party_id,
        document_type="sales_invoice",
        document_no="FAC-1147",
        posting_date=FECHA,
        docstatus=1,
        total=Decimal("100"),
        grand_total=Decimal("100"),
        base_total=Decimal("100"),
        base_grand_total=Decimal("100"),
        transaction_currency="NIO",
        base_currency="NIO",
        exchange_rate=Decimal("1"),
    )
    database.session.add(invoice)
    database.session.flush()
    receivable_id = str(database.session.execute(select(Accounts.id).filter_by(entity="cacao", code="1105")).scalar_one())
    ids = []
    for number, line_id in ((1, "line-1147-a"), (2, "line-1147-b")):
        ledger = ARAPLedgerEntry(
            company="cacao",
            ledger_type="AR",
            party_type="customer",
            party_id=party_id,
            document_type="sales_invoice",
            document_id=str(invoice.id),
            document_no="FAC-1147",
            economic_line_id=line_id,
            posting_date=FECHA,
            event_type="opening",
            currency="NIO",
            document_amount=Decimal("50"),
        )
        database.session.add(ledger)
        database.session.flush()
        item = ARAPOpenItemModel(
            company="cacao",
            ledger_type="AR",
            party_type="customer",
            party_id=party_id,
            account_id=receivable_id,
            document_type="sales_invoice",
            document_id=str(invoice.id),
            document_no="FAC-1147",
            economic_line_id=line_id,
            line_number=number,
            posting_date=FECHA,
            currency="NIO",
            original_amount=Decimal("50"),
            unallocated_amount=Decimal("50"),
            direction="debit",
            status="open",
            source_voucher_type="sales_invoice",
            source_voucher_id=str(invoice.id),
        )
        database.session.add(item)
        database.session.flush()
        ids.append(str(item.id))
    database.session.commit()
    return str(invoice.id), ids[0], ids[1]


def test_posting_de_diario_usa_el_open_item_elegido(entorno_contable_aislado):
    """El diario aplica la línea identificada aunque el número documental sea ambiguo."""
    app = entorno_contable_aislado.app
    with app.app_context():
        party_id = _customer_id()
        invoice_id, first_id, second_id = _seed_invoice_with_two_lines(party_id)
        actor_id = str(database.session.execute(select(User.id).filter_by(user="admin")).scalar_one())
        journal = create_journal_draft(
            {
                "company": "cacao",
                "posting_date": "2026-05-20",
                "books": ["DEFAULT_BOOK"],
                "transaction_currency": "NIO",
                "lines": [
                    {"order": 1, "account": "1101", "debit": "30", "credit": ""},
                    {
                        "order": 2,
                        "account": "1105",
                        "debit": "",
                        "credit": "30",
                        "party_type": "customer",
                        "party": party_id,
                        "reference_type": "sales_invoice",
                        "reference_name": invoice_id,
                        "reference_open_item_id": second_id,
                    },
                ],
            },
            user_id=actor_id,
            assign_identifier=False,
        )

        submit_journal(journal.id, user_id=actor_id)

        first = database.session.get(ARAPOpenItemModel, first_id)
        second = database.session.get(ARAPOpenItemModel, second_id)
        assert first is not None and first.unallocated_amount == Decimal("50.0000")
        assert second is not None and second.unallocated_amount == Decimal("20.0000")


def test_fallback_del_ledger_respeta_la_linea_indicada(entorno_contable_aislado):
    """La importación resuelve el open item por economic line del ledger."""
    app = entorno_contable_aislado.app
    with app.app_context():
        party_id = _customer_id()
        _invoice_id, _first_id, _second_id = _seed_invoice_with_two_lines(party_id)
        validated_row: dict[str, str] = {}

        matches_without_hint = _ledger_open_item_matches(
            company_id="cacao",
            party_type="customer",
            party_id=party_id,
            reference_type="sales_invoice",
            reference_document="FAC-1147",
        )
        matches_line_b = _ledger_open_item_matches(
            company_id="cacao",
            party_type="customer",
            party_id=party_id,
            reference_type="sales_invoice",
            reference_document="FAC-1147",
            line_hint="line-1147-b",
        )
        resolved = _resolve_ledger_open_item_fallback(
            validated_row=validated_row,
            errors=[],
            row_no=1,
            company_id="cacao",
            party_type="customer",
            party_id=party_id,
            reference_type="sales_invoice",
            reference_document="FAC-1147",
            line_hint="line-1147-b",
        )

        assert len(matches_without_hint) == 2
        assert [item.economic_line_id for item in matches_line_b] == ["line-1147-b"]
        assert resolved is True
        assert validated_row["reference_document"] == "FAC-1147"
