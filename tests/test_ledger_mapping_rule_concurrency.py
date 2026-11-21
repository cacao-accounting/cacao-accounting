# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2138: dos altas concurrentes no dejan reglas de mapeo ambiguas.

La comprobación de duplicados y la inserción se serializan por la identidad
de la regla (libro origen, libro destino y cuenta origen).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.ledger_mapping_service import (
    LedgerMappingError,
    create_ledger_mapping_rule,
)
from cacao_accounting.database import Accounts, Book, Currency, Entity, LedgerMappingRule, database


def test_concurrent_mapping_rules_keep_one_target(tmp_path):
    """Solo una regla activa prospera para la misma cuenta y libros."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'ledger-mapping.sqlite'}",
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 4, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:6].upper()
    with app.app_context():
        database.create_all()
        currency = Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True)
        company = Entity(
            code=f"L{suffix}",
            name="Compañía mapeo",
            company_name="Compañía mapeo SA",
            tax_id=f"L{suffix}",
            currency="NIO",
            enabled=True,
            status="default",
        )
        database.session.add_all([currency, company])
        database.session.flush()
        primary = Book(
            code=f"P{suffix}",
            name="Primario",
            entity=company.code,
            currency="NIO",
            status="activo",
            is_primary=True,
        )
        secondary = Book(
            code=f"S{suffix}",
            name="Secundario",
            entity=company.code,
            currency="NIO",
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
            "source_book": primary.code,
            "target_book": secondary.code,
            "source_account": source_account.id,
            "targets": [target_a.id, target_b.id],
        }
        database.session.remove()

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

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(create, ids["targets"]))

    assert sorted(results) == ["created", "rejected"]
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
        database.engine.dispose()
