# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2082: la conciliación de caja chica serializa su creación."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.bancos import services as bank_services
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Book,
    Currency,
    Entity,
    PettyCashAccount,
    PettyCashReconciliation,
    database,
)


def test_creacion_serializa_y_rechaza_duplicado(app, entorno_contable, monkeypatch):
    """El lock precede al chequeo y la segunda creación es un ValueError."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        cuenta = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
        fondo = PettyCashAccount(
            company="cacao",
            account_id=cuenta.id,
            name=f"Caja {suffix}",
            currency="NIO",
            float_amount=Decimal("100"),
            is_default=False,
            is_active=True,
        )
        database.session.add(fondo)
        database.session.commit()
        fondo_id = fondo.id

    llamadas: list[tuple] = []
    original = bank_services.lock_default_scope

    def tracking(*args, **kwargs):
        llamadas.append(args)
        original(*args, **kwargs)

    monkeypatch.setattr(bank_services, "lock_default_scope", tracking)
    with app.app_context():
        bank_services.create_petty_cash_reconciliation(
            company="cacao",
            petty_cash_id=fondo_id,
            reconciliation_date=date(2026, 5, 15),
            counted_cash=Decimal("100"),
        )
        with pytest.raises(ValueError, match="Ya existe una conciliación"):
            bank_services.create_petty_cash_reconciliation(
                company="cacao",
                petty_cash_id=fondo_id,
                reconciliation_date=date(2026, 5, 15),
                counted_cash=Decimal("100"),
            )

    assert any(args and args[0] == "petty_cash_reconciliation" for args in llamadas)


@pytest.mark.database
def test_concurrencia_postgresql_persiste_una_sola_conciliacion():
    """Dos conexiones PostgreSQL concurrentes obtienen una sola conciliación."""
    app = create_app({**configuracion, "TESTING": True, "WTF_CSRF_ENABLED": False})
    with app.app_context():
        if database.engine.dialect.name != "postgresql":
            pytest.skip("La carrera de base de datos requiere PostgreSQL.")
        suffix = uuid4().hex[:7]
        company = f"pc{suffix}"
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
            database.session.flush()
        database.session.add(
            Entity(
                code=company,
                name=company,
                company_name=f"Caja {suffix}",
                tax_id=f"PC-{suffix}",
                currency="NIO",
                enabled=True,
            )
        )
        database.session.flush()
        database.session.add(
            Book(
                entity=company,
                code=f"B{suffix}",
                name="Libro",
                status="activo",
                is_primary=True,
                currency="NIO",
            )
        )
        account = Accounts(entity=company, code=f"pc{suffix}", name="Caja", active=True, enabled=True)
        database.session.add(account)
        database.session.flush()
        fund = PettyCashAccount(
            company=company,
            account_id=account.id,
            name="Fondo",
            currency="NIO",
            float_amount=Decimal("100"),
            is_default=False,
            is_active=True,
        )
        database.session.add(fund)
        database.session.commit()
        fund_id = fund.id

    barrier = Barrier(2, timeout=30)

    def create_one(_):
        with app.app_context():
            try:
                barrier.wait(timeout=10)
                bank_services.create_petty_cash_reconciliation(
                    company=company,
                    petty_cash_id=fund_id,
                    reconciliation_date=date(2026, 5, 15),
                    counted_cash=Decimal("100"),
                )
                return "created"
            except ValueError:
                return "duplicate"
            finally:
                database.session.remove()

    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(create_one, range(2)))

    with app.app_context():
        persisted = database.session.scalars(
            database.select(PettyCashReconciliation).filter_by(company=company, petty_cash_id=fund_id)
        ).all()
        assert sorted(outcomes) == ["created", "duplicate"]
        assert len(persisted) == 1


def test_post_rechazado_conserva_datos_ingresados(app, entorno_contable, authenticated_client):
    """Un duplicado no debe borrar los datos del borrador que el usuario ingresó."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        cuenta = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
        fondo = PettyCashAccount(
            company="cacao",
            account_id=cuenta.id,
            name=f"Caja {suffix}",
            currency="NIO",
            float_amount=Decimal("100"),
            is_default=False,
            is_active=True,
        )
        database.session.add(fondo)
        database.session.commit()
        fund_id = fondo.id
        bank_services.create_petty_cash_reconciliation(
            company="cacao",
            petty_cash_id=fund_id,
            reconciliation_date=date(2026, 5, 16),
            counted_cash=Decimal("100"),
        )

    response = authenticated_client().post(
        "/cash_management/petty-cash-reconciliation/new",
        data={
            "company": "cacao",
            "petty_cash_id": fund_id,
            "reconciliation_date": "2026-05-16",
            "counted_cash": "42.75",
            "explanation": "Confirmación POS 98765",
        },
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Ya existe una conciliación para esa caja y fecha." in body
    assert 'value="cacao"' in body
    assert f'<option value="{fund_id}" selected' in body
    assert 'value="2026-05-16"' in body
    assert 'value="42.75"' in body
    assert "Confirmación POS 98765" in body


def test_conflicto_de_unicidad_se_traduce_y_libera_la_sesion(app, entorno_contable, monkeypatch):
    """La defensa de unicidad convierte IntegrityError en ValueError y revierte."""
    del entorno_contable
    suffix = uuid4().hex[:8]
    with app.app_context():
        cuenta = database.session.execute(database.select(Accounts).filter_by(entity="cacao", code="1101")).scalar_one()
        fondo = PettyCashAccount(
            company="cacao",
            account_id=cuenta.id,
            name=f"Caja {suffix}",
            currency="NIO",
            float_amount=Decimal("100"),
            is_default=False,
            is_active=True,
        )
        database.session.add(fondo)
        database.session.commit()
        fondo_id = fondo.id
        bank_services.create_petty_cash_reconciliation(
            company="cacao",
            petty_cash_id=fondo_id,
            reconciliation_date=date(2026, 5, 20),
            counted_cash=Decimal("100"),
        )
        # Fuerza la colisión de unicidad: el prechequeo no ve la fila existente.
        monkeypatch.setattr(bank_services, "_existing_petty_cash_reconciliation", lambda *args, **kwargs: None)

        with pytest.raises(ValueError, match="Ya existe una conciliación"):
            bank_services.create_petty_cash_reconciliation(
                company="cacao",
                petty_cash_id=fondo_id,
                reconciliation_date=date(2026, 5, 20),
                counted_cash=Decimal("100"),
            )

        bank_services.create_petty_cash_reconciliation(
            company="cacao",
            petty_cash_id=fondo_id,
            reconciliation_date=date(2026, 5, 21),
            counted_cash=Decimal("100"),
        )
        filas = (
            database.session.execute(database.select(PettyCashReconciliation).filter_by(petty_cash_id=fondo_id))
            .scalars()
            .all()
        )

    assert len(filas) == 2
    assert len([fila for fila in filas if fila.reconciliation_date == date(2026, 5, 20)]) == 1
