# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2341: el selector de conciliación muestra la moneda efectiva del fondo.

La vista no debe mostrar ``None`` cuando el fondo no define moneda explícita:
debe mostrar la misma moneda funcional que persiste el servicio.
"""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting.bancos.services import create_petty_cash_reconciliation
from cacao_accounting.database import (
    Accounts,
    Currency,
    Entity,
    PettyCashAccount,
    PettyCashReconciliation,
    PettyCashVoucher,
    database,
)

FECHA = date(2026, 5, 15)
_FONDOS_CREADOS: list[tuple[str, str]] = []


@pytest.fixture(autouse=True)
def _limpia_fondos(app):
    """Elimina los fondos y borradores creados por cada prueba."""
    yield
    with app.app_context():
        for fondo_id, account_id in _FONDOS_CREADOS:
            database.session.execute(
                database.delete(PettyCashReconciliation).where(PettyCashReconciliation.petty_cash_id == fondo_id)
            )
            database.session.execute(database.delete(PettyCashVoucher).where(PettyCashVoucher.petty_cash_id == fondo_id))
            fondo = database.session.get(PettyCashAccount, fondo_id)
            if fondo is not None:
                database.session.delete(fondo)
                database.session.flush()
            database.session.execute(database.delete(Accounts).where(Accounts.id == account_id))
            database.session.commit()
        _FONDOS_CREADOS.clear()


def _moneda_funcional(company: str = "cacao") -> str:
    """Devuelve la moneda funcional configurada para la compañía."""
    entity = database.session.execute(select(Entity).filter_by(code=company)).scalar_one()
    assert entity.currency
    return str(entity.currency)


def _fondo(currency: str | None, company: str = "cacao") -> PettyCashAccount:
    """Crea un fondo de caja chica con la moneda indicada."""
    if currency:
        if database.session.execute(select(Currency).filter_by(code=currency)).scalar_one_or_none() is None:
            database.session.add(Currency(code=currency, name=currency, decimals=2, active=True))
            database.session.flush()
    sufijo = uuid4().hex[:6]
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
        name=f"Fondo {sufijo}",
        currency=currency,
        float_amount=Decimal("100"),
    )
    database.session.add(fondo)
    database.session.flush()
    _FONDOS_CREADOS.append((fondo.id, cuenta.id))
    return fondo


def test_selector_muestra_moneda_funcional_si_el_fondo_no_la_define(app, entorno_contable, authenticated_client):
    """Un fondo sin moneda explícita se etiqueta con la moneda de la compañía."""
    del entorno_contable
    with app.app_context():
        moneda = _moneda_funcional()
        fondo = _fondo(None)
        database.session.commit()
        nombre = fondo.name

    respuesta = authenticated_client("admin").get("/cash_management/petty-cash-reconciliation/new")

    assert respuesta.status_code == 200
    cuerpo = respuesta.get_data(as_text=True)
    opcion = cuerpo.split(nombre, 1)[1].split("</option>", 1)[0]
    assert f"({moneda})" in opcion
    assert "(None)" not in opcion


def test_selector_conserva_la_moneda_explicita_del_fondo(app, entorno_contable, authenticated_client):
    """Un fondo con moneda propia se muestra con esa moneda y no con la funcional."""
    del entorno_contable
    with app.app_context():
        moneda = _moneda_funcional()
        fondo = _fondo("USD")
        database.session.commit()
        nombre = fondo.name

    respuesta = authenticated_client("admin").get("/cash_management/petty-cash-reconciliation/new")

    assert respuesta.status_code == 200
    opcion = respuesta.get_data(as_text=True).split(nombre, 1)[1].split("</option>", 1)[0]
    assert "(USD)" in opcion
    assert f"({moneda})" not in opcion


def test_conciliacion_persiste_la_moneda_mostrada_para_fondo_sin_moneda(app, entorno_contable, authenticated_client):
    """La moneda del selector coincide con la que persiste el servicio."""
    del entorno_contable
    with app.app_context():
        moneda = _moneda_funcional()
        fondo = _fondo(None)
        database.session.commit()
        fondo_id = fondo.id

    respuesta = authenticated_client("admin").post(
        "/cash_management/petty-cash-reconciliation/new",
        data={
            "company": "cacao",
            "petty_cash_id": fondo_id,
            "reconciliation_date": FECHA.isoformat(),
            "counted_cash": "10",
        },
        follow_redirects=False,
    )

    assert respuesta.status_code == 302
    with app.app_context():
        conciliacion = database.session.execute(
            select(PettyCashReconciliation).where(PettyCashReconciliation.petty_cash_id == fondo_id)
        ).scalar_one()
        assert conciliacion.transaction_currency == moneda


def test_edicion_muestra_la_moneda_del_conteo_para_fondo_sin_moneda(app, entorno_contable, authenticated_client):
    """El borrador y la etiqueta del conteo usan la moneda persistida."""
    del entorno_contable
    with app.app_context():
        moneda = _moneda_funcional()
        fondo = _fondo(None)
        database.session.commit()
        conciliacion = create_petty_cash_reconciliation(
            company="cacao",
            petty_cash_id=fondo.id,
            reconciliation_date=FECHA,
            counted_cash=Decimal("10"),
        )
        conciliacion_id = conciliacion.id

    respuesta = authenticated_client("admin").get(f"/cash_management/petty-cash-reconciliation/{conciliacion_id}/edit")

    assert respuesta.status_code == 200
    cuerpo = respuesta.get_data(as_text=True)
    assert f'value="{moneda}" readonly' in cuerpo
    assert f"Efectivo contado ({moneda})" in cuerpo
