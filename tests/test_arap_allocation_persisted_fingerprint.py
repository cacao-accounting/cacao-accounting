# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1836: la idempotencia AR/AP compara el contenido persistido, no solo la clave."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.arap_allocation import (
    ARAPOpenItem,
    AllocationIdempotencyError,
    AllocationLine,
    AllocationRequest,
    OpenItemResolver,
    allocation_fingerprint,
    load_existing_allocation_fingerprints,
    plan_allocation,
)
from cacao_accounting.database import (
    Currency,
    Entity,
    Party,
    PaymentEntry,
    PaymentReference,
    database,
)


@pytest.fixture(params=[True, False], ids=["desktop", "cloud"])
def persisted_allocation(request):
    """Persiste una asignación con clave y huella en una base aislada."""
    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": request.param,
        }
    )
    sufijo = uuid4().hex[:8]
    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="alpha",
                    name="Alfa",
                    company_name=f"Compañía Alfa {sufijo}",
                    tax_id=f"TAX-{sufijo}",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        proveedor = Party(code=f"PROV-{sufijo}", name=f"Proveedor {sufijo}", is_supplier=True)
        database.session.add(proveedor)
        database.session.flush()
        pago = PaymentEntry(
            company="alpha",
            payment_type="pay",
            party_type="supplier",
            party_id=proveedor.id,
            currency="NIO",
            docstatus=1,
        )
        database.session.add(pago)
        database.session.flush()
        documento_id = f"INV-{sufijo}"
        clave = f"{pago.id}:purchase_invoice:{documento_id}"
        linea = AllocationLine(
            document_id=documento_id,
            document_type="purchase_invoice",
            document_currency="NIO",
            source_currency="NIO",
            document_amount=Decimal("80"),
            source_amount=Decimal("80"),
            rate=Decimal("1"),
            idempotency_key=clave,
        )
        referencia = PaymentReference(
            payment_id=pago.id,
            reference_type="purchase_invoice",
            reference_id=documento_id,
            party_type="supplier",
            party_id=proveedor.id,
            company="alpha",
            currency="NIO",
            allocated_amount=Decimal("80"),
            idempotency_key=clave,
            allocation_fingerprint=allocation_fingerprint(linea),
        )
        database.session.add(referencia)
        database.session.commit()
        yield app, pago.id, documento_id, clave, linea

    with app.app_context():
        database.session.remove()
        database.engine.dispose()


def _plan(pago_id: str, documento_id: str, clave: str, monto: str):
    """Planifica en una sesión distinta usando la huella leída de la BD."""
    item = ARAPOpenItem(
        document_id=documento_id,
        document_type="purchase_invoice",
        currency="NIO",
        outstanding=Decimal("100"),
    )
    return plan_allocation(
        Decimal("100"),
        "NIO",
        [AllocationRequest(document_id=documento_id, amount=Decimal(monto), idempotency_key=clave)],
        resolver=OpenItemResolver([item]),
        existing_keys=load_existing_allocation_fingerprints(pago_id),
    )


def test_la_huella_se_carga_en_otra_sesion(persisted_allocation):
    """La consulta a PaymentReference reconstruye la clave y el contenido."""
    app, pago_id, _, clave, linea = persisted_allocation
    with app.app_context():
        database.session.remove()
        existing = load_existing_allocation_fingerprints(pago_id)
        assert existing[clave] == allocation_fingerprint(linea)


def test_repeticion_identica_no_planifica_asignacion(persisted_allocation):
    """Un reintento con el mismo contenido no produce una segunda línea."""
    app, pago_id, documento_id, clave, _ = persisted_allocation
    with app.app_context():
        database.session.remove()
        plan = _plan(pago_id, documento_id, clave, "80")
        assert plan.lines == ()
        assert plan.allocated_source_amount == Decimal("0")


def test_mismo_id_con_otro_importe_conflicta(persisted_allocation):
    """La clave reutilizada con otro importe se rechaza sin plan parcial."""
    app, pago_id, documento_id, clave, _ = persisted_allocation
    with app.app_context():
        database.session.remove()
        with pytest.raises(AllocationIdempotencyError, match="otro contenido"):
            _plan(pago_id, documento_id, clave, "100")


def test_fila_legacy_sin_huella_falla_cerrado(persisted_allocation):
    """Una clave persistida sin huella no puede acreditarse como repetición."""
    app, pago_id, documento_id, clave, _ = persisted_allocation
    with app.app_context():
        database.session.execute(
            database.update(PaymentReference)
            .where(PaymentReference.idempotency_key == clave)
            .values(allocation_fingerprint=None)
        )
        database.session.commit()
        database.session.remove()
        with pytest.raises(AllocationIdempotencyError, match="contenido persistido"):
            _plan(pago_id, documento_id, clave, "80")


def test_otra_compania_no_ve_la_huella(persisted_allocation):
    """El loader está acotado al pago, preservando el aislamiento por compañía."""
    app, pago_id, _, clave, _ = persisted_allocation
    with app.app_context():
        database.session.remove()
        assert load_existing_allocation_fingerprints(f"otro-{pago_id}") == {}
        assert clave not in load_existing_allocation_fingerprints(f"otro-{pago_id}")
