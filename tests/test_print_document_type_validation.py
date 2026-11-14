# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La impresión de un tipo de documento desconocido falla de forma controlada.

Escenario operativo: un usuario abre un enlace de impresión con un tipo de
documento que no existe en el registro (por ejemplo, un enlace viejo o un
``document_type`` escrito a mano). El sistema debe responder 404, no 500, y
debe dejar constancia del intento fallido en la bitácora de impresión.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.printing.models import PrintJobLog, PrintTemplate


def _last_print_job(app, document_type: str) -> PrintJobLog | None:
    """Devuelve el último trabajo de impresión registrado para el tipo dado."""
    with app.app_context():
        return (
            database.session.execute(
                database.select(PrintJobLog).where(PrintJobLog.document_type == document_type).order_by(PrintJobLog.id.desc())
            )
            .scalars()
            .first()
        )


def test_preview_de_tipo_no_registrado_responde_404_y_registra_fallo(app, authenticated_client):
    """La vista previa de un tipo desconocido es un 404 y queda auditada."""
    client = authenticated_client("admin")

    response = client.get("/print/not-registered/audit-document/preview")

    assert response.status_code == 404
    assert b"not-registered" not in response.data
    job = _last_print_job(app, "not-registered")
    assert job is not None
    assert job.success is False
    assert job.output_format == "html_preview"
    assert "no registrado" in (job.error_message or "").lower()


def test_pdf_de_tipo_no_registrado_responde_404_y_registra_fallo(app, authenticated_client):
    """La descarga PDF de un tipo desconocido también es un 404 auditado."""
    client = authenticated_client("admin")

    response = client.get("/print/not-registered/audit-document/pdf")

    assert response.status_code == 404
    assert b"not-registered" not in response.data
    job = _last_print_job(app, "not-registered")
    assert job is not None
    assert job.success is False
    assert job.output_format == "pdf"
    assert "no registrado" in (job.error_message or "").lower()


@pytest.mark.parametrize("output_format", ["preview", "pdf"])
@pytest.mark.parametrize("long_field", ["document_type", "document_id"])
def test_campos_de_ruta_largos_no_rompen_el_404_ni_la_auditoria(app, authenticated_client, output_format, long_field):
    """Los campos inválidos mayores que sus columnas no convierten el 404 en 500."""
    client = authenticated_client("admin")
    document_type = f"unknown-{uuid4().hex}" + ("x" * 100 if long_field == "document_type" else "")
    document_id = "document-id-" + uuid4().hex[:10]
    if long_field == "document_id":
        document_id = "d" * 27
    stored_document_type = document_type[:80]
    stored_document_id = document_id[:26]

    response = client.get(f"/print/{document_type}/{document_id}/{output_format}")

    assert response.status_code == 404
    assert document_type.encode() not in response.data
    job = _last_print_job(app, stored_document_type)
    assert job is not None
    assert job.document_id == stored_document_id
    assert job.success is False
    assert job.output_format == ("html_preview" if output_format == "preview" else "pdf")


def test_admin_preview_de_plantilla_legacy_invalida_responde_404_generico(app, authenticated_client):
    """Una plantilla huérfana heredada no expone el error interno en preview admin."""
    client = authenticated_client("admin")
    document_type = f"legacy-unregistered-{uuid4().hex}"
    with app.app_context():
        template = PrintTemplate(
            company_code="cacao",
            document_type=document_type,
            code=f"legacy-{uuid4().hex}",
            name="Legacy invalid type",
            template_body="<html><body>Legacy</body></html>",
            stylesheet_body="",
            status="draft",
        )
        database.session.add(template)
        database.session.commit()
        template_id = template.id

    response = client.get(f"/admin/print-templates/{template_id}/preview")

    assert response.status_code == 404
    assert document_type.encode() not in response.data
    job = _last_print_job(app, document_type)
    assert job is not None
    assert job.success is False
    assert job.output_format == "html_preview"


