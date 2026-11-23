# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1886: la conciliación de caja chica compara importes en una sola moneda."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.bancos.services import _petty_cash_reconciliation_derived_values
from cacao_accounting.database import (
    Accounts,
    Book,
    GLEntry,
    PettyCashAccount,
    PettyCashVoucher,
    database,
)

FECHA = date(2026, 5, 15)
_FONDOS_CREADOS: list[tuple[str, str]] = []


@pytest.fixture(autouse=True)
def _limpia_fondos(app):
    """Elimina los fondos creados para no contaminar la base compartida del worker."""
    yield
    with app.app_context():
        for fondo_id, account_id in _FONDOS_CREADOS:
            database.session.execute(database.delete(PettyCashVoucher).where(PettyCashVoucher.petty_cash_id == fondo_id))
            database.session.execute(database.delete(GLEntry).where(GLEntry.account_id == account_id))
            fondo = database.session.get(PettyCashAccount, fondo_id)
            if fondo is not None:
                database.session.delete(fondo)
                database.session.flush()
            database.session.execute(database.delete(Accounts).where(Accounts.id == account_id))
            database.session.commit()
        _FONDOS_CREADOS.clear()


def _asegurar_moneda(code: str) -> None:
    """Crea la moneda de prueba si el fixture no la sembró."""
    from cacao_accounting.database import Currency

    if database.session.execute(select(Currency).filter_by(code=code)).scalar_one_or_none() is None:
        database.session.add(Currency(code=code, name=code, decimals=2, active=True))
        database.session.flush()


def _fondo_usd(company: str = "cacao", currency: str = "USD") -> PettyCashAccount:
    """Crea un fondo de caja chica en la moneda indicada."""
    sufijo = uuid4().hex[:6]
    _asegurar_moneda(currency)
    cuenta = Accounts(
        entity=company,
        code=f"PC{sufijo}",
        name=f"Caja chica {sufijo}",
        classification="asset",
        account_type="cash",
    )
    database.session.add(cuenta)
    database.session.flush()
    fondo = PettyCashAccount(
        company=company,
        account_id=cuenta.id,
        name=f"Fondo {currency} {sufijo}",
        currency=currency,
        float_amount=Decimal("100"),
    )
    database.session.add(fondo)
    database.session.flush()
    _FONDOS_CREADOS.append((fondo.id, cuenta.id))
    return fondo


def _asiento_en_libro(fondo: PettyCashAccount, amount: Decimal) -> None:
    """Registra el saldo del fondo en el libro primario NIO."""
    libro = database.session.execute(select(Book).filter_by(code="DEFAULT_BOOK")).scalar_one()
    database.session.add(
        GLEntry(
            company=fondo.company,
            account_id=fondo.account_id,
            account_code=fondo.account_id,
            ledger_id=libro.id,
            posting_date=FECHA,
            debit=amount,
            credit=Decimal("0"),
            voucher_type="journal_entry",
            voucher_id=f"v-{uuid4().hex[:8]}",
        )
    )


def test_convierte_el_saldo_del_libro_a_la_moneda_del_fondo(app, entorno_contable):
    """365 NIO de GL y un vale de 10 USD dejan un esperado de 0 USD (tasa 36.5)."""
    del entorno_contable
    with app.app_context():
        fondo = _fondo_usd()
        _asiento_en_libro(fondo, Decimal("365"))
        database.session.add(
            PettyCashVoucher(
                petty_cash_id=fondo.id,
                concept="Vale entregado",
                amount=Decimal("10"),
                voucher_status="entregado",
                posting_date=FECHA,
            )
        )
        database.session.commit()

        valores = _petty_cash_reconciliation_derived_values(fondo, FECHA)

        assert valores["ledger_balance"] == Decimal("10.0000")
        assert valores["open_vouchers"] == Decimal("10")
        assert valores["expected_cash"] == Decimal("0")


def test_bloquea_la_conciliacion_si_falta_la_tasa(app, entorno_contable):
    """Sin tasa entre el libro y el fondo no se restan monedas distintas."""
    del entorno_contable
    with app.app_context():
        fondo = _fondo_usd(currency="EUR")
        _asiento_en_libro(fondo, Decimal("365"))
        database.session.commit()

        with pytest.raises(ValueError, match="tipo de cambio"):
            _petty_cash_reconciliation_derived_values(fondo, FECHA)


def _voucher_entregado(fondo: PettyCashAccount, amount: Decimal) -> None:
    """Registra un vale entregado pendiente de liquidación."""
    database.session.add(
        PettyCashVoucher(
            petty_cash_id=fondo.id,
            concept="Vale entregado",
            amount=amount,
            voucher_status="entregado",
            posting_date=FECHA,
        )
    )


def test_lista_y_detalle_muestran_el_saldo_en_moneda_del_fondo(app, entorno_contable, authenticated_client):
    """La lista y el detalle convierten 365 NIO a 10 USD y esperan 0."""
    del entorno_contable
    with app.app_context():
        fondo = _fondo_usd()
        _asiento_en_libro(fondo, Decimal("365"))
        _voucher_entregado(fondo, Decimal("10"))
        database.session.commit()
        fondo_id, fondo_nombre = fondo.id, fondo.name

    client = authenticated_client("admin")
    lista = client.get("/cash_management/petty-cash/list")
    detalle = client.get(f"/cash_management/petty-cash/{fondo_id}")

    assert lista.status_code == 200
    cuerpo_lista = lista.get_data(as_text=True)
    fila = cuerpo_lista.split(fondo_nombre, 1)[1].split("</tr>", 1)[0]
    assert "10.0000" in fila
    assert "0.0000" in fila
    assert "365" not in fila

    assert detalle.status_code == 200
    cuerpo_detalle = detalle.get_data(as_text=True)
    assert "10.0000" in cuerpo_detalle
    assert "0.0000" in cuerpo_detalle


def test_lista_muestra_guion_si_falta_la_tasa(app, entorno_contable, authenticated_client):
    """Sin tasa, la lista no mezcla monedas ni responde 500."""
    del entorno_contable
    with app.app_context():
        fondo = _fondo_usd(currency="EUR")
        _asiento_en_libro(fondo, Decimal("365"))
        database.session.commit()
        fondo_nombre = fondo.name

    lista = authenticated_client("admin").get("/cash_management/petty-cash/list")

    assert lista.status_code == 200
    fila = lista.get_data(as_text=True).split(fondo_nombre, 1)[1].split("</tr>", 1)[0]
    assert "365" not in fila
    assert fila.count(">-<") >= 2


def test_post_de_conciliacion_sin_tasa_avisa_y_no_persiste(app, entorno_contable, authenticated_client):
    """La ruta HTTP bloquea la conciliación sin tasa y no crea filas."""
    from cacao_accounting.database import PettyCashReconciliation

    del entorno_contable
    with app.app_context():
        fondo = _fondo_usd(currency="EUR")
        _asiento_en_libro(fondo, Decimal("365"))
        database.session.commit()
        fondo_id = fondo.id
        antes = len(database.session.execute(select(PettyCashReconciliation)).scalars().all())

    response = authenticated_client("admin").post(
        "/cash_management/petty-cash-reconciliation/new",
        data={
            "company": "cacao",
            "petty_cash_id": fondo_id,
            "reconciliation_date": FECHA.isoformat(),
            "counted_cash": "10",
        },
    )

    assert response.status_code == 200
    assert "tipo de cambio" in response.get_data(as_text=True).lower()
    with app.app_context():
        despues = len(database.session.execute(select(PettyCashReconciliation)).scalars().all())
        assert despues == antes
