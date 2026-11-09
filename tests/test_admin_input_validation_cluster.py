# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Validación de entradas administrativas y de comprobantes.

Escenario de negocio (paraguas #1717):
- #2068: una secuencia fiscal no numérica respondía 500.
- #1933: un orden de línea no numérico escapaba de JournalValidationError.
- #1994: SMTP persistía puerto/remitente inválidos con mensaje de éxito.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    CacaoConfig,
    Currency,
    Entity,
    Modules,
    TaxTemplate,
    TaxTemplateItem,
    User,
    database,
)
from cacao_accounting.contabilidad.journal_service import JournalValidationError, _normalize_line


def _crear_app():
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
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="admin", default=False, enabled=True),
                Modules(module="accounting", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                TaxTemplate(name="Plantilla", company="cacao", template_type="selling", is_active=True),
            ]
        )
        database.session.commit()
        template_id = database.session.execute(database.select(TaxTemplate)).scalar_one().id
    return application, template_id


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_secuencia_fiscal_no_numerica_no_responde_500():
    """#2068: la secuencia inválida se rechaza antes de crear la línea."""
    application, template_id = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            f"/settings/tax-templates/{template_id}/items",
            data={"tax_id": "", "sequence": "abc", "calculation_base": "net_document", "behavior": "additive"},
        )

        assert respuesta.status_code == 302
        with application.app_context():
            assert database.session.execute(database.select(TaxTemplateItem)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_orden_de_linea_invalido_es_error_de_dominio():
    """#1933: _normalize_line traduce el ValueError a JournalValidationError."""
    application, _template_id = _crear_app()
    try:
        with application.app_context():
            with pytest.raises(JournalValidationError, match="orden de la línea"):
                _normalize_line({"order": "not-an-integer", "account": "1101", "debit": "1"}, 1)
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_endpoint_de_comprobante_no_propaga_orden_invalido():
    """#1933: el POST con orden inválido vuelve al formulario sin persistir."""
    application, _template_id = _crear_app()
    try:
        client = _cliente(application)
        payload = {
            "company": "cacao",
            "posting_date": "2026-01-02",
            "lines": [{"order": "not-an-integer", "account": "1101", "debit": "1", "credit": "0"}],
        }
        respuesta = client.post("/accounting/journal/new", data={"journal_payload": json.dumps(payload)})

        assert respuesta.status_code == 200
        con_error = "orden de la línea" in respuesta.get_data(as_text=True)
        assert con_error
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


@pytest.mark.parametrize(
    ("campo", "valor", "mensaje"),
    [
        ("smtp_port", "nope", "El puerto SMTP debe ser un número entero entre 1 y 65535."),
        ("smtp_from_email", "not-an-email", "El correo remitente SMTP no es válido."),
    ],
)
def test_smtp_invalido_no_se_persiste(campo, valor, mensaje):
    """#1994: el guardado valida puerto y remitente antes de persistir."""
    application, _template_id = _crear_app()
    try:
        client = _cliente(application)
        datos = {
            "smtp_server": "smtp.test",
            "smtp_port": "587",
            "smtp_from_email": "noreply@test.com",
            "smtp_user": "",
        }
        datos[campo] = valor
        respuesta = client.post("/settings/email", data=datos)

        assert respuesta.status_code == 302
        with application.app_context():
            registros = database.session.execute(database.select(CacaoConfig)).scalars().all()
            valores = {registro.key: registro.value for registro in registros}
            assert "nope" not in valores.get("smtp_port", "")
            assert valores.get("smtp_from_email") != "not-an-email"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_smtp_valido_se_persiste():
    """#1994: la configuración correcta sigue guardándose."""
    application, _template_id = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/settings/email",
            data={
                "smtp_server": "smtp.test",
                "smtp_port": "465",
                "smtp_from_email": "Noreply@Test.COM",
                "smtp_user": "usuario",
            },
        )

        assert respuesta.status_code == 302
        with application.app_context():
            registros = database.session.execute(database.select(CacaoConfig)).scalars().all()
            valores = {registro.key: registro.value for registro in registros}
            assert valores["smtp_port"] == "465"
            assert valores["smtp_from_email"] == "Noreply@test.com"
            assert valores["smtp_server"] == "smtp.test"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
