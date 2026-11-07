# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes
"""Contratos del esquema y la interfaz canónica de los modelos."""

import cacao_accounting.database as database_module
from cacao_accounting.database import (
    ARAPLedgerBookEntry,
    ArApReconciliationPolicy,
    ComprobanteContable,
    Entity,
    Modules,
    Unit,
)
from cacao_accounting.internal_control_service import MUTABLE_STATE


def test_comprobante_contable_expone_solo_estado_canonico():
    """El esquema manual no declara campos legacy sin consumidores."""
    columns = set(ComprobanteContable.__table__.columns.keys())

    assert columns.isdisjoint({"canceled", "canceled_by", "applied_by", "sequential", "sequential_id"})
    assert {"cancelled_at", "cancelled_by", "cancel_reason", "applied", "document_no", "naming_series_id"} <= columns
    assert MUTABLE_STATE.isdisjoint({"canceled", "canceled_by"})


def test_modelos_exponen_nombres_canonicos_sin_aliases_legacy():
    """Los modelos mantienen una sola interfaz ORM por nombre o campo."""
    assert not hasattr(database_module, "Modulos")
    assert not hasattr(database_module, "Unidad")
    assert not hasattr(database_module, "ARAPReconciliationPolicy")
    assert not hasattr(Entity, "is_active")
    assert not hasattr(ArApReconciliationPolicy, "is_enabled")

    legacy_ledger_fields = {
        "amount_document",
        "amount_in_book_currency",
        "functional_amount",
        "functional_currency",
        "book_id",
        "source_currency",
        "destination_currency",
        "amount_in_document_currency",
        "amount_in_functional_currency",
    }
    assert all(not hasattr(ARAPLedgerBookEntry, field) for field in legacy_ledger_fields)
    assert Modules.__name__ == "Modules"
    assert Unit.__name__ == "Unit"
    assert hasattr(ArApReconciliationPolicy, "enabled")
    assert hasattr(ARAPLedgerBookEntry, "document_amount")
    assert hasattr(ARAPLedgerBookEntry, "book_amount")
