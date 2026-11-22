# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2252: las herramientas de documentos no dependen de un módulo inexistente.

`documents.get_details`, `get_lines` y `get_status` autenticaban contra el módulo
`documents`, que no existe, por lo que siempre respondían MODULE_DISABLED. La
autorización debe resolverse por el módulo dueño del tipo de documento.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, Party, SalesInvoice, database
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.errors import ErrorCode, QueryToolError
from cacao_accounting.query_tools.handlers import documents as documents_handlers


@pytest.fixture
def documents_tool_scenario():
    """Compañía con módulo de ventas, cliente y una factura posteada."""
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
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="sales", default=False, enabled=True),
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
            ]
        )
        database.session.flush()
        cliente = Party(code="CLI-2252", name="Cliente", is_customer=True, is_active=True)
        database.session.add(cliente)
        database.session.flush()
        factura = SalesInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"FAC-{uuid4().hex[:6]}",
            document_type="sales_invoice",
            customer_id=cliente.id,
            customer_name=cliente.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            grand_total=Decimal("100"),
            total=Decimal("100"),
            outstanding_amount=Decimal("100"),
        )
        database.session.add(factura)
        database.session.commit()
        ids = {"invoice": factura.id}
    yield app, ids
    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _context() -> QueryContext:
    return QueryContext(
        user_id="tester",
        company_ids=["cacao"],
        permissions={"documents.reports.read", "sales.reports.read", "accounting.reports.read"},
        is_service_principal=False,
    )


def test_get_details_no_falla_por_modulo_inexistente(documents_tool_scenario):
    """La herramienta no responde MODULE_DISABLED por el módulo 'documents'.

    Cualquier rechazo posterior debe venir del ACL del tipo de documento
    (módulo dueño real), no de un módulo inexistente.
    """
    application, ids = documents_tool_scenario
    with application.app_context():
        tool = documents_handlers.get_document_details_handler
        with pytest.raises(QueryToolError) as excinfo:
            tool.handler(
                context=_context(),
                company_id="cacao",
                document_type="sales_invoice",
                document_id=ids["invoice"],
            )
        assert excinfo.value.code != ErrorCode.MODULE_DISABLED, "El módulo 'documents' no debe evaluarse"
