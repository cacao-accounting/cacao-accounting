# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2138: dos altas concurrentes no dejan reglas de mapeo ambiguas.

La comprobación de duplicados y la inserción se serializan por la identidad
de la regla (libro origen, libro destino y cuenta origen). La variante
PostgreSQL ejerce además la rama `ON CONFLICT` + `SELECT FOR UPDATE` del lock.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Barrier, Event
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.ledger_mapping_service import (
    LedgerMappingError,
    create_ledger_mapping_rule,
)
from cacao_accounting.database import Accounts, Book, Currency, Entity, LedgerMappingRule, database
from cacao_accounting.default_scope import lock_default_scope


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
    barrier = Barrier(2)

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
def test_concurrent_mapping_rules_keep_one_target_postgresql():
    """PostgreSQL serializa por el lock y la segunda alta ve la regla confirmada."""
    configured_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if not configured_uri.startswith("postgresql"):
        pytest.skip("Este caso requiere el lock ON CONFLICT de PostgreSQL.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")

    app = _create_app(configured_uri)
    ids = _seed_identidad(app)
    first_locked = Event()
    second_started = Event()

    def create_first() -> str:
        with app.app_context():
            try:
                lock_default_scope("ledger_mapping", ids["source_book"], ids["target_book"], ids["source_account"])
                first_locked.set()
                create_ledger_mapping_rule(
                    source_book=ids["source_book"],
                    target_book=ids["target_book"],
                    source_account_id=ids["source_account"],
                    target_account_id=ids["targets"][0],
                )
                return "created"
            except LedgerMappingError:
                database.session.rollback()
                return "rejected"
            finally:
                database.session.remove()

    def create_second() -> str:
        with app.app_context():
            try:
                assert first_locked.wait(timeout=15)
                second_started.set()
                create_ledger_mapping_rule(
                    source_book=ids["source_book"],
                    target_book=ids["target_book"],
                    source_account_id=ids["source_account"],
                    target_account_id=ids["targets"][1],
                )
                return "created"
            except LedgerMappingError:
                database.session.rollback()
                return "rejected"
            finally:
                database.session.remove()

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(create_first)
            assert first_locked.wait(timeout=15)
            second = workers.submit(create_second)
            assert second_started.wait(timeout=15)
            with pytest.raises(TimeoutError):
                second.result(timeout=0.5)
            assert first.result(timeout=20) == "created"
            assert second.result(timeout=20) == "rejected"
        _assert_una_regla_activa(app, ids)
    finally:
        first_locked.set()
        second_started.set()
        _limpiar(app, ids)
