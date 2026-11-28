# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

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


def test_db_migrate_rejects_bootstrap_incomplete(tmp_path, monkeypatch):
    app = _app(tmp_path, "bootstrap_incomplete.sqlite")
    with app.app_context():
        database.create_all()
        # Esquema completo sin historial alembic y sin bootstrap completo.
        estado = estado_esquema_base_datos()
        assert estado["status"] == "bootstrap_incomplete"
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
        # No debe migrar implícitamente.
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


def test_unversioned_schema_missing_required_column_is_rejected(tmp_path, monkeypatch):
    """No se sella head ni se pierden datos cuando falta una columna del contrato."""
    app = _app(tmp_path, "unversioned_missing_column.sqlite")
    with app.app_context():
        from cacao_accounting.database import CacaoConfig, User

        database.create_all()
        database.session.execute(text("ALTER TABLE audit_trail DROP COLUMN hash_version"))
        database.session.add(User(user="admin", password=b"x", active=True, classification="admin"))
        database.session.add(CacaoConfig(key="SETUP_COMPLETE", value="True"))
        database.session.commit()

        columns = {column["name"] for column in inspect(database.engine).get_columns("audit_trail")}
        assert "hash_version" not in columns
        estado = estado_esquema_base_datos()
        assert estado["status"] == "partial"
        with pytest.raises(RuntimeError, match="parcial|inconsistente"):
            verificar_esquema_base_datos(permitir_migrar=True)
        assert not inspect(database.engine).has_table("alembic_version")
        assert database.session.execute(database.select(database.func.count()).select_from(User)).scalar_one() == 1
        assert database.session.execute(database.select(database.func.count()).select_from(CacaoConfig)).scalar_one() == 1
        database.session.remove()
        database.engine.dispose()

    monkeypatch.setattr(cli, "_obtener_aplicacion", lambda: app)
    result = CliRunner().invoke(cli.db_migrate)
    assert result.exit_code != 0
    assert "parcial" in result.output.lower() or "respaldo" in result.output.lower()
    with app.app_context():
        assert not inspect(database.engine).has_table("alembic_version")
        assert database.session.execute(database.select(database.func.count()).select_from(User)).scalar_one() == 1
        assert database.session.execute(database.select(database.func.count()).select_from(CacaoConfig)).scalar_one() == 1
        database.session.remove()
        database.engine.dispose()


def test_downgrade_rejects_rows_sealed_by_the_product(tmp_path):
    """#1849: la fila v2 la produce el sellado real, no un literal del test."""
    app = _app(tmp_path, "audit.sqlite")
    with app.app_context():
        from cacao_accounting.audit_chain import CHAIN_HASH_VERSION, verify_audit_trail_chain

        database.create_all()
        alembic.stamp("head")
        database.session.add(AuditTrail(document_type="test", document_id="doc-1", action="created"))
        database.session.commit()

        fila = database.session.execute(database.select(AuditTrail)).scalar_one()
        # Sin esta premisa el guard quedaría verde sobre una fila que nada tiene que
        # ver con lo que el producto escribe (hallazgo 1 de QA2).
        assert fila.hash_version == CHAIN_HASH_VERSION, "el sellado debe fijar la versión vigente"
        assert fila.payload_hash, "el sellado debe producir el hash de payload"
        assert verify_audit_trail_chain() == [], "la primera fila de la cadena debe verificar limpia"

        with pytest.raises(RuntimeError, match="hash versionado|downgrade rechazado"):
            alembic.downgrade("20260809_0001")
        cols = {c["name"] for c in inspect(database.engine).get_columns("audit_trail")}
        assert "hash_version" in cols
        # La evidencia sobrevive al intento: sigue siendo verificable.
        assert verify_audit_trail_chain() == []
        database.session.remove()
        database.engine.dispose()


def test_downgrade_rejects_any_versioned_hash_not_only_the_current_number(tmp_path):
    """#1849: si la cadena sube a v3, el guard no puede quedar ciego."""
    app = _app(tmp_path, "audit_v3.sqlite")
    with app.app_context():
        from cacao_accounting.audit_chain import CHAIN_HASH_VERSION

        database.create_all()
        alembic.stamp("head")
        assert CHAIN_HASH_VERSION == 2, "el caso simula una versión futura de la cadena"
        database.session.execute(
            AuditTrail.__table__.insert().values(
                id="01TESTAUDIT00000000000003",
                document_type="test",
                document_id="doc-3",
                action="created",
                hash_version=3,
                payload_hash="hash-futuro",
                prev_hash="",
            )
        )
        database.session.commit()

        with pytest.raises(RuntimeError, match="hash versionado|downgrade rechazado"):
            alembic.downgrade("20260809_0001")
        cols = {c["name"] for c in inspect(database.engine).get_columns("audit_trail")}
        assert "hash_version" in cols
        database.session.remove()
        database.engine.dispose()


def test_downgrade_drops_the_column_when_only_legacy_rows_exist(tmp_path):
    """#1849: sin hash versionado la reversión sí ejecuta el ``drop_column``."""
    app = _app(tmp_path, "audit_legacy.sqlite")
    with app.app_context():
        database.create_all()
        alembic.stamp("head")
        database.session.execute(
            AuditTrail.__table__.insert().values(
                id="01TESTAUDIT00000000000001",
                document_type="test",
                document_id="doc-legacy",
                action="created",
                payload_hash="hash-heredado",
                prev_hash="",
            )
        )
        database.session.commit()

        alembic.downgrade("20260809_0001")

        cols = {c["name"] for c in inspect(database.engine).get_columns("audit_trail")}
        assert "hash_version" not in cols
        # La fila heredada no se pierde: el append-only de evidencia sigue intacto.
        assert database.session.execute(text("SELECT COUNT(*) FROM audit_trail")).scalar() == 1
        database.session.remove()
        database.engine.dispose()
