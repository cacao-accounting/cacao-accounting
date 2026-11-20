# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1319: la identidad del movimiento bancario es única en la base.

La comprobación previa del adaptador no basta ante dos importaciones que leen
antes de que la otra confirme. La base impone unicidad sobre ``identity_key`` y
el adaptador traduce únicamente ese conflicto a un error de negocio, sin
enmascarar otros errores de integridad ni invalidar la transacción externa.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Bank,
    BankAccount,
    BankTransaction,
    Currency,
    Entity,
    database,
)
from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter

MOVEMENT_DATE = date(2026, 5, 15)
DUPLICATE_MESSAGE = "La transacción bancaria ya existe en la base de datos."


def _scenario_settings() -> dict:
    """Configuración aislada para las pruebas de identidad bancaria."""
    return {
        **configuracion,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
        "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool},
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "WTF_CSRF_ENABLED": False,
        "TESTING": True,
        "MODO_ESCRITORIO": False,
    }


def _seed_bank_scenario(app) -> tuple[str, str]:
    """Crea compañía, banco y cuenta únicos y devuelve sus identificadores."""
    suffix = uuid4().hex[:8]
    company_code = f"B{suffix}"
    account_no = f"ACC-{suffix}"
    with app.app_context():
        database.create_all()
        currency = Currency(code=f"C{suffix}", name="Moneda bancaria", decimals=2, active=True, default=False)
        company = Entity(
            code=company_code,
            name=f"Empresa bancaria {suffix}",
            company_name=f"Empresa bancaria {suffix} SA",
            tax_id=f"T{suffix}",
            currency=currency.code,
            enabled=True,
            status="activo",
        )
        database.session.add_all([currency, company])
        database.session.flush()
        bank = Bank(name=f"Banco {suffix}")
        database.session.add(bank)
        database.session.flush()
        account = BankAccount(
            company=company_code,
            bank_id=bank.id,
            account_name=f"Cuenta {suffix}",
            account_no=account_no,
            currency=currency.code,
            is_active=True,
        )
        database.session.add(account)
        database.session.commit()
        account_id = account.id
    return company_code, account_id


def _cleanup_bank_scenario(app, company_code: str, account_id: str) -> None:
    """Retira los datos únicos de la prueba sin tocar el resto del catálogo."""
    with app.app_context():
        database.session.rollback()
        account = database.session.get(BankAccount, account_id)
        if account is not None:
            bank = database.session.get(Bank, account.bank_id)
            database.session.execute(database.delete(BankTransaction).where(BankTransaction.bank_account_id == account_id))
            database.session.delete(account)
            database.session.flush()
            if bank is not None:
                database.session.delete(bank)
        company = database.session.execute(database.select(Entity).filter_by(code=company_code)).scalar_one_or_none()
        currency_code = company.currency if company is not None else None
        if company is not None:
            database.session.delete(company)
            database.session.flush()
        if currency_code:
            currency = database.session.execute(database.select(Currency).filter_by(code=currency_code)).scalar_one_or_none()
            if currency is not None:
                database.session.delete(currency)
        database.session.commit()
        database.session.remove()
        database.engine.dispose()


@pytest.fixture
def bank_identity_scenario():
    """Aplicación SQLite en memoria con una cuenta bancaria utilizable."""
    app = create_app(_scenario_settings())
    company_code, account_id = _seed_bank_scenario(app)
    try:
        yield app, company_code, account_id
    finally:
        _cleanup_bank_scenario(app, company_code, account_id)


def _movement(account_id: str, reference: str | None = "MOV-1", deposit: Decimal = Decimal("10")) -> dict:
    """Documento normalizado equivalente al que produce ``build_document``."""
    return {
        "bank_account_id": account_id,
        "posting_date": MOVEMENT_DATE,
        "reference_number": reference,
        "description": "Movimiento bancario",
        "deposit": deposit,
        "withdrawal": None,
    }


