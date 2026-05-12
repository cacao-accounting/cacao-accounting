# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Modulo de compatibilidad — OBSOLETO.

La terminologia GR/IR (Goods Receipt / Invoice Receipt) es propia de SAP
y queda prohibida en este proyecto.  Usar purchase_reconciliation_service.py.
"""

# Re-exporta todos los simbolos desde el nuevo modulo para no romper imports existentes.
from cacao_accounting.compras.purchase_reconciliation_service import (  # noqa: F401
    EventType,
    GRIRServiceError,
    MatchingConfig,
    MatchingResult,
    MatchingType,
    PurchasePendingRow,
    PurchaseReconciliationError,
    PurchaseReconciliationResult,
    ReconciliationStateSnapshot,
    ToleranceType,
    cancel_purchase_reconciliation,
    emit_economic_event,
    emit_goods_received_cancelled,
    get_events_for_document,
    get_matching_config,
    get_purchase_reconciliation_pending,
    mark_event_processed,
    reconcile_purchase_invoice,
    reconstruct_reconciliation_state,
    seed_matching_config_for_company,
)

# Legacy aliases for any callers still using old names
reconcile_gr_ir_invoice = reconcile_purchase_invoice
cancel_gr_ir_for_invoice = cancel_purchase_reconciliation
get_gr_ir_pending = get_purchase_reconciliation_pending
