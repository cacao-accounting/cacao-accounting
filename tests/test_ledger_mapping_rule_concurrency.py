# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2138: dos altas concurrentes no dejan reglas de mapeo ambiguas.

La comprobación de duplicados y la inserción se serializan por la identidad
de la regla (libro origen, libro destino y cuenta origen). La variante
PostgreSQL ejerce la rama `ON CONFLICT` + `SELECT FOR UPDATE` y confirma en
`pg_stat_activity` que la segunda sesión espera realmente por el lock.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock
from time import monotonic
from uuid import uuid4

import pytest
from sqlalchemy import text

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
import cacao_accounting.default_scope as default_scope
from cacao_accounting.contabilidad.ledger_mapping_service import (
    LedgerMappingError,
    apply_ledger_mappings,
    create_ledger_mapping_rule,
)
from cacao_accounting.database import Accounts, Book, Currency, Entity, GLEntry, LedgerMappingRule, database


def _create_app(uri: str):
    """Construye una aplicación aislada para la URI indicada."""
    return create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": uri,
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 4, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )


def _seed_identidad(app):
    """Siembra la identidad de la regla y devuelve sus referencias."""
    suffix = uuid4().hex[:6].upper()
    currency_code = f"C{suffix}"
    with app.app_context():
        database.create_all()
        database.session.add(Currency(code=currency_code, name="Córdoba", decimals=2, active=True, default=True))
        company = Entity(
            code=f"L{suffix}",
            name="Compañía mapeo",
            company_name="Compañía mapeo SA",
            tax_id=f"L{suffix}",
            currency=currency_code,
            enabled=True,
            status="default",
        )
        database.session.add(company)
        database.session.flush()
        primary = Book(
            code=f"P{suffix}",
            name="Primario",
            entity=company.code,
            currency=currency_code,
            status="activo",
            is_primary=True,
        )
        secondary = Book(
            code=f"S{suffix}",
            name="Secundario",
            entity=company.code,
            currency=currency_code,
            status="activo",
            is_primary=False,
        )
        database.session.add_all([primary, secondary])
        database.session.flush()
        source_account = Accounts(
            entity=company.code,
            code=f"1{suffix}",
            name="Origen",
            classification="asset",
            active=True,
            enabled=True,
        )
        target_a = Accounts(
            entity=company.code,
            code=f"2{suffix}",
            name="Destino A",
            classification="asset",
            active=True,
            enabled=True,
        )
        target_b = Accounts(
            entity=company.code,
            code=f"3{suffix}",
            name="Destino B",
            classification="asset",
            active=True,
            enabled=True,
        )
        database.session.add_all([source_account, target_a, target_b])
        database.session.commit()
        ids = {
            "company": company.code,
            "currency": currency_code,
            "source_book": primary.code,
            "target_book": secondary.code,
            "source_account": source_account.id,
            "targets": [target_a.id, target_b.id],
            "books": [primary.code, secondary.code],
        }
        database.session.remove()
    return ids


def _assert_una_regla_activa(app, ids) -> None:
    """Comprueba que persiste una sola regla activa para la identidad."""
    with app.app_context():
        rules = (
            database.session.execute(
                database.select(LedgerMappingRule).filter_by(
                    source_book=ids["source_book"],
                    target_book=ids["target_book"],
                    source_account_id=ids["source_account"],
                    is_active=True,
                )
            )
            .scalars()
            .all()
        )
        assert len(rules) == 1
        database.session.remove()


def _limpiar(app, ids) -> None:
    """Retira solo las filas creadas por la prueba en un motor compartido."""
    with app.app_context():
        database.session.execute(
            database.delete(LedgerMappingRule).filter_by(
                source_book=ids["source_book"],
                target_book=ids["target_book"],
                source_account_id=ids["source_account"],
            )
        )
        database.session.execute(database.delete(Accounts).where(Accounts.id.in_(ids["targets"] + [ids["source_account"]])))
        database.session.execute(database.delete(Book).where(Book.code.in_(ids["books"])))
        database.session.execute(database.delete(Entity).where(Entity.code == ids["company"]))
        database.session.execute(database.delete(Currency).where(Currency.code == ids["currency"]))
        database.session.commit()
        database.session.remove()
        database.engine.dispose()