def test_unique_constraint_rejects_a_duplicate_identity_key(bank_identity_scenario):
    """La base rechaza dos movimientos con la misma identidad económica."""
    app, _, account_id = bank_identity_scenario

    with app.app_context():
        first = BankTransaction(**_movement(account_id))
        database.session.add(first)
        database.session.commit()
        assert first.identity_key

        unique_constraints = {
            constraint["name"]: constraint
            for constraint in database.inspect(database.engine).get_unique_constraints("bank_transaction")
        }
        assert "uq_bank_transaction_identity" in unique_constraints
        assert unique_constraints["uq_bank_transaction_identity"]["column_names"] == ["identity_key"]

        duplicate = BankTransaction(**_movement(account_id))
        database.session.add(duplicate)
        with pytest.raises(IntegrityError) as error:
            database.session.flush()
        assert "identity_key" in str(error.value.orig)
        database.session.rollback()

        assert (
            database.session.execute(
                database.select(database.func.count())
                .select_from(BankTransaction)
                .where(BankTransaction.bank_account_id == account_id)
            ).scalar_one()
            == 1
        )


def test_adapter_translates_a_real_unique_conflict(bank_identity_scenario):
    """El conflicto de la restricción se convierte en error de negocio controlado.

    La fila existente guarda ``reference_number`` NULL y la importación envía la
    cadena vacía. La comprobación previa no las iguala, así que el rechazo solo
    puede provenir de la restricción única de la base.
    """
    app, company_code, account_id = bank_identity_scenario

    with app.app_context():
        existing = BankTransaction(**_movement(account_id, reference=None))
        database.session.add(existing)
        database.session.commit()

        document = [
            {
                **_movement(account_id, reference=""),
                "company_id": company_code,
                "description": "Misma identidad, otra descripción",
            }
        ]
        with pytest.raises(ValueError, match="ya existe") as error:
            BankStatementAdapter().persist_document(document)

        assert str(error.value) == DUPLICATE_MESSAGE
        assert isinstance(error.value.__cause__, IntegrityError)
        assert "identity_key" in str(error.value.__cause__.orig)

        # El savepoint revierte solo la fila conflictiva: la transacción
        # externa sigue operativa y no quedó una segunda transacción.
        assert (
            database.session.execute(
                database.select(database.func.count())
                .select_from(BankTransaction)
                .where(BankTransaction.bank_account_id == account_id)
            ).scalar_one()
            == 1
        )
        database.session.rollback()


def test_adapter_rejects_a_sequential_duplicate_import(bank_identity_scenario):
    """Repetir la importación no duplica y conserva el mensaje de conflicto."""
    app, company_code, account_id = bank_identity_scenario
    adapter = BankStatementAdapter()
    document = adapter.build_document([_movement(account_id, reference="IMP-1")], {"company_id": company_code})

    with app.app_context():
        adapter.persist_document(document)
        database.session.commit()

        repeated = adapter.build_document([_movement(account_id, reference="IMP-1")], {"company_id": company_code})
        with pytest.raises(ValueError, match="ya existe") as error:
            adapter.persist_document(repeated)
        assert str(error.value) == DUPLICATE_MESSAGE
        database.session.rollback()

        assert (
            database.session.execute(
                database.select(database.func.count())
                .select_from(BankTransaction)
                .where(BankTransaction.bank_account_id == account_id)
            ).scalar_one()
            == 1
        )

        # Control positivo: otra referencia sí se importa.
        different = adapter.build_document([_movement(account_id, reference="IMP-2")], {"company_id": company_code})
        adapter.persist_document(different)
        database.session.commit()
        assert (
            database.session.execute(
                database.select(database.func.count())
                .select_from(BankTransaction)
                .where(BankTransaction.bank_account_id == account_id)
            ).scalar_one()
            == 2
        )


