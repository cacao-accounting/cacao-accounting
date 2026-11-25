# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2090: el importe de caja chica respeta los decimales de su moneda."""

from __future__ import annotations

from datetime import date
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
    PettyCashVoucher,
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


@pytest.fixture
def fondo_precision(app, entorno_contable):
    """Crea un fondo con moneda de N decimales, tasa y centro de costo propios."""
    creados: list[tuple[str, str, str]] = []
    account_id = str(inspect(entorno_contable.caja).identity[0])

    def crear(decimals: int) -> tuple[str, str, str]:
        suffix = uuid4().hex[:6].upper()
        code = f"P{decimals}{suffix}"
        cost_center_code = f"CC{decimals}{suffix}"
        with app.app_context():
            database.session.add(Currency(code=code, name=f"Moneda {code}", decimals=decimals, active=True))
            database.session.add(ExchangeRate(origin=code, destination="NIO", rate=Decimal("1"), date=date(2026, 5, 15)))
            database.session.add(
                CostCenter(entity="cacao", code=cost_center_code, name=f"Centro {code}", active=True, enabled=True)
            )
            database.session.flush()
            fondo = PettyCashAccount(
                company="cacao",
                account_id=account_id,
                name=f"Fondo precisión {code}",
                currency=code,
                float_amount=Decimal("100"),
                is_default=False,
                is_active=True,
            )
            database.session.add(fondo)
            database.session.commit()
            creados.append((fondo.id, code, cost_center_code))
            return fondo.id, code, cost_center_code

    yield crear

    with app.app_context():
        for fondo_id, code, cost_center_code in creados:
            gastos = list(
                database.session.execute(database.select(PettyCashExpense).filter_by(petty_cash_id=fondo_id)).scalars()
            )
            journal_ids = [gasto.journal_id for gasto in gastos if gasto.journal_id]
            if gastos:
                database.session.execute(database.delete(PettyCashExpense).where(PettyCashExpense.petty_cash_id == fondo_id))
                database.session.flush()
            for journal_id in journal_ids:
                database.session.execute(database.delete(GLEntry).where(GLEntry.voucher_id == journal_id))
                database.session.execute(
                    database.delete(ComprobanteContableDetalle).where(ComprobanteContableDetalle.transaction_id == journal_id)
                )
                database.session.execute(database.delete(ComprobanteContable).where(ComprobanteContable.id == journal_id))
            fondo = database.session.get(PettyCashAccount, fondo_id)
            if fondo is not None:
                database.session.delete(fondo)
            database.session.execute(
                database.delete(ExchangeRate).where(
                    ExchangeRate.origin == code,
                    ExchangeRate.destination == "NIO",
                    ExchangeRate.date == date(2026, 5, 15),
                )
            )
            database.session.execute(
                database.delete(CostCenter).where(CostCenter.entity == "cacao", CostCenter.code == cost_center_code)
            )
            database.session.execute(database.delete(Currency).where(Currency.code == code))
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


@pytest.mark.parametrize(
    ("decimals", "step"),
    [(0, "1"), (2, "0.01"), (4, "0.0001"), (5, "0.00001"), (8, "0.00000001")],
)
def test_el_paso_del_importe_respeta_los_decimales_configurados(
    app, entorno_contable, fondo_precision, authenticated_client, decimals, step
):
    """La UI ofrece el paso completo hasta los ocho decimales configurables."""
    del entorno_contable
    fondo_id, _code, _cost_center = fondo_precision(decimals)

    response = authenticated_client("admin").get("/cash_management/petty-cash-expense/new")

    assert response.status_code == 200
    cuerpo = response.get_data(as_text=True)
    assert f'"{fondo_id}": "{step}"' in cuerpo


@pytest.mark.parametrize(
    ("decimals", "accepted", "rejected"),
    [
        (0, "1", "1.1"),
        (2, "1.01", "1.001"),
        (4, "1.0001", "1.00001"),
        (5, "1.00001", "1.000001"),
        (8, "1.00000001", "1.000000001"),
    ],
)
def test_la_precision_efectiva_es_la_de_la_moneda(app, entorno_contable, fondo_precision, decimals, accepted, rejected):
    """Una moneda con hasta 8 decimales conserva toda su escala configurada."""
    del entorno_contable
    fondo_id, _code, _cost_center = fondo_precision(decimals)
    with app.app_context():
        fondo = database.session.get(PettyCashAccount, fondo_id)
        assert fondo is not None
        _validate_petty_cash_expense_precision(Decimal(accepted), fondo)
        with pytest.raises(ValueError, match=f"{decimals} decimales"):
            _validate_petty_cash_expense_precision(Decimal(rejected), fondo)


