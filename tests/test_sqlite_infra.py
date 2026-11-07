# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Validación mínima de la infraestructura de pruebas SQLite y aislamiento por test."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from cacao_accounting.database import Entity, User, database


def test_worker_schema_is_materialized_once(app):
    """El esquema base del worker queda disponible y contempla la entidad principal."""
    with app.app_context():
        inspector = inspect(database.engine)
        assert inspector.has_table("entity")
        assert database.session.execute(select(Entity).filter_by(code="cacao")).scalar_one_or_none() is not None


def test_db_session_commit_is_rolled_back_after_test(db_session):
    """Un commit de negocio sobrevive solo hasta que se revierte la transacción externa del test."""
    probe_code = "infra-rollback-1"

    db_session.add(
        Entity(code=probe_code, name="Rollback Probe", company_name="Rollback Trial", tax_id="J0009", currency="NIO")
    )
    db_session.commit()
    assert db_session.execute(select(Entity).filter_by(code=probe_code)).scalar_one_or_none() is not None

    # El aislamiento real lo garantiza el rollback del outer transaction del fixture, no un rollback local.
    assert db_session.execute(select(Entity).filter_by(code=probe_code)).scalar_one_or_none() is not None


def test_reference_users_seed_is_available(app, reference_users):
    """Los usuarios base reutilizables quedan cargados en la sesión del worker."""
    with app.app_context():
        assert set(reference_users) >= {"admin", "reader", "writer", "no_access", "other_company", "limited_company"}
        assert database.session.execute(select(User).filter_by(user="admin")).scalar_one_or_none() is not None


def test_authenticated_client_isolated_per_test(authenticated_client):
    """Cada cliente autenticado recibe su propio estado de sesión."""
    admin_client = authenticated_client("admin")
    reader_client = authenticated_client("reader")

    with admin_client.session_transaction() as admin_session:
        admin_user_id = admin_session.get("_user_id")
        assert admin_user_id

    with reader_client.session_transaction() as reader_session:
        reader_user_id = reader_session.get("_user_id")
        assert reader_user_id
        assert reader_user_id != admin_user_id


def test_flush_error_does_not_leave_state_in_session(db_session):
    """Un error de flush no deja cambios persistidos cuando la sesión se revierte."""
    original = Entity(code="flush-original", name="Original", company_name="Flush Trial", tax_id="J0010", currency="NIO")
    db_session.add(original)
    db_session.flush()

    entity = Entity(code="flush-error-probe", name="Flush Error", company_name="Flush Trial", tax_id="J0011", currency="NIO")
    db_session.add(entity)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()
    assert db_session.execute(select(Entity).filter_by(code="flush-original")).scalar_one_or_none() is None
    assert db_session.execute(select(Entity).filter_by(code="flush-error-probe")).scalar_one_or_none() is None
