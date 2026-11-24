# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1589: el detalle bancario acumula el saldo anterior al rango consultado."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Bank, BankAccount, Currency, Entity, database
from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter
from cacao_accounting.reportes.services import BankingFilters, get_bank_movement_detail


@pytest.fixture
def banco_con_movimientos():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao SA",
                tax_id="J-1589",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()
        banco = Bank(name="Banco 1589", is_active=True)
        database.session.add(banco)
        database.session.flush()
        cuenta = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name="Cuenta 1589",
            account_no="CTA-1589",
            currency="NIO",
            is_active=True,
        )
        database.session.add(cuenta)
        database.session.commit()
        adapter = BankStatementAdapter()
        for fecha, referencia, deposito in (
            (date(2025, 12, 31), "EXT-1589-A", "100.00"),
            (date(2026, 1, 2), "EXT-1589-B", "20.00"),
        ):
            fila = {
                "bank_account_id": cuenta.id,
                "posting_date": fecha.isoformat(),
                "reference_number": referencia,
                "description": referencia,
                "deposit": deposito,
                "withdrawal": None,
            }
            assert adapter.validate_row(fila) == []
            adapter.persist_document(adapter.build_document([fila], {"company_id": "cacao"}))
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_saldo_inicial_incluye_movimientos_anteriores(banco_con_movimientos):
    """Un ingreso del 31 de diciembre eleva el saldo del detalle de enero."""
    with banco_con_movimientos.app_context():
        reporte = get_bank_movement_detail(
            BankingFilters(company="cacao", date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
        )

    assert len(reporte.rows) == 1
    assert Decimal(str(reporte.rows[0].values["running_balance"])) == Decimal("120")
    assert Decimal(str(reporte.totals["opening_balance"])) == Decimal("100")
    assert Decimal(str(reporte.totals["running_balance"])) == Decimal("120")


def test_saldo_inicial_es_cero_si_no_hay_movimientos_previos(banco_con_movimientos):
    """Un rango anterior al primer movimiento no inventa saldo de apertura."""
    with banco_con_movimientos.app_context():
        reporte = get_bank_movement_detail(
            BankingFilters(company="cacao", date_from=date(2025, 12, 1), date_to=date(2025, 12, 30))
        )

    assert reporte.rows == []
    assert Decimal(str(reporte.totals["opening_balance"])) == Decimal("0")


def test_saldo_inicial_excluye_el_mismo_dia_del_corte(banco_con_movimientos):
    """El movimiento del día inicial pertenece al rango y no al saldo previo."""
    with banco_con_movimientos.app_context():
        reporte = get_bank_movement_detail(
            BankingFilters(company="cacao", date_from=date(2025, 12, 31), date_to=date(2026, 1, 31))
        )

    assert [Decimal(str(fila.values["running_balance"])) for fila in reporte.rows] == [
        Decimal("100"),
        Decimal("120"),
    ]
    assert Decimal(str(reporte.totals["opening_balance"])) == Decimal("0")