@pytest.mark.parametrize(
    ("decimals", "amount"),
    [(0, "1.1"), (2, "1.001"), (4, "1.00001"), (5, "1.000001"), (8, "1.000000001")],
)
def test_post_rechaza_exceso_de_escala_sin_persistir(
    app, entorno_contable, fondo_precision, authenticated_client, decimals, amount
):
    """El POST rechaza la escala no configurada sin crear el gasto."""
    del entorno_contable
    fondo_id, _code, cost_center_code = fondo_precision(decimals)
    antes = _conteo_gastos(app)

    response = authenticated_client("admin").post(
        "/cash_management/petty-cash-expense/new",
        data={
            "company": "cacao",
            "petty_cash_id": fondo_id,
            "posting_date": FECHA,
            "concept": "Compra fuera de escala",
            "amount": amount,
            "cost_center_code": cost_center_code,
        },
    )

    assert response.status_code == 200
    assert f"{decimals} decimales" in response.get_data(as_text=True)
    assert _conteo_gastos(app) == antes


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


@pytest.mark.database
def test_el_esquema_monetary_conserva_escala_ocho(app, entorno_contable):
    """Las columnas del flujo de caja chica y GL no redondean a cuatro decimales."""
    del entorno_contable
    with app.app_context():
        inspector = inspect(database.engine)
        esperado = {
            PettyCashExpense.__tablename__: {"amount"},
            PettyCashVoucher.__tablename__: {"amount"},
            GLEntry.__tablename__: {
                "debit",
                "credit",
                "debit_in_account_currency",
                "credit_in_account_currency",
            },
        }
        for tabla, nombres in esperado.items():
            columnas = {columna["name"]: columna["type"] for columna in inspector.get_columns(tabla)}
            for nombre in nombres:
                assert getattr(columnas[nombre], "scale", None) == 8


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


@pytest.mark.parametrize(
    ("decimals", "amount"),
    [(0, "1"), (2, "1.01"), (4, "1.0001"), (5, "1.00001"), (8, "1.00000001")],
)
def test_persistencia_y_gl_respetan_la_escala_configurada(
    app, entorno_contable, reference_users, fondo_precision, decimals, amount
):
    """El importe aceptado se conserva al recargar y cuadra en el GL."""
    del entorno_contable
    fondo_id, code, cost_center_code = fondo_precision(decimals)

    with app.app_context():
        gasto = create_petty_cash_expense(
            company="cacao",
            petty_cash_id=fondo_id,
            expense_account_code="5201",
            concept="Compra con precisión soportada",
            amount=Decimal(amount),
            cost_center_code=cost_center_code,
            posted_date=date(2026, 5, 15),
            actor_id=str(reference_users["admin"].id),
        )
        gasto_id = gasto.id
        journal_id = gasto.journal_id

        database.session.remove()
        recargado = database.session.get(PettyCashExpense, gasto_id)
        assert recargado is not None
        assert Decimal(recargado.amount) == Decimal(amount)

        entries = database.session.execute(database.select(GLEntry).where(GLEntry.voucher_id == journal_id)).scalars().all()
        assert len(entries) >= 2
        balances: dict[str, tuple[Decimal, Decimal]] = {}
        for entry in entries:
            debit, credit = balances.get(entry.ledger_id, (Decimal("0"), Decimal("0")))
            balances[entry.ledger_id] = (debit + entry.debit, credit + entry.credit)
        assert balances
        assert all(debit == Decimal(amount) and credit == Decimal(amount) for debit, credit in balances.values())
        assert {entry.account_currency for entry in entries} == {code}
        assert {entry.company_currency for entry in entries} == {"NIO"}
        assert all(
            (entry.debit_in_account_currency or entry.credit_in_account_currency) == Decimal(amount) for entry in entries
        )
