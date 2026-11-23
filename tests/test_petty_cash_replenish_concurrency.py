# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1093/#1094: dos solicitudes concurrentes no reservan el mismo gasto."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Currency,
    Entity,
    PettyCashAccount,
    PettyCashExpense,
    PettyCashReplenishmentExpense,
    database,
)

pytestmark = pytest.mark.database


@pytest.fixture
def caja_chica_app(tmp_path):
    uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if uri.startswith("sqlite"):
        uri = f"sqlite:///{tmp_path / 'petty-concurrency.sqlite'}"
    elif os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true y una base dedicada.")
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": uri,
            "SQLALCHEMY_ENGINE_OPTIONS": {
                **configuracion.get("SQLALCHEMY_ENGINE_OPTIONS", {}),
                "pool_size": 4,
                "max_overflow": 0,
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "MODO_ESCRITORIO": False,
        }
    )
    empresa = f"L{uuid4().hex[:8]}"
    with app.app_context():
        database.create_all()
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.add(
            Entity(
                code=empresa,
                name=f"Empresa {empresa}",
                company_name=f"Empresa de prueba {empresa}",
                tax_id=f"TAX-{empresa}",
                currency="NIO",
                enabled=True,
                status="activo",
            )
        )
        database.session.flush()
        cuenta = Accounts(
            entity=empresa,
            code=f"PC-{empresa}",
            name="Caja chica",
            classification="asset",
            account_type="petty_cash",
            active=True,
            enabled=True,
            group=False,
        )
        database.session.add(cuenta)
        database.session.flush()
        fondo = PettyCashAccount(
            company=empresa,
            account_id=cuenta.id,
            name=f"Fondo {empresa}",
            currency="NIO",
            float_amount=Decimal("1000"),
            is_default=True,
            is_active=True,
        )
        database.session.add(fondo)
        database.session.flush()
        gasto = PettyCashExpense(
            company=empresa,
            petty_cash_id=fondo.id,
            posting_date=date(2026, 10, 19),
            amount=Decimal("85.00"),
            concept="Consumibles",
            expense_account_code=f"EXP-{empresa}",
            docstatus=1,
        )
        database.session.add(gasto)
        database.session.commit()
        ids = {"company": empresa, "fund_id": fondo.id, "expense_id": gasto.id}
    yield app, ids
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _solicitar(app, ids, barrera: Barrier, dia: int) -> str:
    from cacao_accounting.bancos.services import create_petty_cash_replenishment

    with app.app_context():
        try:
            barrera.wait(timeout=10)
            create_petty_cash_replenishment(
                company=ids["company"],
                petty_cash_id=ids["fund_id"],
                expense_ids=[ids["expense_id"]],
                request_date=date(2026, 10, dia),
            )
            database.session.commit()
            return "creada"
        except Exception:
            database.session.rollback()
            return "rechazada"


def test_dos_solicitudes_concurrentes_reservan_una_vez(caja_chica_app):
    """Una sola solicitud reserva el gasto; la otra se rechaza sin duplicar el vínculo."""
    app, ids = caja_chica_app
    barrera = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(lambda dia: _solicitar(app, ids, barrera, dia), (20, 21)))

    assert resultados.count("creada") == 1, resultados
    with app.app_context():
        vinculos = (
            database.session.execute(
                database.select(PettyCashReplenishmentExpense).filter_by(petty_cash_expense_id=ids["expense_id"])
            )
            .scalars()
            .all()
        )
        assert len(vinculos) == 1