def test_concurrent_mapping_rules_keep_one_target_sqlite(tmp_path):
    """Solo una regla activa prospera para la misma cuenta y libros."""
    app = _create_app(f"sqlite:///{tmp_path / 'ledger-mapping.sqlite'}")
    ids = _seed_identidad(app)
    barrier = Barrier(2, timeout=30)

    def create(target_account_id: str) -> str:
        with app.app_context():
            try:
                barrier.wait(timeout=10)
                create_ledger_mapping_rule(
                    source_book=ids["source_book"],
                    target_book=ids["target_book"],
                    source_account_id=ids["source_account"],
                    target_account_id=target_account_id,
                )
                return "created"
            except LedgerMappingError:
                database.session.rollback()
                return "rejected"
            finally:
                database.session.remove()

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(create, ids["targets"]))
        assert sorted(results) == ["created", "rejected"]
        _assert_una_regla_activa(app, ids)
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.database
def test_concurrent_mapping_rules_mysql_stale_snapshot():
    """MySQL REPEATABLE READ no puede reutilizar el snapshot previo al lock."""
    configured_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if not configured_uri.startswith("mysql"):
        pytest.skip("Este caso requiere MySQL/InnoDB bajo REPEATABLE READ.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")

    app = _create_app(configured_uri)
    ids = _seed_identidad(app)
    barrier = Barrier(2, timeout=30)

    def create(target_account_id: str) -> str:
        with app.app_context():
            try:
                # Fija el snapshot consistente antes de competir por el lock.
                database.session.execute(database.select(Currency.id).limit(1)).scalar_one_or_none()
                barrier.wait(timeout=10)
                create_ledger_mapping_rule(
                    source_book=ids["source_book"],
                    target_book=ids["target_book"],
                    source_account_id=ids["source_account"],
                    target_account_id=target_account_id,
                )
                return "created"
            except LedgerMappingError:
                database.session.rollback()
                return "rejected"
            finally:
                database.session.remove()

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(create, ids["targets"]))
        assert sorted(results) == ["created", "rejected"], results
        _assert_una_regla_activa(app, ids)
    finally:
        _limpiar(app, ids)


def _confirmar_espera_por_lock(app, pid: int, timeout: float) -> str:
    """Confirma en pg_stat_activity que la sesión indicada espera por un lock."""
    limite = monotonic() + timeout
    with app.app_context():
        while monotonic() < limite:
            espera = (
                database.session.execute(
                    text("SELECT wait_event_type, wait_event FROM pg_stat_activity WHERE pid = :pid"),
                    {"pid": pid},
                )
                .mappings()
                .first()
            )
            if espera is not None and espera["wait_event_type"] == "Lock":
                return str(espera["wait_event"])
            database.session.remove()
    pytest.fail(f"La sesión {pid} no esperó por el lock en {timeout} s.")
    return ""


@pytest.mark.database
def test_concurrent_mapping_rules_keep_one_target_postgresql(monkeypatch):
    """La segunda sesión espera por el lock real antes de ver la regla confirmada."""
    configured_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if not configured_uri.startswith("postgresql"):
        pytest.skip("Este caso requiere el lock ON CONFLICT de PostgreSQL.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")

    app = _create_app(configured_uri)
    ids = _seed_identidad(app)
    real_lock = default_scope.lock_default_scope
    primera_bloqueada = Event()
    liberar_primera = Event()
    segunda_en_lock = Event()
    pid_segundo: list[int] = []
    contador = 0
    guarda = Lock()

    def lock_instrumentado(*partes: str | None) -> None:
        """Pausa la primera transacción y registra el PID de la segunda."""
        nonlocal contador
        with guarda:
            contador += 1
            orden = contador
        if orden == 1:
            real_lock(*partes)
            primera_bloqueada.set()
            assert liberar_primera.wait(timeout=25)
            return
        if orden == 2:
            pid = database.session.execute(text("SELECT pg_backend_pid()")).scalar_one()
            pid_segundo.append(int(pid))
            segunda_en_lock.set()
        real_lock(*partes)

    monkeypatch.setattr(default_scope, "lock_default_scope", lock_instrumentado)

    def create(target_account_id: str) -> str:
        with app.app_context():
            try:
                create_ledger_mapping_rule(
                    source_book=ids["source_book"],
                    target_book=ids["target_book"],
                    source_account_id=ids["source_account"],
                    target_account_id=target_account_id,
                )
                return "created"
            except LedgerMappingError:
                database.session.rollback()
                return "rejected"
            finally:
                database.session.remove()

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(create, ids["targets"][0])
            assert primera_bloqueada.wait(timeout=15)
            second = workers.submit(create, ids["targets"][1])
            assert segunda_en_lock.wait(timeout=15)
            wait_event = _confirmar_espera_por_lock(app, pid_segundo[0], timeout=15)
            assert wait_event
            liberar_primera.set()
            assert first.result(timeout=25) == "created"
            assert second.result(timeout=25) == "rejected"
        _assert_una_regla_activa(app, ids)
    finally:
        liberar_primera.set()
        primera_bloqueada.set()
        segunda_en_lock.set()
        _limpiar(app, ids)


