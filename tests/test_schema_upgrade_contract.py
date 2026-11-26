# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William Jos? Moreno Reyes

"""Contrato de upgrades de esquema #1898/#2234/#1849."""

from __future__ import annotations

import pytest
from click.testing import CliRunner
from sqlalchemy import inspect, text

from cacao_accounting import alembic, cli, create_app
from cacao_accounting.database import AuditTrail, database
from cacao_accounting.database.helpers import estado_esquema_base_datos, verificar_esquema_base_datos


def _app(tmp_path, name="app.sqlite"):
    return create_app(
        {
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / name}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "WTF_CSRF_ENABLED": False,
        }
    )


def test_estado_empty_db(tmp_path):
    app = _app(tmp_path)
    with app.app_context():
        estado = estado_esquema_base_datos()
        assert estado["status"] == "empty"
        assert estado["alembic_table"] is False
        database.session.remove()
        database.engine.dispose()


def test_db_init_fresh_db_stamps_alembic_head(tmp_path, monkeypatch):
    app = _app(tmp_path, "init.sqlite")
    monkeypatch.setattr(cli, "_obtener_aplicacion", lambda: app)
    from cacao_accounting.database import helpers as db_helpers

    monkeypatch.setattr(db_helpers, "resolver_credenciales_iniciales", lambda: ("admin", "secret-pass"))
    result = CliRunner().invoke(cli.db_init)
    assert result.exit_code == 0, result.output
    with app.app_context():
        estado = estado_esquema_base_datos()
        assert estado["status"] == "current"
        assert inspect(database.engine).has_table("user")
        assert inspect(database.engine).has_table("alembic_version")
        database.session.remove()
        database.engine.dispose()


def test_db_migrate_rejects_empty_db(tmp_path, monkeypatch):
    app = _app(tmp_path, "empty.sqlite")
    monkeypatch.setattr(cli, "_obtener_aplicacion", lambda: app)
    result = CliRunner().invoke(cli.db_migrate)
    assert result.exit_code != 0
    assert "db init" in result.output.lower() or "inicializada" in result.output.lower()


def test_db_migrate_rejects_partial_schema(tmp_path, monkeypatch):
    app = _app(tmp_path, "partial.sqlite")
    with app.app_context():
        database.session.execute(text("CREATE TABLE user (id VARCHAR(26) PRIMARY KEY)"))
        database.session.commit()
        database.session.remove()
        database.engine.dispose()
    monkeypatch.setattr(cli, "_obtener_aplicacion", lambda: app)
    result = CliRunner().invoke(cli.db_migrate)
    assert result.exit_code != 0
    assert "parcial" in result.output.lower() or "respaldo" in result.output.lower()


def test_verify_rejects_outdated_schema_without_migrating(tmp_path):
    app = _app(tmp_path, "outdated.sqlite")
    with app.app_context():
        database.create_all()
        alembic.stamp("20260809_0001")
        with pytest.raises(RuntimeError, match="migrate|migraciones"):
            verificar_esquema_base_datos(permitir_migrar=False)
        # No debe migrar impl?citamente.
        assert tuple(s.revision for s in alembic.current()) == ("20260809_0001",)
        database.session.remove()
        database.engine.dispose()


def test_verify_stamps_unversioned_but_initialized_schema(tmp_path):
    app = _app(tmp_path, "unversioned.sqlite")
    with app.app_context():
        database.create_all()
        # Simula esquema completo ya bootstrapped sin historial Alembic.
        from cacao_accounting.database import CacaoConfig, User

        database.session.add(User(user="admin", password=b"x", active=True, classification="admin"))
        database.session.add(CacaoConfig(key="SETUP_COMPLETE", value="True"))
        database.session.commit()
        assert not inspect(database.engine).has_table("alembic_version")
        estado = verificar_esquema_base_datos(permitir_migrar=True)
        assert estado["status"] in {"current", "outdated"}
        assert inspect(database.engine).has_table("alembic_version")
        if estado["status"] == "outdated":
            from cacao_accounting import alembic as _al

            _al.upgrade("head")
            estado = estado_esquema_base_datos()
        assert estado["status"] == "current"
        database.session.remove()
        database.engine.dispose()


def test_downgrade_rejects_when_v2_audit_rows_exist(tmp_path):
    app = _app(tmp_path, "audit.sqlite")
    with app.app_context():
        database.create_all()
        alembic.stamp("head")
        database.session.execute(
            AuditTrail.__table__.insert().values(
                id="01TESTAUDIT00000000000000",
                document_type="test",
                document_id="doc-1",
                action="created",
                hash_version=2,
                payload_hash="x",
                prev_hash="",
            )
        )
        database.session.commit()
        with pytest.raises(RuntimeError, match="hash v2|downgrade rechazado"):
            alembic.downgrade("20260809_0001")
        cols = {c["name"] for c in inspect(database.engine).get_columns("audit_trail")}
        assert "hash_version" in cols
        database.session.remove()
        database.engine.dispose()
