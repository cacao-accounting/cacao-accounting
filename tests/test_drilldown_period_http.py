# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1939: el drilldown conserva el rango de períodos al navegar.

La prueba renderiza un reporte padre con dos períodos, extrae el enlace real de
drilldown y abre el detalle: el movimiento debe filtrar por ese rango, no por el
período predeterminado de la compañía.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from html import unescape
from uuid import uuid4

import pytest

from cacao_accounting.database import Accounts, AccountingPeriod, Book, GLEntry, database


@pytest.fixture
def movimientos_en_dos_periodos(app, entorno_contable):
    """Tres movimientos: dos dentro del rango solicitado y uno fuera."""
    del entorno_contable
    sufijo = uuid4().hex[:5]
    with app.app_context():
        cuenta = (
            database.session.execute(database.select(Accounts).where(Accounts.entity == "cacao").order_by(Accounts.code))
            .scalars()
            .first()
        )
        libro = database.session.execute(database.select(Book).filter_by(code="DEFAULT_BOOK")).scalar_one()
        periodos = [
            AccountingPeriod(
                id=f"P{sufijo}A",
                entity="cacao",
                fiscal_year_id="FY2026",
                name=f"Enero {sufijo}",
                start=date(2026, 1, 1),
                end=date(2026, 1, 31),
                enabled=True,
                is_closed=False,
            ),
            AccountingPeriod(
                id=f"P{sufijo}B",
                entity="cacao",
                fiscal_year_id="FY2026",
                name=f"Febrero {sufijo}",
                start=date(2026, 2, 1),
                end=date(2026, 2, 28),
                enabled=True,
                is_closed=False,
            ),
        ]
        database.session.add_all(periodos)
        database.session.flush()
        for fecha, voucher in (
            (date(2026, 1, 15), "V-DENTRO"),
            (date(2026, 2, 15), "V-DENTRO-2"),
            (date(2026, 3, 15), "V-FUERA"),
        ):
            database.session.add(
                GLEntry(
                    company="cacao",
                    ledger_id=libro.id,
                    account_id=cuenta.id,
                    account_code=cuenta.code,
                    account_currency="NIO",
                    company_currency="NIO",
                    exchange_rate=Decimal("1"),
                    posting_date=fecha,
                    debit=Decimal("10"),
                    credit=Decimal("0"),
                    voucher_type="journal_entry",
                    voucher_id=voucher,
                )
            )
        database.session.commit()
        ids = {"desde": periodos[0].id, "hasta": periodos[1].id}
    yield ids
    with app.app_context():
        database.session.execute(database.delete(GLEntry).where(GLEntry.voucher_id.in_(["V-DENTRO", "V-DENTRO-2", "V-FUERA"])))
        database.session.execute(database.delete(AccountingPeriod).where(AccountingPeriod.id.in_(ids.values())))
        database.session.commit()


def test_el_enlace_del_reporte_conserva_el_rango_y_el_destino_lo_aplica(
    app, authenticated_client, movimientos_en_dos_periodos
):
    """El href lleva los dos períodos y el detalle excluye el movimiento de marzo."""
    ids = movimientos_en_dos_periodos
    client = authenticated_client("admin")
    reporte = client.get(
        "/reports/account-summary",
        query_string={
            "company": "cacao",
            "accounting_period_from": ids["desde"],
            "accounting_period_to": ids["hasta"],
            "apply_filters": "1",
        },
    )

    assert reporte.status_code == 200
    cuerpo = unescape(reporte.get_data(as_text=True))
    enlaces = re.findall(r'href="([^"]*account-movement[^"]*)"', cuerpo)
    assert enlaces
    enlace = enlaces[0]
    assert f"accounting_period_from={ids['desde']}" in enlace
    assert f"accounting_period_to={ids['hasta']}" in enlace

    detalle = client.get(f"{enlace}&apply_filters=1")
    assert detalle.status_code == 200
    cuerpo_detalle = detalle.get_data(as_text=True)
    assert "V-DENTRO" in cuerpo_detalle
    assert "V-FUERA" not in cuerpo_detalle
