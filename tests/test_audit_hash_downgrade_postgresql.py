# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2316: el downgrade del hash v2 se rechaza en PostgreSQL real."""

from __future__ import annotations

import os
from datetime import datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.engine import make_url

from cacao_accounting import alembic, create_app
from cacao_accounting.audit_chain import compute_payload_hash
from cacao_accounting.config import configuracion
from cacao_accounting.database import AuditTrail, database

pytestmark = pytest.mark.database


def _isolated_url():
    raw = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    url = make_url(raw)
    if not url.drivername.startswith("postgresql"):
        pytest.skip("Este escenario requiere PostgreSQL Tier 1.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")
    name = f"audit_{uuid4().hex[:10]}"
    admin = create_engine(url.set(database="postgres"))
    with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()
    return url.set(database=name), name


def _drop_database(url, name: str) -> None:
    admin = create_engine(url.set(database="postgres"))
    try:
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            try:
                conn.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        f"WHERE datname = '{name}' AND pid <> pg_backend_pid()"
                    )
                )
            except ProgrammingError:
                # Un rol sin pg_signal_autovacuum_worker no puede terminar todos los
                # backends; el engine ya hizo dispose y DROP DATABASE no los espera.
                pass
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
    finally:
        admin.dispose()


def test_downgrade_rechaza_evidencia_v2_en_postgresql():
    """La migración no elimina la columna mientras exista evidencia v2."""
    url, name = _isolated_url()
    try:
        app = create_app(
            {
                **configuracion,
                "SQLALCHEMY_DATABASE_URI": url.render_as_string(hide_password=False),
                "TESTING": True,
                "SECRET_KEY": "test-2316",
                "WTF_CSRF_ENABLED": False,
            }
        )
        with app.app_context():
            from cacao_accounting.audit_chain import CHAIN_HASH_VERSION, verify_audit_trail_chain

            database.create_all()
            alembic.stamp("head")
            database.session.add(AuditTrail(document_type="test", document_id="doc-1", action="created"))
            database.session.commit()

            row = database.session.execute(database.select(AuditTrail)).scalar_one()
            assert row.hash_version == CHAIN_HASH_VERSION
            assert verify_audit_trail_chain() == []

            with pytest.raises(RuntimeError, match="hash versionado|downgrade rechazado"):
                alembic.downgrade("20260809_0001")

            columns = {column["name"] for column in inspect(database.engine).get_columns("audit_trail")}
            assert "hash_version" in columns
            assert verify_audit_trail_chain() == []
            database.session.remove()
            database.engine.dispose()
    finally:
        _drop_database(url, name)


def test_downgrade_conserva_evidencia_heredada_en_postgresql():
    """Sin filas v2 la reversión elimina la columna y conserva la cadena v1."""
    url, name = _isolated_url()
    try:
        app = create_app(
            {
                **configuracion,
                "SQLALCHEMY_DATABASE_URI": url.render_as_string(hide_password=False),
                "TESTING": True,
                "SECRET_KEY": "test-2316-legacy",
                "WTF_CSRF_ENABLED": False,
            }
        )
        with app.app_context():
            from cacao_accounting.audit_chain import verify_audit_trail_chain

            database.create_all()
            alembic.stamp("head")
            # Fila heredada: hash v1 y columna versionada nula, como el dato
            # migrado desde una instalación previa al sellado v2.
            values = {
                "id": "01TESTAUDIT00000000000001",
                "document_type": "test",
                "document_id": "doc-legacy",
                "action": "created",
                "payload_hash": "",
                "prev_hash": None,
                "timestamp": datetime(2026, 1, 1, 12, 0, 0),
            }
            values["payload_hash"] = compute_payload_hash(values, version=1)
            database.session.execute(AuditTrail.__table__.insert().values(**values))
            database.session.commit()
            assert verify_audit_trail_chain() == []
            # El DDL de Alembic usa otra conexión: cerrar la transacción de
            # lectura evita que el DROP COLUMN espere indefinidamente.
            database.session.remove()

            alembic.downgrade("20260809_0001")

            columns = {column["name"] for column in inspect(database.engine).get_columns("audit_trail")}
            assert "hash_version" not in columns
            row = database.session.execute(database.text("SELECT document_id, payload_hash FROM audit_trail")).one()
            assert row.document_id == "doc-legacy"
            assert row.payload_hash == values["payload_hash"]
            database.session.remove()

            alembic.upgrade("head")
            assert verify_audit_trail_chain() == []
            database.session.remove()
            database.engine.dispose()
    finally:
        _drop_database(url, name)