def test_identity_conflict_detection_ignores_other_integrity_errors():
    """Solo la restricción de identidad bancaria se traduce a conflicto de negocio."""
    from cacao_accounting.imports.adapters.bank_statement import _is_bank_identity_conflict

    sqlite_error = IntegrityError(
        "INSERT INTO bank_transaction",
        {},
        Exception("UNIQUE constraint failed: bank_transaction.identity_key"),
    )
    postgres_error = IntegrityError(
        "INSERT INTO bank_transaction",
        {},
        SimpleNamespace(diag=SimpleNamespace(constraint_name="uq_bank_transaction_identity")),
    )
    unrelated_error = IntegrityError(
        "INSERT INTO party",
        {},
        Exception("UNIQUE constraint failed: party.tax_id_key"),
    )

    assert _is_bank_identity_conflict(sqlite_error)
    assert _is_bank_identity_conflict(postgres_error)
    assert not _is_bank_identity_conflict(unrelated_error)


def _legacy_bank_database(path, identities: tuple[str, ...]) -> None:
    """Crea una base previa al fix, sin restricción única en identity_key."""
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE bank_transaction (
            id VARCHAR(26) PRIMARY KEY,
            identity_key VARCHAR(64) NOT NULL
        );
        """)
    connection.executemany(
        "INSERT INTO bank_transaction (id, identity_key) VALUES (?, ?)",
        [(f"LEGACY-{index}", identity) for index, identity in enumerate(identities, start=1)],
    )
    connection.commit()
    connection.close()


def _legacy_indexes(path) -> dict[str, str]:
    """Devuelve los índices declarados en la base previa."""
    connection = sqlite3.connect(path)
    indexes = {
        row[0]: row[1]
        for row in connection.execute("SELECT name, sql FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")
    }
    connection.close()
    return indexes


def test_startup_installs_the_unique_guard_on_an_existing_database(tmp_path):
    """Una base previa recibe el índice único al arrancar."""
    database_path = tmp_path / "legacy-bank-unique.sqlite"
    _legacy_bank_database(database_path, ("IDENTITY-A", "IDENTITY-B"))

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
    try:
        indexes = _legacy_indexes(database_path)
        assert "uq_bank_transaction_identity" in indexes

        connection = sqlite3.connect(database_path)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO bank_transaction (id, identity_key) VALUES ('LEGACY-3', 'IDENTITY-A')")
        connection.rollback()
        assert connection.execute("SELECT COUNT(*) FROM bank_transaction").fetchone()[0] == 2
        connection.close()
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()


def test_startup_refuses_duplicate_identities_and_preserves_the_rows(tmp_path):
    """Si la base previa ya tiene duplicados, el arranque falla sin borrar evidencia."""
    database_path = tmp_path / "legacy-bank-duplicates.sqlite"
    _legacy_bank_database(database_path, ("IDENTITY-A", "IDENTITY-A"))

    with pytest.raises(RuntimeError, match="unicidad de movimientos bancarios"):
        create_app(
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
    assert connection.execute("SELECT COUNT(*) FROM bank_transaction").fetchone()[0] == 2
    indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    connection.close()
    assert "uq_bank_transaction_identity" not in indexes


@pytest.mark.database
def test_identity_uniqueness_on_the_configured_engine():
    """La misma garantía se cumple en el motor configurado (PostgreSQL/MySQL)."""
    configured_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if configured_uri.startswith("sqlite"):
        pytest.skip("El motor configurado es SQLite; la cobertura por defecto ya lo valida.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")

    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": configured_uri,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    company_code, account_id = _seed_bank_scenario(app)
    try:
        with app.app_context():
            database.session.add(BankTransaction(**_movement(account_id, reference=None)))
            database.session.commit()

            database.session.add(BankTransaction(**_movement(account_id, reference=None)))
            with pytest.raises(IntegrityError) as error:
                database.session.flush()
            assert "identity_key" in str(error.value.orig)
            database.session.rollback()

            with pytest.raises(ValueError, match="ya existe"):
                BankStatementAdapter().persist_document([{**_movement(account_id, reference=""), "company_id": company_code}])
            database.session.rollback()

            assert (
                database.session.execute(
                    database.select(database.func.count())
                    .select_from(BankTransaction)
                    .where(BankTransaction.bank_account_id == account_id)
                ).scalar_one()
                == 1
            )
    finally:
        _cleanup_bank_scenario(app, company_code, account_id)
