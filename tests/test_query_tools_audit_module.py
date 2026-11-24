# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1581: la consulta de auditoría no depende de un módulo inexistente."""

from __future__ import annotations

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, database
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.handlers import audit_trail


def test_resumen_de_auditoria_funciona_sin_modulo_audit():
    """Con el permiso de auditoría y un módulo estándar activo no hay MODULE_DISABLED."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    context = QueryContext(
        user_id="tester",
        company_ids=["cacao"],
        permissions={"audit.reports.read"},
        is_service_principal=False,
    )
    try:
        with app.app_context():
            database.create_all()
            database.session.add_all(
                [
                    Modules(module="accounting", default=False, enabled=True),
                    Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                    Entity(
                        code="cacao",
                        name="Cacao",
                        company_name="Cacao SA",
                        tax_id="J-1581",
                        currency="NIO",
                        enabled=True,
                        status="default",
                    ),
                ]
            )
            database.session.commit()

            resultado = audit_trail.get_user_activity_summary.handler(context=context, company_id="cacao")

        assert resultado["items"] == []
        assert resultado["page"]["total_items"] == 0
    finally:
        with app.app_context():
            database.session.remove()
            database.engine.dispose()
