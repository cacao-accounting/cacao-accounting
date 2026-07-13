# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 William José Moreno Reyes

"""Pruebas expandidas para las validaciones de permisos de query_tools."""

from __future__ import annotations

import sys
import os
import pytest
from unittest import mock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../tests"))

from cacao_accounting import create_app
from cacao_accounting.database import database, Entity, Modules, User
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.errors import QueryToolError, ErrorCode
from cacao_accounting.query_tools.permissions import (
    validate_company_access,
    validate_module_active,
    validate_permission,
)
from z_func import init_test_db


@pytest.fixture(scope="module")
def app_instance():
    """Instancia de aplicación Flask con base de datos en memoria para pruebas de permisos."""
    _app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "permissions_test_secret_key",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    with _app.app_context():
        init_test_db(_app)
        # Ensure there is a company and modules registered
        entity = database.session.execute(database.select(Entity)).scalars().first()
        if not entity:
            database.session.add(
                Entity(
                    id="permissions_company",
                    code="cacao",
                    company_name="Cacao",
                    tax_id="J0001",
                    currency="NIO",
                )
            )
            database.session.commit()
    return _app


def test_query_context_defaults():
    ctx = QueryContext(user_id="user123")
    assert ctx.user_id == "user123"
    assert ctx.company_ids == []
    assert ctx.permissions == set()
    assert ctx.source == "test"


def test_query_context_with_values():
    ctx = QueryContext(
        user_id="user456",
        company_ids=["EMP001", "EMP002"],
        permissions={"accounting.read", "companies.read"},
        source="mcp",
        source_client="claude",
    )
    assert ctx.user_id == "user456"
    assert "EMP001" in ctx.company_ids
    assert "accounting.read" in ctx.permissions
    assert ctx.source == "mcp"


def test_permission_validation_error():
    ctx = QueryContext(user_id="user1", permissions=set())
    with pytest.raises(QueryToolError) as exc:
        validate_permission(ctx, required_permission="accounting.reports.read")
    assert "permisos" in exc.value.message.lower()


def test_permission_validation_passes():
    ctx = QueryContext(
        user_id="user1",
        permissions={"accounting.reports.read"},
    )
    # Should not raise for missing company/module (no company_id provided)
    validate_permission(ctx, required_permission="accounting.reports.read")


def test_validate_company_access_denied_by_context(app_instance):
    with app_instance.app_context():
        # company_ids is not empty, and requested company_id is not in list
        ctx = QueryContext(user_id="user1", company_ids=["EMP001"])
        with pytest.raises(QueryToolError) as exc:
            validate_company_access(ctx, "cacao")
        assert exc.value.code == ErrorCode.COMPANY_ACCESS_DENIED


def test_validate_company_access_nonexistent(app_instance):
    with app_instance.app_context():
        # company_ids is empty (has access to all), but company does not exist in DB
        ctx = QueryContext(user_id="user1", company_ids=[])
        with pytest.raises(QueryToolError) as exc:
            validate_company_access(ctx, "nonexistent_company_code")
        assert exc.value.code == ErrorCode.COMPANY_ACCESS_DENIED
        assert "no existe" in exc.value.message


def test_validate_company_access_success(app_instance):
    with app_instance.app_context():
        ctx = QueryContext(user_id="user1", company_ids=[])
        # "cacao" company exists from init_test_db/setup
        validate_company_access(ctx, "cacao")


def test_validate_module_active_not_available(app_instance):
    with app_instance.app_context():
        with pytest.raises(QueryToolError) as exc:
            validate_module_active("nonexistent_module_name")
        assert exc.value.code == ErrorCode.MODULE_DISABLED
        assert "no está disponible" in exc.value.message


def test_validate_module_active_disabled(app_instance):
    with app_instance.app_context():
        # Find any module, disable it temporarily
        module = database.session.execute(database.select(Modules)).scalars().first()
        if module:
            orig_enabled = module.enabled
            module.enabled = False
            database.session.commit()

            with pytest.raises(QueryToolError) as exc:
                validate_module_active(module.module)
            assert exc.value.code == ErrorCode.MODULE_DISABLED
            assert "deshabilitado" in exc.value.message

            # restore
            module.enabled = orig_enabled
            database.session.commit()


def test_validate_permission_with_required_module_not_available(app_instance):
    with app_instance.app_context():
        ctx = QueryContext(user_id="cacao", permissions={"accounting.reports.read"})
        with pytest.raises(QueryToolError) as exc:
            validate_permission(ctx, required_permission=None, required_module="nonexistent_module_name")
        assert exc.value.code == ErrorCode.MODULE_DISABLED


@mock.patch("cacao_accounting.query_tools.permissions.Permisos")
def test_validate_permission_with_required_module_not_authorized(mock_permisos, app_instance):
    with app_instance.app_context():
        ctx = QueryContext(user_id="non_admin_user", permissions=set())

        # Mock Permisos so that .autorizado is False
        mock_instance = mock.MagicMock()
        mock_instance.autorizado = False
        mock_permisos.return_value = mock_instance

        # We will use an existing module name like "accounting"
        with pytest.raises(QueryToolError) as exc:
            validate_permission(ctx, required_permission=None, required_module="accounting")
        assert exc.value.code == ErrorCode.PERMISSION_DENIED
        assert "No tiene permisos" in exc.value.message


@mock.patch("cacao_accounting.query_tools.permissions.Permisos")
def test_validate_permission_with_required_module_authorized(mock_permisos, app_instance):
    with app_instance.app_context():
        ctx = QueryContext(user_id="admin", permissions=set())

        # Mock Permisos so that .autorizado is True
        mock_instance = mock.MagicMock()
        mock_instance.autorizado = True
        mock_permisos.return_value = mock_instance

        # Should pass without raising exceptions
        validate_permission(ctx, required_permission=None, required_module="accounting")


def test_validate_permission_combined_success(app_instance):
    with app_instance.app_context():
        user = database.session.execute(database.select(User).filter_by(user="cacao")).scalar_one()
        user_uuid = user.id
        ctx = QueryContext(
            user_id=user_uuid, # use the actual user UUID so that Permisos can load it
            permissions={"accounting.reports.read"},
            company_ids=["cacao"],
        )
        validate_permission(
            ctx,
            required_permission="accounting.reports.read",
            required_module="accounting",
            company_id="cacao",
        )
