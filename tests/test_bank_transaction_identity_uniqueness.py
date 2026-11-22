# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1319: la identidad del movimiento bancario es única en la base.

La comprobación previa del adaptador no basta ante dos importaciones que leen
antes de que la otra confirme. La base impone unicidad sobre ``identity_key`` y
el adaptador traduce únicamente ese conflicto a un error de negocio, sin
enmascarar otros errores de integridad ni invalidar la transacción externa.
"""

from __future__ import annotations

import csv
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
    AccountingPeriod,
    Bank,
    BankAccount,
    BankTransaction,
    Currency,
    Entity,
    database,
)
from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter, _is_bank_identity_conflict
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.services.import_service import ImportService

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
        database.session.add(
            AccountingPeriod(
                entity=company_code,
                name="Mayo 2026",
                start=date(2026, 5, 1),
                end=date(2026, 5, 31),
                enabled=True,
                is_closed=False,
            )
        )
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
        database.session.execute(database.delete(ImportBatch).where(ImportBatch.company_id == company_code))
        database.session.execute(database.delete(AccountingPeriod).where(AccountingPeriod.entity == company_code))
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

    Dos filas con la misma referencia en un mismo lote superan la comprobación
    previa (que excluye las filas recién persistidas) y chocan con la
    restricción única ``uq_bank_transaction_identity``; el adaptador traduce
    ese ``IntegrityError`` a un ``ValueError`` de negocio dentro del savepoint.
    Con referencia se conserva esta deduplicación (#1262); sin referencia la
    identidad usa la procedencia.
    """
    app, company_code, account_id = bank_identity_scenario

    with app.app_context():
        movement = {
            **_movement(account_id, reference="REF-CONFLICT"),
            "company_id": company_code,
        }
        document = [dict(movement), dict(movement)]

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

        # Control positivo: otra identidad económica sí se importa.
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


def _write_bank_statement(path, account_id: str, rows: list[tuple[str, str]]) -> None:
    """Escribe movimientos CSV con referencia informativa y monto de depósito."""
    with path.open("w", encoding="utf-8", newline="") as source:
        writer = csv.writer(source)
        writer.writerow(["bank_account_id", "posting_date", "reference", "description", "deposit", "withdrawal"])
        for reference, deposit in rows:
            writer.writerow([account_id, MOVEMENT_DATE.isoformat(), reference, "Movimiento", deposit, ""])


def _import_bank_statement(app, company_code: str, path) -> ImportBatch:
    """Valida y ejecuta un CSV bancario por el servicio público de lotes."""
    with app.app_context():
        batch = ImportBatch(
            company_id=company_code,
            record_type="bank_statement",
            source_format="csv",
            source_filename=path.name,
            source_path=str(path),
            import_status=1,
        )
        database.session.add(batch)
        database.session.commit()

        service = ImportService()
        assert service.validate(batch.id)
        assert batch.import_status == 3
        assert service.execute(batch.id)
        database.session.refresh(batch)
        return batch


def test_csv_import_keeps_distinct_movements_with_the_same_reference(bank_identity_scenario, tmp_path):
    """La referencia compartida no fusiona movimientos con importes distintos."""
    app, company_code, account_id = bank_identity_scenario
    path = tmp_path / "same-reference.csv"
    _write_bank_statement(path, account_id, [("BANK-REF", "10.00"), ("BANK-REF", "5.00")])

    batch = _import_bank_statement(app, company_code, path)

    with app.app_context():
        transactions = (
            database.session.execute(
                database.select(BankTransaction)
                .where(BankTransaction.bank_account_id == account_id)
                .order_by(BankTransaction.deposit.desc())
            )
            .scalars()
            .all()
        )
        assert batch.import_status == 5
        assert batch.success_rows == 2
        assert batch.error_rows == 0
        assert [(transaction.reference_number, transaction.deposit) for transaction in transactions] == [
            ("BANK-REF", Decimal("10.00")),
            ("BANK-REF", Decimal("5.00")),
        ]