@pytest.fixture
def print_scope_app():
    """Aísla RBAC y auditoría para probar un usuario con permiso en un módulo."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
            "SECRET_KEY": "print-scope-test-secret-key-32-bytes",
        }
    )
    document_type = f"unknown-cross-company-{uuid4().hex}"
    user_name = f"print-audit-{uuid4().hex[:8]}"
    admin_name = f"print-admin-audit-{uuid4().hex[:8]}"
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="USD", name="US Dollar", decimals=2, active=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha Company",
                    tax_id=f"ALPHA-{uuid4().hex[:8]}",
                    currency="USD",
                    enabled=True,
                ),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao Company",
                    tax_id=f"CACAO-{uuid4().hex[:8]}",
                    currency="USD",
                    enabled=True,
                ),
                Modules(module="sales", default=False, enabled=True),
            ]
        )
        user = User(
            user=user_name,
            name="Print audit test",
            password=b"unused-test-password",
            classification="user",
            active=True,
            company="alpha",
        )
        admin = User(
            user=admin_name,
            name="Print audit admin",
            password=b"unused-test-password",
            classification="admin",
            active=True,
            company="alpha",
        )
        role = Roles(name=f"Print audit {uuid4().hex[:8]}", note="Single-module access test")
        sales_module = database.session.execute(select(Modules).filter_by(module="sales")).scalar_one()
        database.session.add_all([user, admin, role])
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=role.id, module_id=sales_module.id, view=True),
                RolesUser(user_id=user.id, role_id=role.id, active=True),
                UserCompanyAccess(user_id=user.id, company_code="alpha"),
            ]
        )
        database.session.commit()
        user_id, admin_id = str(user.id), str(admin.id)
        auth_version, admin_auth_version = user.auth_version, admin.auth_version
    yield application, document_type, user_id, auth_version, admin_id, admin_auth_version
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_tipo_desconocido_no_crea_auditoria_en_compania_no_autorizada(print_scope_app):
    """Un permiso de ventas autoriza auditoría solo en la compañía asignada."""
    application, document_type, user_id, auth_version, _, _ = print_scope_app
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True
    allowed_response = client.get(f"/print/{document_type}/document-1/preview?company=alpha")
    assert allowed_response.status_code == 404
    with application.app_context():
        jobs = database.session.execute(select(PrintJobLog).filter_by(document_type=document_type)).scalars().all()
        assert len(jobs) == 1
        assert jobs[0].company_code == "alpha"
        assert jobs[0].success is False

    denied_response = client.get(f"/print/{document_type}/document-1/preview?company=cacao")
    nonexistent_response = client.get(f"/print/{document_type}/document-1/preview?company=unknown-company")

    assert denied_response.status_code == 403
    assert nonexistent_response.status_code == denied_response.status_code
    with application.app_context():
        jobs = database.session.execute(select(PrintJobLog).filter_by(document_type=document_type)).scalars().all()
        assert len(jobs) == 1


def test_tipo_desconocido_de_admin_con_compania_inexistente_no_falla_al_auditar(print_scope_app):
    """Una compañía desconocida no alcanza la FK de PrintJobLog aunque el usuario sea admin."""
    application, document_type, _, _, admin_id, auth_version = print_scope_app
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = admin_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True

    response = client.get(f"/print/{document_type}/document-1/preview?company=unknown-company")

    assert response.status_code == 404
    with application.app_context():
        jobs = database.session.execute(select(PrintJobLog).filter_by(document_type=document_type)).scalars().all()
        assert jobs == []


def test_create_template_does_not_persist_unregistered_document_type(app, authenticated_client):
    """Un POST manipulado no debe dejar un borrador que nunca se pueda publicar."""
    client = authenticated_client("admin")
    code = f"invalid-document-type-{uuid4().hex}"

    response = client.post(
        "/admin/print-templates/new",
        data={
            "document_type": "not-registered-audit",
            "code": code,
            "name": "Invalid template type",
            "template_body": "<html><body>Safe sample</body></html>",
            "stylesheet_body": "",
            "paper_size": "letter",
            "orientation": "portrait",
        },
    )

    assert response.status_code == 200
    assert b"no registrado" in response.data.lower()
    assert b"is not registered" not in response.data.lower()
    with app.app_context():
        persisted = database.session.execute(select(PrintTemplate).filter_by(code=code)).scalar_one_or_none()
        assert persisted is None
