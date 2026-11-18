# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1051: identidad fiscal global normalizada y única.

La reimportación rechaza una identificación ya registrada; la base impone
la unicidad y las bases existentes se auditan sin fusionar duplicados.
"""

from __future__ import annotations

import sqlite3
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Party, database
from cacao_accounting.imports.adapters.customer import CustomerAdapter
from cacao_accounting.imports.adapters.vendor import VendorAdapter
from cacao_accounting.party_identity import normalize_tax_id


@pytest.fixture
def tax_id_scenario():
    """Create one customer and one supplier with normalized tax ids."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with app.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.add_all(
            [
                Party(
                    code=f"C-{uuid4().hex[:8]}",
                    name="Cliente existente",
                    tax_id="J-123456",
                    is_customer=True,
                    is_active=True,
                ),
                Party(
                    code=f"P-{uuid4().hex[:8]}",
                    name="Proveedor existente",
                    tax_id="RUC 9988",
                    is_supplier=True,
                    is_active=True,
                ),
            ]
        )
        database.session.commit()

    yield app

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def test_normalize_tax_id_ignores_formatting():
    """Case, spaces, hyphens and dots do not create a second identity."""
    assert normalize_tax_id(" j-123.456 ") == "J123456"
    assert normalize_tax_id("RUC 9988") == "RUC9988"
    assert normalize_tax_id(None) is None
    assert normalize_tax_id("   ") is None


def test_database_rejects_a_second_party_with_the_same_normalized_tax_id(tax_id_scenario):
    """The unique key is enforced before commit."""
    app = tax_id_scenario

    with app.app_context():
        database.session.add(
            Party(
                code=f"D-{uuid4().hex[:8]}",
                name="Duplicado",
                tax_id="j123456",
                is_customer=True,
                is_active=True,
            )
        )
        with pytest.raises(IntegrityError):
            database.session.flush()
        database.session.rollback()


@pytest.mark.parametrize(
    ("adapter", "existing"),
    [
        (CustomerAdapter(), " J-123 456 "),
        (VendorAdapter(), "ruc-9988"),
    ],
)
def test_import_validation_rejects_an_existing_identity(tax_id_scenario, adapter, existing):
    """Import validation reports the duplicate before persisting."""
    app = tax_id_scenario

    with app.app_context():
        errors = adapter.validate_row({"nombre": "Tercero", "identificacion_fiscal": existing})

    assert any("ya está registrada" in error for error in errors)


def test_import_persist_rechecks_and_does_not_duplicate(tax_id_scenario):
    """A direct persist call also fails and leaves a single Party row."""
    app = tax_id_scenario
    adapter = CustomerAdapter()

    with app.app_context():
        documents = adapter.build_document(
            [{"nombre": "Nuevo cliente", "identificacion_fiscal": "J-123456"}],
            {"company_id": None},
        )
        with pytest.raises(ValueError):
            adapter.persist_document(documents)
        database.session.rollback()
        count = database.session.execute(
            database.select(database.func.count()).select_from(Party).where(Party.tax_id_key == "J123456")
        ).scalar_one()

    assert count == 1


def test_existing_database_backfills_unique_keys_without_merging(tmp_path):
    """Legacy duplicates keep NULL keys and are reported; unique ids get keys."""
    database_path = tmp_path / "legacy-party.sqlite"
    connection = sqlite3.connect(database_path)
    connection.executescript("""
        CREATE TABLE party (
            id VARCHAR(26) PRIMARY KEY,
            code VARCHAR(50) NOT NULL,
            name VARCHAR(150) NOT NULL,
            tax_id VARCHAR(50),
            modified DATETIME
        );
        INSERT INTO party VALUES ('01A', 'A', 'Tercero A', 'J-100', NULL);
        INSERT INTO party VALUES ('01B', 'B', 'Tercero B', 'j100', NULL);
        INSERT INTO party VALUES ('01C', 'C', 'Tercero C', 'RUC-200', NULL);
        """)
    connection.commit()
    connection.close()

    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )

    connection = sqlite3.connect(database_path)
    rows = dict(connection.execute("SELECT id, tax_id_key FROM party").fetchall())
    indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")}
    connection.close()

    assert rows["01A"] is None
    assert rows["01B"] is None
    assert rows["01C"] == "RUC200"
    assert "uq_party_tax_id_key" in indexes

    with app.app_context():
        assert database.session.execute(database.select(database.func.count(Party.id))).scalar_one() == 3
        database.session.remove()
        database.engine.dispose()
