# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Contratos de retiro de código sin consumidores.

Sustituye al inventario eliminado en ``0970476b``: cada símbolo retirado en
esta limpieza no debe reaparecer sin una decisión y pruebas propias.

Superficie dinámica excluida del retiro (#1841), porque su consumidor no
aparece en el grafo de imports:

- ``cacao_accounting/query_tools``: API pública para plugins externos y
  entry point declarado en ``pyproject``.
- ``cacao_accounting/cli.py`` y ``__main__.py``: invocado por consola.
- Filtros y globales registrados en ``printing``: los consume Jinja desde
  plantillas guardadas en base de datos.
"""

from __future__ import annotations

import importlib
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


# Inventario de #1841 verificado contra HEAD: cada símbolo fue retirado por no
# tener consumidor en producto, plantilla, CLI ni API documentada.
RETIRADOS_1841 = [
    ("cacao_accounting.cancellation_scope", "audit_gl_scope"),
    ("cacao_accounting.cancellation_scope", "append_only_gl_scope"),
    ("cacao_accounting.reportes.helpers", "_report_form_key"),
    ("cacao_accounting.reportes.helpers", "_extract_filter_payload"),
    ("cacao_accounting.reportes.helpers", "_restore_filters_from_view"),
    ("cacao_accounting.reportes.helpers", "_safe_page_size"),
    ("cacao_accounting.reportes.helpers", "_str_or_none"),
    ("cacao_accounting.bancos.services", "petty_cash_account_choices"),
    ("cacao_accounting.bancos.services", "update_petty_cash_voucher"),
    ("cacao_accounting.bancos.statement_service", "suggest_bank_matches"),
    ("cacao_accounting.bancos.forms", "FormularioPago"),
    ("cacao_accounting.contabilidad.recurring_journal_service", "_canonical_book_reference"),
    ("cacao_accounting.contabilidad.recurring_journal_service", "_normalize_ledger_id_for_validation"),
    ("cacao_accounting.contabilidad.posting_service", "_normalize_ledger_codes"),
    ("cacao_accounting.contabilidad.posting_service", "_delivery_outgoing_totals"),
    ("cacao_accounting.contabilidad.posting_service", "_receipt_total"),
    ("cacao_accounting.contabilidad.posting_service", "_validate_cancel_accounting_period"),
    ("cacao_accounting.contabilidad.forms", "FormularioSecuencia"),
    ("cacao_accounting.contabilidad.arap_allocation", "resolve_open_item"),
    ("cacao_accounting.contabilidad.default_accounts", "accounts_for_company"),
    ("cacao_accounting.database", "obtiene_texto_unico_cuid2"),
    ("cacao_accounting.database", "GLEntryDimension"),
    ("cacao_accounting.database", "CommentMention"),
    ("cacao_accounting.database", "Assignment"),
    ("cacao_accounting.database", "BaseTercero"),
    ("cacao_accounting.database.helpers", "obtener_id_usuario_por_nombre"),
    ("cacao_accounting.document_identifiers", "suggest_next_external_number"),
    ("cacao_accounting.audit_trail_service", "log_reverse"),
    ("cacao_accounting.audit_trail_service", "log_delete_attempt"),
    ("cacao_accounting.printing.service", "TemplateValidationResult"),
    ("cacao_accounting.auth.roles", "RegistroRol"),
    ("cacao_accounting.auth.roles", "RegistroRolUsuario"),
    ("cacao_accounting.auth.permisos", "RegistroPermisosRol"),
    ("cacao_accounting.auth.device_verification", "listar_dispositivos"),
    ("cacao_accounting.admin.session_security_service", "listar_dispositivos_usuario"),
    ("cacao_accounting.setup.forms", "SetupConfirmationForm"),
    ("cacao_accounting.setup.repository", "get_default_entity"),
    ("cacao_accounting.modulos", "lista_tipos_documentos"),
    ("cacao_accounting.config", "probar_modo_escritorio"),
    ("cacao_accounting.datos.dev", "series_predeterminadas"),
    ("cacao_accounting.exceptions", "TransactionError"),
]


@pytest.mark.parametrize(("modulo", "simbolo"), RETIRADOS_1841)
def test_inventario_1841_permanece_retirado(modulo: str, simbolo: str):
    """#1841: ningún candidato del inventario vuelve sin decisión y pruebas."""
    assert not hasattr(importlib.import_module(modulo), simbolo), f"{simbolo} reapareció en {modulo}"


@pytest.mark.parametrize(
    "ruta",
    [
        "cacao_accounting/reportes/semantic.py",
        "cacao_accounting/accounting_engine/fiscal/resolver.py",
        "cacao_accounting/compras/purchase_invoice_draft_service.py",
    ],
)
def test_modulos_sin_consumidor_no_reaparecen(ruta: str):
    """#1841: los módulos retirados por completo no se reintroducen."""
    assert not (RAIZ / ruta).exists(), f"{ruta} reapareció sin consumidores"


def test_query_tools_conserva_su_contrato_publico():
    """#1841: ``query_tools`` queda fuera de la limpieza por ser API para plugins."""
    from cacao_accounting.query_tools import QueryContext, Registry, load_query_tools, query_tool

    assert callable(query_tool) and callable(load_query_tools)
    assert hasattr(Registry, "register") and hasattr(QueryContext, "__init__")
