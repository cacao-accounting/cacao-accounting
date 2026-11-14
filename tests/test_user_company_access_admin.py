# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes
"""Administra el alcance de compañías con auditoría Cloud habilitada."""

from __future__ import annotations

import json

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    AuditTrail,
    Currency,
    Entity,
    Modules,
    User,
    UserCompanyAccess,
    database,
)


def _crear_app():
    """Crea un entorno Cloud aislado con los controles internos activos."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "company-access-test",
            "TESTING": True,
            "INTERNAL_CONTROLS_ENFORCE": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add_all(
            [
                Modules(module="admin", default=False, enabled=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                Entity(
                    code="beta",
                    name="Beta",
                    company_name="Beta SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                User(id="admin", user="admin", name="Administrador", password=b"x", active=True, classification="admin"),
                User(id="objetivo", user="objetivo", name="Objetivo", password=b"x", active=True, classification="system"),
                UserCompanyAccess(user_id="objetivo", company_code="alpha"),
            ]
        )
        database.session.commit()
    return application


def _cliente_admin(application):
    """Devuelve un cliente autenticado como administrador del sistema."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_admin_reemplaza_alcance_y_audita_la_revocacion():
    """La revocación y el alta se confirman juntas y conservan actor/evidencia."""
    application = _crear_app()
    try:
        with application.app_context():
            antigua = database.session.execute(
                database.select(UserCompanyAccess).filter_by(user_id="objetivo", company_code="alpha")
            ).scalar_one()
            antigua_id = antigua.id

        response = _cliente_admin(application).post(
            "/settings/users/objetivo/companies",
            data={"companies": "beta"},
        )

        assert response.status_code == 302
        with application.app_context():
            asignaciones = (
                database.session.execute(database.select(UserCompanyAccess).filter_by(user_id="objetivo")).scalars().all()
            )
            assert [(row.company_code) for row in asignaciones] == ["beta"]
            evento = database.session.execute(
                database.select(AuditTrail).filter_by(
                    document_type="user_company_access",
                    document_id=antigua_id,
                    action="deleted",
                )
            ).scalar_one()
            assert evento.actor_user_id == "admin"
            assert json.loads(evento.before_json)["company_code"] == "alpha"
            assert evento.after_json is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_post_sin_cambios_conserva_asignacion_y_no_duplica_auditoria():
    """Guardar el mismo alcance es idempotente y no reemplaza la fila existente."""
    application = _crear_app()
    try:
        with application.app_context():
            antigua = database.session.execute(
                database.select(UserCompanyAccess).filter_by(user_id="objetivo", company_code="alpha")
            ).scalar_one()
            antigua_id = antigua.id

        response = _cliente_admin(application).post(
            "/settings/users/objetivo/companies",
            data={"companies": "alpha"},
        )

        assert response.status_code == 302
        with application.app_context():
            asignaciones = (
                database.session.execute(database.select(UserCompanyAccess).filter_by(user_id="objetivo")).scalars().all()
            )
            assert len(asignaciones) == 1
            assert asignaciones[0].id == antigua_id
            evento = database.session.execute(
                database.select(AuditTrail).filter_by(
                    document_type="user_company_access",
                    document_id=antigua_id,
                    action="deleted",
                )
            ).scalar_one_or_none()
            assert evento is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_borrado_directo_de_asignacion_sigue_prohibido():
    """El permiso de transición no elimina la protección general de ACL."""
    application = _crear_app()
    try:
        with application.app_context():
            asignacion = database.session.execute(database.select(UserCompanyAccess)).scalar_one()
            database.session.delete(asignacion)
            with pytest.raises(ValueError, match="servicio auditado"):
                database.session.flush()
            database.session.rollback()
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
