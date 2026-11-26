# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2292: el comparativo distingue error de cálculo de solicitud sin líneas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import inspect

import pytest

from cacao_accounting.compras.purchase_request_comparison_service import save_purchase_request_comparison_draft
from cacao_accounting.database import (
    PurchaseRequest,
    PurchaseRequestComparison,
    PurchaseRequestComparisonLine,
    PurchaseRequestComparisonOffer,
    PurchaseRequestItem,
    SupplierQuotation,
    SupplierQuotationItem,
    database,
)


def _cliente(escenario):
    """Autentica al administrador del escenario aislado."""
    application = escenario.app
    user_id = str(inspect(escenario.admin_user).identity[0])
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def _sembrar_comparativo(entorno, *, con_lineas: bool, sin_tasa: bool) -> str:
    """Crea un comparativo con una oferta y devuelve su identificador."""
    sufijo = uuid4().hex[:6]
    fecha = date(2026, 4, 15)
    with entorno.app.app_context():
        solicitud = PurchaseRequest(
            company="cacao",
            document_no=f"REQ-ERR-{sufijo}",
            requested_by="admin",
            posting_date=fecha,
            docstatus=1,
        )
        database.session.add(solicitud)
        database.session.flush()
        if con_lineas:
            database.session.add(
                PurchaseRequestItem(
                    purchase_request_id=solicitud.id,
                    item_code="ART01",
                    item_name="Artículo comparativo",
                    qty=Decimal("1"),
                    uom="UND",
                )
            )
        comparativo = PurchaseRequestComparison(
            company="cacao",
            purchase_request_id=solicitud.id,
            document_no=f"CMP-ERR-{sufijo}",
            posting_date=fecha,
            status="draft",
        )
        database.session.add(comparativo)
        database.session.flush()
        cotizacion = SupplierQuotation(
            company="cacao",
            posting_date=fecha,
            docstatus=1,
            document_no=f"SC-ERR-{sufijo}",
            supplier_name=f"Proveedor {sufijo}",
            transaction_currency="USD" if sin_tasa else "NIO",
            exchange_rate=Decimal("0") if sin_tasa else Decimal("1"),
        )
        database.session.add(cotizacion)
        database.session.flush()
        database.session.add(
            SupplierQuotationItem(
                supplier_quotation_id=cotizacion.id,
                item_code="ART01",
                item_name="Artículo comparativo",
                qty=Decimal("1"),
                uom="UND",
                rate=Decimal("100"),
            )
        )
        database.session.add(
            PurchaseRequestComparisonOffer(
                comparison_id=comparativo.id,
                supplier_quotation_id=cotizacion.id,
            )
        )
        database.session.commit()
        return comparativo.id


def test_error_de_conversion_no_muestra_solicitud_vacia(entorno_contable_aislado):
    """Una tasa faltante muestra su causa sin diagnosticar líneas inexistentes."""
    comparativo_id = _sembrar_comparativo(entorno_contable_aislado, con_lineas=True, sin_tasa=True)
    respuesta = _cliente(entorno_contable_aislado).get(f"/buying/request-for-quotation/comparison/{comparativo_id}")
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_data(as_text=True)
    assert "No existe tipo de cambio para comparar una oferta en USD contra NIO." in cuerpo
    assert "La Solicitud de Compra no tiene líneas." not in cuerpo


def test_solicitud_realmente_vacia_muestra_estado_vacio(entorno_contable_aislado):
    """El estado vacío aparece solo cuando la solicitud no tiene líneas."""
    comparativo_id = _sembrar_comparativo(entorno_contable_aislado, con_lineas=False, sin_tasa=False)
    respuesta = _cliente(entorno_contable_aislado).get(f"/buying/request-for-quotation/comparison/{comparativo_id}")
    assert respuesta.status_code == 200
    cuerpo = respuesta.get_data(as_text=True)
    assert "La Solicitud de Compra no tiene líneas." in cuerpo
    assert "No existe tipo de cambio" not in cuerpo


def test_guardar_borrador_rechaza_recomendaciones_incompletas(entorno_contable_aislado):
    """El error de conversión impide guardar decisiones sobre un comparativo incompleto."""
    comparativo_id = _sembrar_comparativo(entorno_contable_aislado, con_lineas=True, sin_tasa=True)
    with entorno_contable_aislado.app.app_context():
        comparativo = database.session.get(PurchaseRequestComparison, comparativo_id)
        with pytest.raises(ValueError, match="No existe tipo de cambio para comparar una oferta en USD contra NIO"):
            save_purchase_request_comparison_draft(comparativo, {}, {}, None)
        assert (
            database.session.execute(
                database.select(PurchaseRequestComparisonLine).where(
                    PurchaseRequestComparisonLine.comparison_id == comparativo_id
                )
            )
            .scalars()
            .all()
            == []
        )
