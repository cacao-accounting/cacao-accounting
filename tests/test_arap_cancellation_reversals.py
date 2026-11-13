# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Anulación AR/AP: no duplica reversas y encuentra el diario reversa.

Escenario de negocio (issue #2117): al anular una factura se volvía a revertir
una asignación ya neutralizada por la anulación del pago; además la apertura
creada por un diario de reversa no se encontraba por su voucher.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.arap_ledger_service import cancel_document_ar_ap
from cacao_accounting.database import ARAPLedgerEntry, ComprobanteContable, Currency, Entity, Party, database

FECHA = date(2026, 10, 15)


def _crear_app():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao SA",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.add(Party(id="CUST-1", code="CUST-1", name="Cliente", is_customer=True, is_supplier=False))
        database.session.commit()
    return application


def _movimiento(**kwargs) -> ARAPLedgerEntry:
    datos = {
        "company": "cacao",
        "ledger_type": "AR",
        "party_type": "customer",
        "party_id": "CUST-1",
        "document_type": "sales_invoice",
        "document_id": "INV-1",
        "posting_date": FECHA,
        "event_type": "opening",
        "currency": "NIO",
        "document_amount": 100,
        "voucher_type": "sales_invoice",
        "voucher_id": "INV-1",
        "is_reversal": False,
    }
    datos.update(kwargs)
    return ARAPLedgerEntry(**datos)


def test_no_revierte_una_asignacion_ya_neutralizada():
    """La asignación con reversa previa no recibe una segunda contrapartida."""
    application = _crear_app()
    try:
        with application.app_context():
            apertura = _movimiento(event_type="opening", document_amount=100)
            asignacion = _movimiento(event_type="allocation", document_amount=-100)
            database.session.add_all([apertura, asignacion])
            database.session.flush()
            database.session.add(
                _movimiento(
                    event_type="cancellation",
                    document_amount=100,
                    is_reversal=True,
                    reversal_of=asignacion.id,
                    voucher_type="payment_entry",
                    voucher_id="PAY-1",
                )
            )
            database.session.commit()

            factura = SimpleNamespace(
                id="INV-1",
                document_type="sales_invoice",
                company="cacao",
                posting_date=FECHA,
            )
            reversas = cancel_document_ar_ap(factura)
            database.session.flush()

            assert {row.reversal_of for row in reversas} == {apertura.id}
            total_asignacion = (
                database.session.execute(
                    database.select(ARAPLedgerEntry).where(
                        ARAPLedgerEntry.is_reversal.is_(True),
                        ARAPLedgerEntry.reversal_of == asignacion.id,
                    )
                )
                .scalars()
                .all()
            )
            assert len(total_asignacion) == 1
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_anular_un_diario_reversa_encuentra_su_apertura():
    """El diario R1 se localiza por voucher_id aunque su apertura sea reversa."""
    application = _crear_app()
    try:
        with application.app_context():
            apertura_original = _movimiento(
                document_type="journal_entry",
                document_id="ORIG-1",
                event_type="opening",
                voucher_type="journal_entry",
                voucher_id="ORIG-OPEN",
                document_amount=100,
            )
            database.session.add(apertura_original)
            database.session.flush()
            diario = ComprobanteContable(
                id="R1",
                entity="cacao",
                date=FECHA,
                reference="Reversa",
                memo="Reversa",
            )
            apertura_reversa = _movimiento(
                document_type="journal_entry",
                document_id="ORIG-1",
                event_type="opening",
                voucher_type="journal_entry",
                voucher_id="R1",
                is_reversal=True,
                reversal_of=apertura_original.id,
                document_amount=-100,
            )
            asignacion = _movimiento(
                document_type="sales_invoice",
                document_id="INV-1",
                event_type="allocation",
                voucher_type="journal_entry",
                voucher_id="R1",
                document_amount=100,
            )
            database.session.add_all([apertura_reversa, asignacion])
            database.session.commit()

            reversas = cancel_document_ar_ap(diario)
            database.session.flush()

            assert {row.reversal_of for row in reversas} == {apertura_reversa.id, asignacion.id}
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
