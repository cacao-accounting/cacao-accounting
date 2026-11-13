# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Enums fiscales y etiquetas de impresión localizados.

Escenario de negocio:
- #1911: tablas de impuestos mostraban valores internos sin traducir.
- #1932: la lista/duplicado de impresión usaban literales sin gettext.
- #1928: las plantillas de impresión usaban el bloque incorrecto.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    Roles,
    RolesUser,
    Tax,
    TaxRule,
    TaxTemplate,
    TaxTemplateItem,
    User,
    database,
)
from cacao_accounting.printing.models import PrintTemplate


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
                    language="en",
                ),
                Roles(name="admin", note="Administrador"),
                Tax(
                    id="TAX-1",
                    name="IVA",
                    rate=15,
                    tax_type="percentage",
                    applies_to="sales",
                    is_active=True,
                ),
                TaxTemplate(
                    id="TPL-1",
                    name="Plantilla ventas",
                    company="cacao",
                    template_type="selling",
                    is_active=True,
                ),
                TaxRule(
                    company="cacao",
                    name="Regla",
                    concept="iva",
                    applies_to="sales",
                    level="transaction",
                    tax_type="tax",
                    is_active=True,
                ),
                PrintTemplate(
                    company_code="cacao",
                    document_type="journal_entry",
                    code="BASE",
                    name="Base",
                    template_body="<html></html>",
                    status="published",
                ),
            ]
        )
        database.session.flush()
        rol = database.session.execute(database.select(Roles).filter_by(name="admin")).scalar_one()
        database.session.add(RolesUser(user_id="admin", role_id=rol.id, active=True))
        database.session.add(
            TaxTemplateItem(
                tax_template_id="TPL-1",
                tax_id="TAX-1",
                sequence=10,
                calculation_base="net_document",
                behavior="additive",
            )
        )
        database.session.commit()
        ids = {"template": "TPL-1", "print": database.session.execute(database.select(PrintTemplate)).scalar_one().id}
    return application, ids


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def test_tablas_fiscales_traducen_enums():
    """#1911: las tablas muestran etiquetas, no valores internos."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        taxes = client.get("/settings/taxes").get_data(as_text=True)
        templates = client.get("/settings/tax-templates").get_data(as_text=True)
        items = client.get(f"/settings/tax-templates/{ids['template']}/items").get_data(as_text=True)
        rules = client.get("/settings/tax-rules").get_data(as_text=True)

        assert "Percentage" in taxes and ">Sale<" in taxes and "Yes" in taxes
        assert ">Sale<" in templates
        assert "IVA" in items and "Net document" in items and "Additive" in items
        assert ">Sale<" in rules and "Transaction" in rules and "Yes" in rules
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_lista_de_impresion_renderiza_y_traduce():
    """#1932/#1928: la lista usa el bloque correcto y etiquetas localizadas."""
    application, _ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.get("/admin/print-templates")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert "Accounting Entry" in html
        assert "Published" in html
        assert "journal_entry" not in html
        assert ">published<" not in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_duplicado_usa_nombre_traducido():
    """#1932: la copia se nombra con gettext y no con un literal fijo."""
    application, ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(f"/admin/print-templates/{ids['print']}/duplicate")

        assert respuesta.status_code == 302
        with application.app_context():
            copia = database.session.execute(database.select(PrintTemplate).filter_by(code="BASE_copy")).scalar_one()
            assert copia.name == "Copy of Base"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_crear_plantilla_rechaza_css_que_cierra_style():
    """La ruta de creación valida el CSS antes de guardar el borrador."""
    application, _ids = _crear_app()
    try:
        client = _cliente(application)
        response = client.post(
            "/admin/print-templates/new",
            data={
                "company_code": "cacao",
                "document_type": "journal_entry",
                "code": "UNSAFE",
                "name": "Unsafe",
                "template_body": "<p>Entry</p>",
                "stylesheet_body": "</style><script>alert(1)</script>",
            },
        )

        assert response.status_code == 200
        with application.app_context():
            unsafe = database.session.execute(database.select(PrintTemplate).filter_by(code="UNSAFE")).first()
            assert unsafe is None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
