# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2175: migración del alcance de folios en el motor configurado.

Estas pruebas se ejecutan con ``pytest -m database`` para cubrir la ruta no
SQLite de la migración (PostgreSQL/MySQL) y la idempotencia del arranque.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    GeneratedIdentifierLog,
    database,
)
from cacao_accounting.database import helpers as db_helpers

pytestmark = pytest.mark.database


@pytest.fixture
def database_app():
    """Aplicación sobre el motor configurado por el workflow de bases de datos."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": configuracion["SQLALCHEMY_DATABASE_URI"],
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _drop_index(connection, index_name: str) -> None:
    """Elimina un índice con la sintaxis del motor activo."""
    dialect = connection.dialect.name
    table = "generated_identifier_log"
    if dialect in {"mysql", "mariadb", "mssql"}:
        connection.exec_driver_sql(f"DROP INDEX {index_name} ON {table}")
    else:
        connection.exec_driver_sql(f"DROP INDEX {index_name}")


def _index_names(bind) -> set[str]:
    """Devuelve los índices actuales de la tabla de identificadores."""
    return {item["name"] for item in inspect(bind).get_indexes("generated_identifier_log")}


def _seed_company(name: str) -> str:
    """Crea una compañía con moneda y código únicos para la prueba."""
    code = f"{name}{uuid4().hex[:6].upper()}"
    if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
    database.session.add(
        Entity(
            code=code,
            name=code,
            company_name=f"{code} SA",
            tax_id=f"J-{code}",
            currency="NIO",
            enabled=True,
            status="activo",
        )
    )
    database.session.flush()
    return code


def _log(company: str | None, identifier: str) -> GeneratedIdentifierLog:
    """Construye un registro de identificador para la prueba."""
    return GeneratedIdentifierLog(
        entity_type="sales_invoice",
        entity_id=f"DOC-{uuid4().hex[:10]}",
        full_identifier=identifier,
        company=company,
    )


def test_migra_indices_en_el_motor_configurado_y_es_idempotente(database_app, monkeypatch):
    """La ruta no SQLite retira el índice global y conserva las filas."""
    suffix = uuid4().hex[:8]
    with database_app.app_context():
        company_a = _seed_company("MA")
        company_b = _seed_company("MB")
        database.session.add_all([_log(company_a, f"INV-{suffix}"), _log(company_b, f"PUR-{suffix}")])
        database.session.commit()

        with database.engine.begin() as connection:
            for index_name in (
                db_helpers.GENERATED_IDENTIFIER_SCOPE_INDEX,
                db_helpers.GENERATED_IDENTIFIER_GLOBAL_INDEX,
            ):
                if index_name in _index_names(connection):
                    _drop_index(connection, index_name)
            db_helpers._create_unique_index_sql(
                connection,
                GeneratedIdentifierLog.__table__,
                "uq_generated_identifier_log_legacy_full",
                ("full_identifier",),
            )

        db_helpers._ensure_generated_identifier_scope_unique()

        indices = _index_names(database.engine)
        assert db_helpers.GENERATED_IDENTIFIER_SCOPE_INDEX in indices
        assert "uq_generated_identifier_log_legacy_full" not in indices
        assert database.session.execute(database.select(database.func.count(GeneratedIdentifierLog.id))).scalar_one() >= 2

        monkeypatch.setattr(
            db_helpers,
            "_drop_legacy_generated_identifier_unique",
            lambda *_a, **_k: pytest.fail("la migración no debe repetirse"),
        )
        db_helpers._ensure_generated_identifier_scope_unique()

        database.session.add(_log(company_b, f"INV-{suffix}"))
        database.session.commit()

        database.session.add(_log(company_a, f"INV-{suffix}"))
        with pytest.raises(IntegrityError):
            database.session.flush()
        database.session.rollback()
