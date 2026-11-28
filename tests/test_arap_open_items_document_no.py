# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1146: la reconstrucción AR/AP conserva el número documental.

El open item canónico debe exponer ``document_no`` y la búsqueda de
referencias del diario debe resolverlo también desde el ledger.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import select

from cacao_accounting.contabilidad.arap_allocation import list_open_items
from cacao_accounting.contabilidad.journal_service import _find_ar_ap_reference_targets
from cacao_accounting.database import ARAPLedgerEntry, Party, database

FECHA = date(2026, 5, 15)


def _seed_open_item(document_id: str, document_no: str | None, amount: Decimal = Decimal("100")) -> str:
    """Crea una apertura AR canónica sin fila en el cache de open items."""
    party_id = str(database.session.execute(select(Party.id).filter_by(code="CLI001")).scalar_one())
    database.session.add(
        ARAPLedgerEntry(
            company="cacao",
            ledger_type="AR",
            party_type="customer",
            party_id=party_id,
            document_type="sales_invoice",
            document_id=document_id,
            document_no=document_no,
            posting_date=FECHA,
            event_type="opening",
            currency="NIO",
            document_amount=amount,
        )
    )
    database.session.flush()
    return party_id


def test_list_open_items_conserva_el_numero_documental(entorno_contable_aislado):
    """El DTO reconstruido desde el ledger publica el número visible."""
    app = entorno_contable_aislado.app
    with app.app_context():
        party_id = _seed_open_item("INV-ID-1146", "FAC-2026-001")
        database.session.commit()

        items = [
            item
            for item in list_open_items(company="cacao", party_type="customer", party_id=party_id)
            if item.document_id == "INV-ID-1146"
        ]

        assert len(items) == 1
        assert items[0].document_no == "FAC-2026-001"
        assert items[0].outstanding == Decimal("100")


def test_busqueda_de_referencia_resuelve_el_numero_desde_el_ledger(entorno_contable_aislado):
    """La referencia del diario encuentra el open item por su número visible."""
    app = entorno_contable_aislado.app
    with app.app_context():
        _seed_open_item("INV-ID-1146", "FAC-2026-001")
        database.session.commit()
        line = SimpleNamespace(party="CLI001")

        by_number = _find_ar_ap_reference_targets("cacao", line, "customer", "sales_invoice", "FAC-2026-001")
        by_id = _find_ar_ap_reference_targets("cacao", line, "customer", "sales_invoice", "INV-ID-1146")
        missing = _find_ar_ap_reference_targets("cacao", line, "customer", "sales_invoice", "FAC-OTRA")

        assert [item.document_id for item in by_number] == ["INV-ID-1146"]
        assert [item.document_id for item in by_id] == ["INV-ID-1146"]
        assert missing == []


def test_list_open_items_tolera_documento_sin_numero(entorno_contable_aislado):
    """Un documento legacy sin número no inventa una referencia."""
    app = entorno_contable_aislado.app
    with app.app_context():
        party_id = _seed_open_item("INV-ID-SIN-NUMERO", None)
        database.session.commit()

        items = [
            item
            for item in list_open_items(company="cacao", party_type="customer", party_id=party_id)
            if item.document_id == "INV-ID-SIN-NUMERO"
        ]

        assert len(items) == 1
        assert items[0].document_no is None
