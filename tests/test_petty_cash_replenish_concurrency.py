# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1093/#1094: dos solicitudes concurrentes no reservan el mismo gasto."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier, Event, Lock
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    Bank,
    BankAccount,
    Book,
    CompanyDefaultAccount,
    Currency,
    Entity,
    FiscalYear,
    GLEntry,
    PaymentEntry,
    PettyCashAccount,
    PettyCashExpense,
    PettyCashReplenishment,
    PettyCashReplenishmentExpense,
    User,
    database,
)
from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company

pytestmark = pytest.mark.database

ES_SQLITE = str(configuracion["SQLALCHEMY_DATABASE_URI"]).startswith("sqlite")


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
            "MODO_ESCRITORIO": True,
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
        database.session.flush()
        anio = FiscalYear(
            entity=empresa,
            name="2026",
            year_start_date=date(2026, 1, 1),
            year_end_date=date(2026, 12, 31),
            is_closed=False,
        )
        database.session.add(anio)
        database.session.flush()
        database.session.add(
            AccountingPeriod(
                entity=empresa,
                fiscal_year_id=anio.id,
                name="Octubre 2026",
                start=date(2026, 10, 1),
                end=date(2026, 10, 31),
                enabled=True,
                is_closed=False,
            )
        )
        database.session.add(
            Book(
                entity=empresa,
                code=f"B{empresa[1:]}",
                name="Libro caja chica",
                status="activo",
                is_primary=True,
                currency="NIO",
            )
        )
        cuenta_banco = Accounts(
            entity=empresa,
            code=f"BK-{empresa}",
            name="Banco caja chica",
            classification="asset",
            account_type="bank",
            active=True,
            enabled=True,
            group=False,
        )
        cuenta_gasto = Accounts(
            entity=empresa,
            code=f"GX-{empresa}",
            name="Gasto caja chica",
            classification="expense",
            account_type="expense",
            active=True,
            enabled=True,
            group=False,
        )
        database.session.add_all([cuenta_banco, cuenta_gasto])
        database.session.flush()
        database.session.add(
            CompanyDefaultAccount(
                company=empresa,
                default_cash=cuenta.id,
                default_bank=cuenta_banco.id,
                default_expense=cuenta_gasto.id,
            )
        )
        banco = Bank(name=f"Banco {empresa}")
        database.session.add(banco)
        database.session.flush()
        cuenta_bancaria = BankAccount(
            company=empresa,
            bank_id=banco.id,
            account_name=f"Cuenta {empresa}",
            account_no=f"AC-{empresa}",
            currency="NIO",
            is_active=True,
            gl_account_id=cuenta_banco.id,
        )
        database.session.add(cuenta_bancaria)
        database.session.flush()
        solicitud = PettyCashReplenishment(
            company=empresa,
            petty_cash_id=fondo.id,
            request_date=date(2026, 10, 19),
            amount=Decimal("85.00"),
            status="aprobado",
            docstatus=1,
        )
        database.session.add(solicitud)
        usuario = User(
            id=f"admin-{empresa}",
            user=f"admin_{empresa}",
            name="Admin caja chica",
            password=b"unused",
            active=True,
            classification="admin",
        )
        database.session.add(usuario)
        database.session.flush()
        ensure_default_naming_series_for_company(empresa)
        database.session.commit()
        ids = {
            "company": empresa,
            "fund_id": fondo.id,
            "expense_id": gasto.id,
            "bank_id": cuenta_bancaria.id,
            "replenishment_id": solicitud.id,
            "user_id": usuario.id,
        }
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


def _reembolsar(app, ids, barrera: Barrier | None) -> str:
    from flask_login import login_user

    from cacao_accounting.bancos.services import replenish_petty_cash

    with app.test_request_context("/"):
        login_user(database.session.get(User, ids["user_id"]))
        try:
            if barrera is not None:
                barrera.wait(timeout=10)
            solicitud = database.session.get(PettyCashReplenishment, ids["replenishment_id"])
            replenish_petty_cash(solicitud, bank_account_id=ids["bank_id"])
            return "reembolsada"
        except ValueError:
            database.session.rollback()
            return "rechazada"
        finally:
            database.session.remove()


@pytest.mark.skipif(ES_SQLITE, reason="La exclusión FOR UPDATE se verifica en PostgreSQL/MySQL.")
def test_el_segundo_reembolso_espera_mientras_el_primero_tiene_el_lock(caja_chica_app, monkeypatch):
    """La segunda transacción no avanza hasta que la primera libera el lock."""
    from cacao_accounting.bancos import services

    app, ids = caja_chica_app
    original = services._lock_row_for_transition
    first_locked = Event()
    second_started = Event()
    release = Event()
    calls: list[int] = []
    calls_lock = Lock()

    def lock_observable(model, record_id):
        with calls_lock:
            calls.append(1)
            number = len(calls)
        if number == 1:
            locked = original(model, record_id)
            first_locked.set()
            assert release.wait(timeout=10)
            return locked
        second_started.set()
        return original(model, record_id)

    monkeypatch.setattr(services, "_lock_row_for_transition", lock_observable)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(_reembolsar, app, ids, None)
        assert first_locked.wait(timeout=10)
        second = pool.submit(_reembolsar, app, ids, None)
        try:
            assert second_started.wait(timeout=10)
            assert second.done() is False, "El segundo reembolso no esperó el lock"
        finally:
            release.set()
        resultados = [first.result(timeout=10), second.result(timeout=10)]

    assert resultados.count("reembolsada") == 1, resultados
    with app.app_context():
        solicitud = database.session.get(PettyCashReplenishment, ids["replenishment_id"])
        assert solicitud is not None
        assert solicitud.status == "reembolsado"
        assert solicitud.bank_debit_note_id
        pagos = database.session.execute(database.select(PaymentEntry).filter_by(company=ids["company"])).scalars().all()
        assert len(pagos) == 1
        gl = (
            database.session.execute(database.select(GLEntry).filter_by(voucher_type="payment_entry", voucher_id=pagos[0].id))
            .scalars()
            .all()
        )
        assert gl
        assert sum(fila.debit for fila in gl) == sum(fila.credit for fila in gl)


def test_dos_reembolsos_concurrentes_crean_una_sola_nota(caja_chica_app):
    """Dos pagos simultáneos de la misma solicitud dejan una sola nota y un GL."""
    app, ids = caja_chica_app
    barrera = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(lambda _: _reembolsar(app, ids, barrera), range(2)))

    assert resultados.count("reembolsada") == 1, resultados
    with app.app_context():
        solicitud = database.session.get(PettyCashReplenishment, ids["replenishment_id"])
        assert solicitud.status == "reembolsado"
        assert solicitud.bank_debit_note_id
        pagos = (
            database.session.execute(
                database.select(PaymentEntry).filter_by(
                    company=ids["company"], payment_type="debit_note", posting_date=date(2026, 10, 19)
                )
            )
            .scalars()
            .all()
        )
        assert len(pagos) == 1
        gl = (
            database.session.execute(database.select(GLEntry).filter_by(voucher_type="payment_entry", voucher_id=pagos[0].id))
            .scalars()
            .all()
        )
        assert gl
        assert sum(fila.debit for fila in gl) == sum(fila.credit for fila in gl)
