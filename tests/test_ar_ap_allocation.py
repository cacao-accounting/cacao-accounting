# SPDX-License-Identifier: Apache-2.0
"""Pruebas del planificador y ejecutor de asignaciones AR/AP."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from cacao_accounting.contabilidad.arap_allocation import (
    ARAPOpenItem,
    AllocationCurrencyError,
    AllocationOverpaymentError,
    AllocationRequest,
    OpenItemResolver,
    apply_allocation,
    plan_allocation,
)


def _resolver() -> OpenItemResolver:
    """Crea documentos AR/AP independientes para las pruebas."""
    return OpenItemResolver(
        [
            ARAPOpenItem("INV-NIO", "sales_invoice", "NIO", Decimal("1000")),
            ARAPOpenItem("INV-USD", "sales_invoice", "USD", Decimal("100")),
        ]
    )


def test_same_currency_supports_partial_and_full_allocation():
    """Dos líneas en la misma moneda pueden cerrar un documento parcialmente."""
    resolver = OpenItemResolver([ARAPOpenItem("INV", "sales_invoice", "NIO", Decimal("1000"))])
    plan = plan_allocation(
        Decimal("1000"),
        "NIO",
        [AllocationRequest("INV", Decimal("250"), idempotency_key="PAY-1")],
        resolver=resolver,
    )
    assert plan.lines[0].source_amount == Decimal("250.0000")
    assert plan.remaining_source_amount == Decimal("750")
    apply_allocation(plan, resolver=resolver)
    assert resolver.resolve("INV").outstanding == Decimal("750")

    full = plan_allocation(
        Decimal("750"),
        "NIO",
        [AllocationRequest("INV", idempotency_key="PAY-2")],
        resolver=resolver,
    )
    assert full.is_full
    apply_allocation(full, resolver=resolver)
    assert resolver.resolve("INV").outstanding == Decimal("0")


def test_cross_currency_uses_explicit_document_to_source_rate():
    """Una aplicación USD consume efectivo NIO según la tasa guardada."""
    resolver = _resolver()
    plan = plan_allocation(
        Decimal("3650"),
        "NIO",
        [AllocationRequest("INV-USD", Decimal("100"), rate=Decimal("36.5"))],
        resolver=resolver,
    )
    assert plan.lines[0].source_amount == Decimal("3650.0000")
    assert plan.lines[0].rate == Decimal("36.5")

    with pytest.raises(AllocationCurrencyError):
        plan_allocation(Decimal("3650"), "NIO", [AllocationRequest("INV-USD", Decimal("100"))], resolver=resolver)


def test_over_allocation_is_rejected_before_execution():
    """El exceso de saldo o efectivo no muta el resolver."""
    resolver = _resolver()
    with pytest.raises(AllocationOverpaymentError):
        plan_allocation(Decimal("10000"), "NIO", [AllocationRequest("INV-NIO", Decimal("1001"))], resolver=resolver)
    assert resolver.resolve("INV-NIO").outstanding == Decimal("1000")

    with pytest.raises(AllocationOverpaymentError):
        plan_allocation(
            Decimal("10"), "NIO", [AllocationRequest("INV-USD", Decimal("1"), rate=Decimal("36.5"))], resolver=resolver
        )
    assert resolver.resolve("INV-USD").outstanding == Decimal("100")


def test_apply_is_idempotent_and_rejects_key_reuse_with_different_amount():
    """Reintentar la misma clave no consume saldo dos veces."""
    resolver = OpenItemResolver([ARAPOpenItem("INV", "sales_invoice", "NIO", Decimal("1000"))])
    request = AllocationRequest("INV", Decimal("100"), idempotency_key="PAY-1-L1")
    plan = plan_allocation(Decimal("100"), "NIO", [request], resolver=resolver)
    assert len(apply_allocation(plan, resolver=resolver)) == 1
    assert len(apply_allocation(plan, resolver=resolver)) == 1
    assert resolver.resolve("INV").outstanding == Decimal("900")

    different = plan_allocation(
        Decimal("50"), "NIO", [AllocationRequest("INV", Decimal("50"), idempotency_key="PAY-2")], resolver=resolver
    )
    # Simulate a retry carrying the original key but another amount.
    altered = different.lines[0].__class__(
        document_id=different.lines[0].document_id,
        document_type=different.lines[0].document_type,
        document_currency=different.lines[0].document_currency,
        source_currency=different.lines[0].source_currency,
        document_amount=different.lines[0].document_amount,
        source_amount=different.lines[0].source_amount,
        rate=different.lines[0].rate,
        idempotency_key="PAY-1-L1",
    )
    from cacao_accounting.contabilidad.arap_allocation import AllocationPlan

    with pytest.raises(ValueError):
        apply_allocation(AllocationPlan("NIO", Decimal("50"), (altered,)), resolver=resolver)


def test_persistence_failure_rolls_back_balances_and_external_transaction():
    """Un fallo al persistir revierte estado local y llama al callback externo."""
    resolver = OpenItemResolver([ARAPOpenItem("INV", "sales_invoice", "NIO", Decimal("1000"))])
    plan = plan_allocation(
        Decimal("500"), "NIO", [AllocationRequest("INV", Decimal("500"), idempotency_key="PAY-FAIL")], resolver=resolver
    )
    rolled_back: list[bool] = []

    def persist(_line):
        """Simula error de escritura de ledger."""
        raise RuntimeError("database unavailable")

    with pytest.raises(RuntimeError):
        apply_allocation(plan, resolver=resolver, persist=persist, rollback=lambda: rolled_back.append(True))
    assert rolled_back == [True]
    assert resolver.resolve("INV").outstanding == Decimal("1000")


def test_resolver_adapts_cached_ar_ap_open_item_rows():
    """El DTO acepta el snapshot de consulta rápida sin volverlo fuente histórica."""
    from cacao_accounting.contabilidad.arap_allocation import ARAPOpenItem

    resolver = OpenItemResolver.from_models(
        [
            SimpleNamespace(
                document_id="INV-CACHE",
                document_type="sales_invoice",
                currency="USD",
                unallocated_amount=Decimal("25"),
                company="cacao",
                economic_line_id="LINE-1",
                account_id="AR-1",
                party_type="customer",
                party_id="P-1",
                ledger_type="AR",
                posting_date=None,
                document_no="INV-001",
            )
        ]
    )
    item = resolver.resolve("INV-CACHE")
    assert isinstance(item, ARAPOpenItem)
    assert item.outstanding == Decimal("25")
    assert item.economic_line_id == "LINE-1"


def test_resolver_requires_line_identity_when_document_has_multiple_open_items():
    """Una referencia a un comprobante con varias líneas no puede ser ambigua."""
    resolver = OpenItemResolver(
        [
            ARAPOpenItem("JE-1", "journal_entry", "USD", Decimal("50"), economic_line_id="L1", open_item_id="OI-1"),
            ARAPOpenItem("JE-1", "journal_entry", "USD", Decimal("75"), economic_line_id="L2", open_item_id="OI-2"),
        ]
    )
    with pytest.raises(ValueError, match="varias líneas"):
        resolver.resolve("JE-1")
    assert resolver.resolve("OI-2").outstanding == Decimal("75")
