# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Inventario de helpers retirados por falta de consumidores.

Escenario de mantenimiento (#1841): estos helpers no tienen llamadores en
código productivo, plantillas, scripts ni puntos de entrada dinámicos. El test
fija el contrato de que la superficie muerta no vuelva a introducirse.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    "module_name, symbol",
    [
        ("cacao_accounting.reportes.helpers", "_report_form_key"),
        ("cacao_accounting.reportes.helpers", "_extract_filter_payload"),
        ("cacao_accounting.reportes.helpers", "_restore_filters_from_view"),
        ("cacao_accounting.bancos.services", "_get_default_entity_type_for_payment_type"),
        ("cacao_accounting.bancos.services", "_bank_account_for_note"),
        ("cacao_accounting.bancos.services", "_payment_identifier_inputs"),
        ("cacao_accounting.document_identifiers", "record_external_number_used"),
        ("cacao_accounting.bancos.statement_service", "import_bank_statement"),
        ("cacao_accounting.bancos.statement_service", "suggest_bank_matches"),
        ("cacao_accounting.auth.roles", "RegistroRol"),
        ("cacao_accounting.auth.roles", "RegistroRolUsuario"),
        ("cacao_accounting.auth.permisos", "RegistroPermisosRol"),
        ("cacao_accounting.printing.service", "TemplateValidationResult"),
        ("cacao_accounting.printing.exceptions", "PrintableDocumentNotRegisteredError"),
        ("cacao_accounting.exceptions", "TransactionError"),
        ("cacao_accounting.setup.forms", "SetupConfirmationForm"),
        ("cacao_accounting.bancos.forms", "FormularioPago"),
        ("cacao_accounting.config", "probar_modo_escritorio"),
        ("cacao_accounting.setup.repository", "get_default_entity"),
        ("cacao_accounting.modulos", "lista_tipos_documentos"),
        ("cacao_accounting.party_management", "party_account_labels"),
        ("cacao_accounting.party_management", "build_party_code"),
        ("cacao_accounting.tax_pricing_service", "get_item_price"),
        ("cacao_accounting.tax_pricing_service", "validate_price_tolerance"),
        ("cacao_accounting.tax_pricing_service", "PriceToleranceResult"),
        ("cacao_accounting.tax_pricing_service", "PriceSuggestion"),
        ("cacao_accounting.contabilidad.arap_allocation", "resolve_open_item"),
        ("cacao_accounting.contabilidad.default_accounts", "accounts_for_company"),
        ("cacao_accounting.datos.dev", "series_predeterminadas"),
        ("cacao_accounting.datos.dev.data", "_make_series"),
        ("cacao_accounting.auth.device_verification", "listar_dispositivos"),
        ("cacao_accounting.admin.session_security_service", "listar_dispositivos_usuario"),
        ("cacao_accounting.database", "BaseTercero"),
        ("cacao_accounting.database", "CommentMention"),
        ("cacao_accounting.database", "Assignment"),
        ("cacao_accounting.database", "Workflow"),
        ("cacao_accounting.database", "WorkflowState"),
        ("cacao_accounting.database", "WorkflowTransition"),
        ("cacao_accounting.database", "WorkflowInstance"),
        ("cacao_accounting.database", "WorkflowActionLog"),
        ("cacao_accounting.database", "GLEntryDimension"),
        ("cacao_accounting.cancellation_scope", "audit_gl_scope"),
        ("cacao_accounting.cancellation_scope", "append_only_gl_scope"),
        ("cacao_accounting.bancos.services", "petty_cash_account_choices"),
        ("cacao_accounting.bancos.services", "update_petty_cash_voucher"),
        ("cacao_accounting.contabilidad.recurring_journal_service", "_canonical_book_reference"),
        ("cacao_accounting.contabilidad.recurring_journal_service", "_normalize_ledger_id_for_validation"),
        ("cacao_accounting.contabilidad.posting_service", "_normalize_ledger_codes"),
        ("cacao_accounting.contabilidad.posting_service", "_delivery_outgoing_totals"),
        ("cacao_accounting.contabilidad.posting_service", "_receipt_total"),
        ("cacao_accounting.contabilidad.posting_service", "_validate_cancel_accounting_period"),
        ("cacao_accounting.database.helpers", "obtener_id_usuario_por_nombre"),
        ("cacao_accounting.database", "obtiene_texto_unico_cuid2"),
        ("cacao_accounting.document_identifiers", "suggest_next_external_number"),
        ("cacao_accounting.audit_trail_service", "log_reverse"),
        ("cacao_accounting.audit_trail_service", "log_delete_attempt"),
        ("cacao_accounting.contabilidad.forms", "FormularioSecuencia"),
        ("cacao_accounting.contabilidad.services", "_build_project_from_form"),
        ("cacao_accounting.compras.services", "_comparison_item_at_occurrence"),
        ("cacao_accounting.compras.purchase_reconciliation_service", "_find_order_item_for_invoice_line"),
        ("cacao_accounting.compras.purchase_reconciliation_service", "_find_receipt_item_for_invoice_line"),
        ("cacao_accounting.compras.purchase_reconciliation_service", "_group_lines_by_item_and_uom"),
        ("cacao_accounting.bancos.cash_forecast_service", "_query_gl_sum"),
        ("cacao_accounting.api.dashboard", "_sum_query"),
        ("cacao_accounting.bancos.reconciliation_service", "backfill_reconciliation_item_context"),
        ("cacao_accounting.compras.purchase_order_comparison_service", "comparable_purchase_orders"),
        ("cacao_accounting.compras.purchase_request_comparison_service", "purchase_request_comparison_is_closed"),
        ("cacao_accounting.compras.purchase_request_comparison_service", "supplier_quotation_comparison_rows"),
        ("cacao_accounting.contabilidad.recurring_journal_service", "get_applicable_templates"),
        ("cacao_accounting.contabilidad.journal_repository", "list_journals"),
        ("cacao_accounting.document_flow.repository", "recompute_states_for_source"),
        ("cacao_accounting.inventario.service", "rebuild_stock_bins"),
        ("cacao_accounting.contabilidad.arap_gl_reconciliation", "reconcile_companies_arap_to_gl"),
    ],
)
def test_helper_sin_consumidores_esta_retirado(module_name: str, symbol: str):
    """El helper no debe volver a existir sin un consumidor real."""
    module = importlib.import_module(module_name)

    assert not hasattr(module, symbol)


@pytest.mark.parametrize(
    "module_name",
    [
        "cacao_accounting.compras.purchase_invoice_draft_service",
        "cacao_accounting.reportes.semantic",
        "cacao_accounting.accounting_engine.fiscal.resolver",
    ],
)
def test_modulo_sin_consumidores_esta_retirado(module_name: str):
    """El módulo completo no debe volver sin un punto de entrada real."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)
