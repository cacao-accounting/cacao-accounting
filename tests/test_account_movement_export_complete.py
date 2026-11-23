# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1937: la exportación completa del movimiento contable no se trunca.

CSV, XLSX y PDF deben entregar todas las filas que satisfacen los filtros.
La ruta `account_movement` reejecuta el servicio con `export_all=True` para
cualquier formato de export (incluido PDF), por lo que el reporte de detalle
debe devolver el total y no una sola página.
"""

from __future__ import annotations

import inspect
from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import (
    Accounts,
    Book,
    ComprobanteContable,
    Currency,
    Entity,
    GLEntry,
    Party,
    database,
)
from cacao_accounting.reportes.routes import account_movement
from cacao_accounting.reportes.helpers import _group_paginated_rows
from cacao_accounting.reportes.services import FinancialReportFilters, get_account_movement_detail

FECHA = date(2026, 5, 15)
COMPANIA = "cacao"


def _scenario(app) -> None:
    with app.app_context():
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        if database.session.execute(database.select(Entity).filter_by(code=COMPANIA)).scalar_one_or_none() is None:
            database.session.add(
                Entity(
                    code=COMPANIA,
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                )
            )
        book = database.session.execute(database.select(Book).filter_by(entity=COMPANIA)).scalars().first()
        if book is None:
            book = Book(
                entity=COMPANIA,
                code="DEFAULT_BOOK",
                name="Default",
                status="activo",
                is_primary=True,
                currency="NIO",
            )
            database.session.add(book)
            database.session.flush()
        cuenta = database.session.execute(
            database.select(Accounts).filter_by(entity=COMPANIA, code="1101")
        ).scalar_one_or_none()
        if cuenta is None:
            cuenta = Accounts(
                entity=COMPANIA,
                code="1101",
                name="Caja",
                classification="asset",
                account_type="cash",
                group=False,
                active=True,
                enabled=True,
            )
            database.session.add(cuenta)
            database.session.flush()

        marker = f"MOV-{uuid4().hex[:8]}"
        for index in range(102):
            voucher = ComprobanteContable(
                entity=COMPANIA,
                date=FECHA,
                document_no=f"{marker}-{index}",
                status="submitted",
            )
            database.session.add(voucher)
            database.session.flush()
            database.session.add(
                GLEntry(
                    company=COMPANIA,
                    ledger_id=book.id,
                    account_id=cuenta.id,
                    account_code=cuenta.code,
                    voucher_type="journal_entry",
                    voucher_id=voucher.id,
                    posting_date=FECHA,
                    debit=Decimal("1"),
                    credit=Decimal("0"),
                    is_cancelled=False,
                )
            )
        database.session.commit()


def test_export_all_devuelve_todas_las_filas(app, entorno_contable):
    """`export_all=True` supera el límite de página de 100."""
    _scenario(app)
    with app.app_context():
        filters = FinancialReportFilters(company=COMPANIA, page=1, page_size=100, export_all=False)
        paginated = get_account_movement_detail(filters)
        full = get_account_movement_detail(FinancialReportFilters(company=COMPANIA, page=1, page_size=100, export_all=True))

        assert paginated.total_rows >= 102
        assert len(paginated.rows) == 100
        assert "__party_group_label" not in paginated.columns
        assert len(full.rows) == full.total_rows
        assert len(full.rows) >= 102


def test_agrupacion_por_tercero_conserva_identidades_distintas(app, entorno_contable):
    """Parties sharing a display name remain separate accounting groups."""
    _scenario(app)
    with app.app_context():
        ledger = database.session.execute(database.select(Book).filter_by(entity=COMPANIA)).scalars().first()
        account = database.session.execute(database.select(Accounts).filter_by(entity=COMPANIA, code="1101")).scalar_one()
        parties = [Party(code=f"DUP-{index}", name="Mismo tercero", is_customer=True) for index in range(2)]
        database.session.add_all(parties)
        database.session.flush()
        for index, party in enumerate(parties):
            voucher = ComprobanteContable(
                entity=COMPANIA,
                date=FECHA,
                document_no=f"PARTY-{index}-{uuid4().hex[:6]}",
                status="submitted",
            )
            database.session.add(voucher)
            database.session.flush()
            database.session.add(
                GLEntry(
                    company=COMPANIA,
                    ledger_id=ledger.id,
                    account_id=account.id,
                    account_code=account.code,
                    voucher_type="journal_entry",
                    voucher_id=voucher.id,
                    posting_date=FECHA,
                    debit=Decimal("1"),
                    credit=Decimal("0"),
                    party_type="customer",
                    party_id=party.id,
                    is_cancelled=False,
                )
            )
        database.session.commit()

        report = get_account_movement_detail(
            FinancialReportFilters(company=COMPANIA, page=1, page_size=500),
            group_by="party_id",
        )
        duplicate_name_rows = [row.values for row in report.rows if row.values["party_id"] == "Mismo tercero"]

        assert len(duplicate_name_rows) == 2
        assert "__party_group_label" not in report.columns
        assert [row["__group_count"] for row in duplicate_name_rows] == [1, 1]
        grouped = _group_paginated_rows(
            [{key: value for key, value in row.items() if not key.startswith("__")} for row in duplicate_name_rows],
            duplicate_name_rows,
            "party_id",
            "NIO",
        )
        titles = [row["__group_title"] for row in grouped if row.get("__row_type") == "group"]
        assert "DUP-0" in titles[0] and "DUP-1" in titles[1]
        assert titles[0] != titles[1]


def test_ruta_account_movement_usa_export_all_para_pdf():
    """La ruta reejecuta el servicio completo también para PDF (#1937)."""
    source = inspect.getsource(account_movement)
    assert '"csv", "xlsx", "pdf"' in source or "{'csv', 'xlsx', 'pdf'}" in source
    assert "export_all=True" in source
