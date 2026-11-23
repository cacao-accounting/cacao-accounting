# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2090: el importe de caja chica respeta los decimales de su moneda."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import inspect

from cacao_accounting.bancos.services import (
    _validate_petty_cash_expense_precision,
    create_petty_cash_expense,
)
from cacao_accounting.database import (
    ComprobanteContable,
    ComprobanteContableDetalle,
    CostCenter,
    Currency,
    ExchangeRate,
    GLEntry,
    PettyCashAccount,
    PettyCashExpense,
    database,
)

FECHA = "2026-05-15"


@pytest.fixture
def fondos_monetarios(app, entorno_contable):
    """Crea fondos con monedas de 2 y 3 decimales y los elimina al final."""
    creados: list[tuple[str, str]] = []
    account_id = str(inspect(entorno_contable.caja).identity[0])

    def crear(code: str, decimals: int) -> str:
        with app.app_context():
            existente = database.session.execute(database.select(Currency).filter_by(code=code)).scalar_one_or_none()
            if existente is None:
                database.session.add(Currency(code=code, name=code, decimals=decimals, active=True))
                database.session.flush()
            sufijo = uuid4().hex[:6]
            fondo = PettyCashAccount(
                company="cacao",
                account_id=account_id,
                name=f"Fondo {code} {sufijo}",
                currency=code,
                float_amount=Decimal("100"),
                is_default=False,
                is_active=True,
            )
            database.session.add(fondo)
            database.session.commit()
            creados.append((fondo.id, code))
            return fondo.id

    yield crear

    with app.app_context():
        for fondo_id, code in creados:
            database.session.execute(database.delete(PettyCashExpense).where(PettyCashExpense.petty_cash_id == fondo_id))
            fondo = database.session.get(PettyCashAccount, fondo_id)
            if fondo is not None:
                database.session.delete(fondo)
        database.session.commit()


def test_el_paso_del_importe_se_deriva_de_la_moneda_del_fondo(app, entorno_contable, fondos_monetarios, authenticated_client):
    """El formulario publica el paso de cada fondo según Currency.decimals."""
    del entorno_contable
    fondo_tres = fondos_monetarios("BHD3", 3)
    fondo_dos = fondos_monetarios("USD", 2)

    response = authenticated_client("admin").get("/cash_management/petty-cash-expense/new")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert f'"{fondo_tres}": "0.001"' in cuerpo
    assert f'"{fondo_dos}": "0.01"' in cuerpo
    assert 'step="0.01"' in cuerpo


def test_el_servicio_conserva_tres_decimales_y_rechaza_exceso_en_dos(
    app, entorno_contable, fondos_monetarios, authenticated_client
):
    """3 decimales se conservan en moneda de 3; una moneda de 2 rechaza el exceso."""
    del entorno_contable
    fondo_tres = fondos_monetarios("BHD3", 3)
    fondo_dos = fondos_monetarios("USD", 2)

    with app.app_context():
        fondo = database.session.get(PettyCashAccount, fondo_tres)
        _validate_petty_cash_expense_precision(Decimal("1.001"), fondo)
        assert Decimal("1.001") == Decimal("1.001")

        fondo = database.session.get(PettyCashAccount, fondo_dos)
        with pytest.raises(ValueError, match="2 decimales"):
            _validate_petty_cash_expense_precision(Decimal("1.001"), fondo)

    antes = _conteo_gastos(app)
    response = authenticated_client("admin").post(
        "/cash_management/petty-cash-expense/new",
        data={
            "company": "cacao",
            "petty_cash_id": fondo_dos,
            "posting_date": FECHA,
            "concept": "Compra precisa",
            "amount": "1.001",
            "cost_center_code": "CC-2090",
        },
    )

    assert response.status_code == 200
    assert "2 decimales" in response.get_data(as_text=True)
    assert _conteo_gastos(app) == antes


def _conteo_gastos(app) -> int:
    with app.app_context():
        return len(database.session.execute(database.select(PettyCashExpense)).scalars().all())


def test_el_servicio_persiste_tres_decimales_sin_redondear(app, entorno_contable, reference_users, fondos_monetarios):
    """Un gasto de 1.001 en moneda de 3 decimales conserva su escala al postear."""
    from datetime import date

    del entorno_contable
    fondo_id = fondos_monetarios("BHD3", 3)
    with app.app_context():
        if (
            database.session.execute(
                database.select(ExchangeRate).filter_by(origin="BHD3", destination="NIO", date=date(2026, 5, 15))
            ).scalar_one_or_none()
            is None
        ):
            database.session.add(ExchangeRate(origin="BHD3", destination="NIO", rate=Decimal("1"), date=date(2026, 5, 15)))
        centro = database.session.execute(
            database.select(CostCenter).filter_by(entity="cacao", code="CC2090")
        ).scalar_one_or_none()
        if centro is None:
            database.session.add(CostCenter(entity="cacao", code="CC2090", name="Centro 2090", active=True, enabled=True))
        database.session.commit()

        gasto = create_petty_cash_expense(
            company="cacao",
            petty_cash_id=fondo_id,
            expense_account_code="5201",
            concept="Compra precisa",
            amount=Decimal("1.001"),
            cost_center_code="CC2090",
            posted_date=date(2026, 5, 15),
            actor_id=str(reference_users["admin"].id),
        )
        assert gasto.amount == Decimal("1.001")

        journal_id = gasto.journal_id
        database.session.execute(database.delete(GLEntry).where(GLEntry.voucher_id == journal_id))
        database.session.execute(
            database.delete(ComprobanteContableDetalle).where(ComprobanteContableDetalle.transaction_id == journal_id)
        )
        database.session.delete(gasto)
        database.session.execute(database.delete(ComprobanteContable).where(ComprobanteContable.id == journal_id))
        centro = database.session.execute(
            database.select(CostCenter).filter_by(entity="cacao", code="CC2090")
        ).scalar_one_or_none()
        if centro is not None:
            database.session.delete(centro)
        database.session.commit()