def test_csv_import_rejects_identical_rows_within_one_batch(bank_identity_scenario, tmp_path):
    """Dos filas idénticas producen un error de fila sin duplicar evidencia bancaria."""
    app, company_code, account_id = bank_identity_scenario
    path = tmp_path / "duplicate-rows.csv"
    movement = ("BANK-REF", "10.00")
    _write_bank_statement(path, account_id, [movement, movement])

    batch = _import_bank_statement(app, company_code, path)

    with app.app_context():
        transactions = BankTransaction.query.filter_by(bank_account_id=account_id).all()
        errors = ImportBatchError.query.filter_by(batch_id=batch.id).all()
        assert batch.import_status == 6
        assert batch.success_rows == 1
        assert batch.error_rows == 1
        assert len(transactions) == 1
        assert transactions[0].reference_number == "BANK-REF"
        assert len(errors) == 1
        # La referencia puede repetirse; row_N identifica inequívocamente la fila rechazada.
        assert errors[0].document_ref == "row_1"
        assert errors[0].error_type == "IMPORT_ERROR"
        assert "ya existe" in errors[0].message


def test_csv_import_rejects_same_movement_across_batches(bank_identity_scenario, tmp_path):
    """Reimportar el movimiento en otro lote no agrega una segunda transacción."""
    app, company_code, account_id = bank_identity_scenario
    movement = ("BANK-REF", "10.00")
    first_path = tmp_path / "first-import.csv"
    second_path = tmp_path / "second-import.csv"
    _write_bank_statement(first_path, account_id, [movement])
    _write_bank_statement(second_path, account_id, [movement])

    first_batch = _import_bank_statement(app, company_code, first_path)
    second_batch = _import_bank_statement(app, company_code, second_path)

    with app.app_context():
        transactions = BankTransaction.query.filter_by(bank_account_id=account_id).all()
        errors = ImportBatchError.query.filter_by(batch_id=second_batch.id).all()
        assert first_batch.import_status == 5
        assert second_batch.import_status == 6
        assert second_batch.success_rows == 0
        assert second_batch.error_rows == 1
        assert len(transactions) == 1
        assert len(errors) == 1
        assert errors[0].document_ref == "row_0"
        assert errors[0].error_type == "IMPORT_ERROR"
        assert "ya existe" in errors[0].message


def test_identity_conflict_detection_ignores_other_integrity_errors():
    """Solo la restricción de identidad bancaria se traduce a conflicto de negocio."""
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
    mysql_error = IntegrityError(
        "INSERT INTO bank_transaction",
        {},
        Exception("(1062, \"Duplicate entry 'abc' for key 'bank_transaction.uq_bank_transaction_identity'\")"),
    )
    unrelated_error = IntegrityError(
        "INSERT INTO party",
        {},
        Exception("UNIQUE constraint failed: party.tax_id_key"),
    )

    assert _is_bank_identity_conflict(sqlite_error)
    assert _is_bank_identity_conflict(postgres_error)
    assert _is_bank_identity_conflict(mysql_error)
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
            # Con referencia, la identidad económica es única en el motor real.
            database.session.add(BankTransaction(**_movement(account_id, reference="REF-ENGINE")))
            database.session.commit()

            database.session.add(BankTransaction(**_movement(account_id, reference="REF-ENGINE")))
            with pytest.raises(IntegrityError) as error:
                database.session.flush()
            # Cada motor nombra la restricción de forma distinta: SQLite y
            # PostgreSQL exponen la columna, MySQL el índice único.
            assert _is_bank_identity_conflict(error.value)
            database.session.rollback()

            movement = {**_movement(account_id, reference="REF-ENGINE-2"), "company_id": company_code}
            with pytest.raises(ValueError, match="ya existe"):
                BankStatementAdapter().persist_document([dict(movement), dict(movement)])
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
