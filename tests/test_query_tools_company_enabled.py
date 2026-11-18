# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1338: las query tools rechazan compañías deshabilitadas.

La validación de acceso y el listado de compañías deben exigir
``Entity.enabled``, sin importar si el contexto es de usuario o de service
principal y aunque la allowlist conserve el código deshabilitado.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, database
from cacao_accounting.query_tools.context import QueryContext
from cacao_accounting.query_tools.errors import ErrorCode, QueryToolError
from cacao_accounting.query_tools.handlers.companies import list_companies
from cacao_accounting.query_tools.permissions import validate_company_access


@pytest.fixture
def query_company_scenario():
    """Create one enabled and one disabled company."""
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
    suffix = uuid4().hex[:6]
    enabled_company = f"on{suffix}"
    disabled_company = f"off{suffix}"

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code=enabled_company,
                    name="Habilitada",
                    company_name=f"Compañía Habilitada {suffix}",
                    tax_id=f"TAX-ON-{suffix}",
                    currency="NIO",
                    enabled=True,
                ),
                Entity(
                    code=disabled_company,
                    name="Deshabilitada",
                    company_name=f"Compañía Deshabilitada {suffix}",
                    tax_id=f"TAX-OFF-{suffix}",
                    currency="NIO",
                    enabled=False,
                ),
            ]
        )
        database.session.commit()
        ids = {
            "enabled_company": enabled_company,
            "disabled_company": disabled_company,
        }

    yield app, ids

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _service_context(companies: list[str], *, allow_all: bool = False) -> QueryContext:
    """Build a service-principal context with the requested allow-list."""
    return QueryContext(
        user_id="service",
        company_ids=list(companies),
        permissions={"report.view"},
        is_service_principal=True,
        allow_all_companies=allow_all,
    )


def test_company_access_rejects_disabled_company_for_service_principal(query_company_scenario):
    """A disabled company in the allow-list is denied even for a service principal."""
    app, ids = query_company_scenario

    with app.app_context():
        with pytest.raises(QueryToolError) as error:
            validate_company_access(_service_context([ids["disabled_company"]]), ids["disabled_company"])

        assert error.value.code == ErrorCode.COMPANY_ACCESS_DENIED


def test_company_access_accepts_enabled_company(query_company_scenario):
    """An enabled company in the allow-list keeps working."""
    app, ids = query_company_scenario

    with app.app_context():
        validate_company_access(_service_context([ids["enabled_company"]]), ids["enabled_company"])


def test_company_list_hides_disabled_company_for_allow_list(query_company_scenario):
    """A non-global context lists only its enabled companies."""
    app, ids = query_company_scenario

    with app.app_context():
        result = list_companies.handler(
            context=_service_context([ids["enabled_company"], ids["disabled_company"]]),
            page=1,
            page_size=100,
        )

    codes = {item["code"] for item in result["items"]}
    assert codes == {ids["enabled_company"]}
    assert result["total_items"] == 1


def test_company_list_hides_disabled_company_for_global_context(query_company_scenario):
    """A global context also lists only enabled companies."""
    app, ids = query_company_scenario

    with app.app_context():
        result = list_companies.handler(context=_service_context([], allow_all=True), page=1, page_size=100)

    codes = {item["code"] for item in result["items"]}
    assert ids["enabled_company"] in codes
    assert ids["disabled_company"] not in codes