def test_mapeo_aplica_solo_libro_destino_y_compania(tmp_path):
    """La regla transforma el libro secundario propio y no toca otra compañía."""
    uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if uri.startswith("sqlite"):
        uri = f"sqlite:///{tmp_path / 'mapping-books.sqlite'}"
    app = _create_app(uri)
    ids = _seed_identidad(app)
    other_suffix = uuid4().hex[:6].upper()
    with app.app_context():
        other_currency = Currency(code=f"X{other_suffix}", name="Otra", decimals=2, active=True, default=False)
        other_company = Entity(
            code=f"X{other_suffix}",
            name="Otra compañía",
            company_name=f"Otra {other_suffix} SA",
            tax_id=f"X{other_suffix}",
            currency=other_currency.code,
            enabled=True,
            status="default",
        )
        database.session.add_all([other_currency, other_company])
        database.session.flush()
        other_primary = Book(
            code=f"XP{other_suffix}",
            name="Primario",
            entity=other_company.code,
            currency=other_currency.code,
            status="activo",
            is_primary=True,
        )
        other_secondary = Book(
            code=f"XS{other_suffix}",
            name="Secundario",
            entity=other_company.code,
            currency=other_currency.code,
            status="activo",
            is_primary=False,
        )
        database.session.add_all([other_primary, other_secondary])
        database.session.flush()
        other_account = Accounts(
            entity=other_company.code,
            code=f"X{other_suffix}",
            name="Cuenta",
            classification="asset",
            active=True,
            enabled=True,
        )
        database.session.add(other_account)
        database.session.commit()
        primary = database.session.execute(database.select(Book).filter_by(code=ids["source_book"])).scalar_one()
        secondary = database.session.execute(database.select(Book).filter_by(code=ids["target_book"])).scalar_one()
        source_account = database.session.get(Accounts, ids["source_account"])
        rule = create_ledger_mapping_rule(
            source_book=primary.code,
            target_book=secondary.code,
            source_account_id=source_account.id,
            target_account_id=ids["targets"][0],
        )
        database.session.commit()
        primary_entry = GLEntry(
            company=ids["company"], ledger_id=primary.id, account_id=source_account.id, account_code=source_account.code
        )
        secondary_entry = GLEntry(
            company=ids["company"], ledger_id=secondary.id, account_id=source_account.id, account_code=source_account.code
        )
        foreign_entry = GLEntry(
            company=other_company.code,
            ledger_id=other_primary.id,
            account_id=other_account.id,
            account_code=other_account.code,
        )
        apply_ledger_mappings([primary_entry, secondary_entry, foreign_entry])
        assert primary_entry.account_id == source_account.id
        assert secondary_entry.account_id == ids["targets"][0]
        assert foreign_entry.account_id == other_account.id
        database.session.execute(database.delete(LedgerMappingRule).filter_by(id=rule.id))
        database.session.execute(
            database.delete(Accounts).where(Accounts.id.in_([source_account.id, *ids["targets"], other_account.id]))
        )
        database.session.execute(
            database.delete(Book).where(
                Book.code.in_([primary.code, secondary.code, other_primary.code, other_secondary.code])
            )
        )
        database.session.execute(database.delete(Entity).where(Entity.code.in_([ids["company"], other_company.code])))
        database.session.execute(database.delete(Currency).where(Currency.code.in_([ids["currency"], other_currency.code])))
        database.session.commit()
        database.session.remove()
        database.engine.dispose()
