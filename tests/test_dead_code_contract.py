# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Contratos de retiro de código sin consumidores.

Sustituye al inventario eliminado en ``0970476b``: cada símbolo retirado en
esta limpieza no debe reaparecer sin una decisión y pruebas propias.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cacao_accounting import audit_chain, document_identifiers
from cacao_accounting.bancos import cash_forecast_service
from cacao_accounting.admin import services as admin_services
from cacao_accounting.api import dashboard as api_dashboard
from cacao_accounting import tax_pricing_service
from cacao_accounting.accounting_engine.orchestrator.event_orchestrator import BusinessEventOrchestrator
from cacao_accounting.bancos import services as bancos_services
from cacao_accounting.contabilidad import default_accounts, exchange_revaluation_service
from cacao_accounting.document_flow import payment as document_flow_payment
from cacao_accounting.setup import forms as setup_forms

RAIZ = Path(__file__).resolve().parents[1]


def test_admin_services_no_reintroduce_blueprint_sin_rutas():
    """#1357: el blueprint administrativo vive solo en admin.routes."""
    assert not hasattr(admin_services, "admin")


@pytest.mark.parametrize(
    ("modulo", "simbolo", "issue"),
    [
        (default_accounts, "SPECIAL_ACCOUNT_TYPES", "#1361"),
        (document_identifiers, "record_external_number_used", "#1294"),
        (api_dashboard, "_sum_query", "#2071"),
        (exchange_revaluation_service, "MONETARY_ACCOUNT_TYPES", "#1162"),
        (audit_chain, "_CHAIN_FIELDS", "#2079"),
        (cash_forecast_service, "_query_gl_sum", "#1260"),
        (tax_pricing_service, "get_item_price", "#1277"),
        (tax_pricing_service, "validate_price_tolerance", "#1278"),
        (document_flow_payment, "_validate_payment_currency_match", "#1099"),
        (bancos_services, "_get_default_entity_type_for_payment_type", "#1100"),
        (bancos_services, "_bank_account_for_note", "#1100"),
        (bancos_services, "_payment_identifier_inputs", "#1100"),
    ],
)
def test_simbolos_retirados_no_reaparecen(modulo, simbolo, issue):  # noqa: ANN001 - parametrizado
    """Cada limpieza conserva su contrato de ausencia."""
    assert not hasattr(modulo, simbolo), f"{issue}: {simbolo} reapareció en {modulo.__name__}"


def test_formularios_de_setup_no_reintroducen_step_oculto(app):
    """#1909: la navegación del asistente no depende de campos step."""
    with app.test_request_context("/"):
        for formulario in (setup_forms.SetupLanguageForm, setup_forms.SetupRegionalForm, setup_forms.SetupCompanyForm):
            assert "step" not in formulario()._fields, formulario.__name__


@pytest.mark.parametrize("hoja", ["dashboard.css", "checkout.css", "purecss-treeview.css"])
def test_hojas_css_retiradas_no_reaparecen(hoja):
    """#1899: las hojas sin consumidor no vuelven al paquete."""
    assert not (RAIZ / "cacao_accounting" / "static" / "css" / hoja).exists()


def test_inventario_services_no_reexporta_company_currency():
    """#1308: la moneda canónica se consume desde document_flow.context."""
    from cacao_accounting.inventario import services as inventario_services

    assert not hasattr(inventario_services, "company_currency")


def test_orchestrator_no_reexpone_reversion_de_snapshot():
    """#1352: la reversión real vive en posting_service, no en un helper sin caller."""
    assert not hasattr(BusinessEventOrchestrator, "reverse_from_snapshot")


def test_modelos_workflow_sin_consumidor_no_reaparecen():
    """#1916: la familia de modelos workflow sin consumidor no vuelve al esquema."""
    from cacao_accounting import database as cacao_database

    for symbol in ("WorkflowActionLog", "WorkflowInstance", "WorkflowState", "WorkflowTransition"):
        assert not hasattr(cacao_database, symbol), f"#1916: {symbol} reapareció"


def test_excepciones_sin_consumidores_no_reaparecen():
    """#1841: DataError, OperationalError y AccessDenied no tienen consumidores."""
    from cacao_accounting import exceptions as cacao_exceptions

    for simbolo in ("DataError", "OperationalError", "AccessDenied"):
        assert not hasattr(cacao_exceptions, simbolo), f"{simbolo} reapareció sin consumidores"
