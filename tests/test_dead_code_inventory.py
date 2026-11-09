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
    ],
)
def test_modulo_sin_consumidores_esta_retirado(module_name: str):
    """El módulo completo no debe volver sin un punto de entrada real."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)
