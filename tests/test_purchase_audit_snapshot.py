# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El snapshot de auditoría de facturas de compra (#2137) cubre la cabecera ampliada.

La edición de una factura de compra en borrador debe registrar en el AuditTrail
los campos ``supplier_invoice_no``, ``tax_template_id``, ``transaction_currency``,
``exchange_rate`` y los datos logísticos, con el par antes/después por campo.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.database import (
    AuditTrail,
    CompanyParty,
    DocumentTaxLine,
    DocumentTaxSummary,
    Party,
    PurchaseInvoice,
    PurchaseInvoiceItem,
    PurchaseMatchingConfig,
    PurchaseOrder,
    SupplierQuotation,
    SupplierQuotationItem,
    TaxTemplate,
    database,
)


@pytest.fixture
def factura_editable(app, entorno_contable):
    """Factura de compra borrador con orden de compra, plantilla de impuesto y línea."""
    sufijo = uuid4().hex[:10]
    with app.app_context():
        matching_config = database.session.execute(
            database.select(PurchaseMatchingConfig).filter_by(company="cacao")
        ).scalar_one_or_none()
        matching_config_created = matching_config is None
        previous_order_requirement = matching_config.require_purchase_order if matching_config is not None else None
        if matching_config is None:
            matching_config = PurchaseMatchingConfig(
                company="cacao",
                matching_type="2-way",
                require_purchase_order=False,
                bridge_account_required=False,
                auto_reconcile=False,
            )
            database.session.add(matching_config)
        else:
            matching_config.require_purchase_order = False
        proveedor = Party(
            code=f"PRV-AUD-{sufijo}",
            name=f"Proveedor auditoría {sufijo}",
            is_supplier=True,
        )
        database.session.add(proveedor)
        database.session.flush()
        company_party = CompanyParty(
            company="cacao",
            party_id=proveedor.id,
            is_active=True,
            allow_purchase_invoice_without_order=True,
            allow_purchase_invoice_without_receipt=True,
        )
        database.session.add(company_party)
        orden = PurchaseOrder(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"PO-AUD-{sufijo}",
            supplier_id=proveedor.id,
            supplier_name=proveedor.name,
        )
        plantilla = TaxTemplate(
            name=f"Plantilla de compra {sufijo}",
            company="cacao",
            template_type="buying",
            is_active=True,
        )
        database.session.add_all([orden, plantilla])
        database.session.flush()
        factura = PurchaseInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=0,
            document_no=f"FI-AUD-{sufijo}",
            supplier_id=proveedor.id,
            supplier_name=proveedor.name,
            supplier_invoice_no=f"FAC-ORIGEN-{sufijo}",
            tax_template_id=plantilla.id,
            document_type="purchase_invoice",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(factura)
        database.session.flush()
        database.session.add(
            PurchaseInvoiceItem(
                purchase_invoice_id=factura.id,
                item_code="ART01",
                item_name="Articulo Comercial",
                qty=Decimal("2"),
                uom="UND",
                rate=Decimal("10"),
                amount=Decimal("20"),
            )
        )
        database.session.commit()
        ids = {
            "factura": factura.id,
            "orden": orden.id,
            "plantilla": plantilla.id,
            "proveedor": proveedor.id,
            "sufijo": sufijo,
            "matching_config_created": matching_config_created,
            "previous_order_requirement": previous_order_requirement,
        }
    yield ids
    with app.app_context():
        # La evidencia de auditoría es append-only y sostiene la cadena de
        # hashes compartida por el worker: no se elimina al limpiar la prueba.
        resumenes = (
            database.session.execute(
                database.select(DocumentTaxSummary).filter_by(document_type="purchase_invoice", document_id=ids["factura"])
            )
            .scalars()
            .all()
        )
        for resumen in resumenes:
            database.session.execute(
                database.delete(DocumentTaxLine).where(DocumentTaxLine.document_tax_summary_id == resumen.id)
            )
            database.session.delete(resumen)
        factura = database.session.get(PurchaseInvoice, ids["factura"])
        if factura is not None:
            database.session.execute(
                database.delete(PurchaseInvoiceItem).where(PurchaseInvoiceItem.purchase_invoice_id == factura.id)
            )
            database.session.delete(factura)
        orden = database.session.get(PurchaseOrder, ids["orden"])
        if orden is not None:
            database.session.delete(orden)
        plantilla = database.session.get(TaxTemplate, ids["plantilla"])
        if plantilla is not None:
            database.session.delete(plantilla)
        database.session.execute(
            database.delete(CompanyParty).where(CompanyParty.party_id == ids["proveedor"], CompanyParty.company == "cacao")
        )
        proveedor = database.session.get(Party, ids["proveedor"])
        if proveedor is not None:
            database.session.delete(proveedor)
        matching_config = database.session.execute(
            database.select(PurchaseMatchingConfig).filter_by(company="cacao")
        ).scalar_one_or_none()
        if matching_config is not None:
            if ids["matching_config_created"]:
                database.session.delete(matching_config)
            else:
                matching_config.require_purchase_order = bool(ids["previous_order_requirement"])
        database.session.commit()


def _ultimo_cambio_de_factura(app, factura_id):
    """Devuelve la entrada de auditoría de actualización más reciente del documento."""
    with app.app_context():
        entrada = database.session.execute(
            database.select(AuditTrail)
            .filter_by(document_type="purchase_invoice", document_id=factura_id, action="updated")
            .order_by(AuditTrail.timestamp.desc(), AuditTrail.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        assert entrada is not None, "La edición no registró una entrada de auditoría."
        return (
            json.loads(entrada.changes_json),
            json.loads(entrada.before_json),
            json.loads(entrada.after_json),
        )


def _editar_factura(authenticated_client, factura_id, datos):
    """Envía la edición de la factura en borrador y devuelve la respuesta seguida."""
    respuesta = authenticated_client("admin").post(
        f"/buying/purchase-invoice/{factura_id}/edit",
        data=datos,
        follow_redirects=True,
    )
    assert respuesta.status_code == 200
    return respuesta


def test_edicion_registra_numero_de_proveedor_y_plantilla_en_auditoria(app, authenticated_client, factura_editable):
    """changes_json incluye supplier_invoice_no y tax_template_id con antes y después distintos."""
    ids = factura_editable
    datos = {
        "supplier_id": ids["proveedor"],
        "company": "cacao",
        "posting_date": "2026-05-15",
        "supplier_invoice_no": f"FAC-EDITADA-{ids['sufijo']}",
        "tax_template_id": "",
        "remarks": "Edición controlada de prueba",
        "item_code_0": "ART01",
        "item_name_0": "Articulo Comercial",
        "qty_0": "2",
        "uom_0": "UND",
        "rate_0": "10",
        "amount_0": "20",
    }
    respuesta = _editar_factura(authenticated_client, ids["factura"], datos)

    assert "Factura de compra actualizada correctamente." in respuesta.get_data(as_text=True)
    cambios, antes, despues = _ultimo_cambio_de_factura(app, ids["factura"])
    assert cambios["supplier_invoice_no"]["before"] == f"FAC-ORIGEN-{ids['sufijo']}"
    assert cambios["supplier_invoice_no"]["after"] == f"FAC-EDITADA-{ids['sufijo']}"
    assert cambios["tax_template_id"]["before"] == ids["plantilla"]
    assert cambios["tax_template_id"]["after"] is None
    assert antes["supplier_invoice_no"] != despues["supplier_invoice_no"]


def test_edicion_registra_moneda_tasa_y_logistica_en_auditoria(app, authenticated_client, factura_editable):
    """El snapshot cubre transaction_currency, exchange_rate y los campos logísticos."""
    ids = factura_editable
    datos = {
        "supplier_id": ids["proveedor"],
        "company": "cacao",
        "posting_date": "2026-05-15",
        "transaction_currency": "USD",
        "currency": "USD",
        "supplier_invoice_no": f"FAC-ORIGEN-{ids['sufijo']}",
        "tax_template_id": "",
        "remarks": "Cambio de moneda y logística",
        "delivery_date": "2026-06-30",
        "delivery_place": f"Puerto Aéreo {ids['sufijo']}",
        "item_code_0": "ART01",
        "item_name_0": "Articulo Comercial",
        "qty_0": "2",
        "uom_0": "UND",
        "rate_0": "10",
        "amount_0": "20",
    }
    respuesta = _editar_factura(authenticated_client, ids["factura"], datos)

    assert "Factura de compra actualizada correctamente." in respuesta.get_data(as_text=True)
    cambios, antes, despues = _ultimo_cambio_de_factura(app, ids["factura"])
    assert cambios["transaction_currency"]["before"] == "NIO"
    assert cambios["transaction_currency"]["after"] == "USD"
    assert Decimal(cambios["exchange_rate"]["before"]) == Decimal("1")
    assert Decimal(cambios["exchange_rate"]["after"]) == Decimal("36.5")
    assert cambios["delivery_date"]["before"] is None
    assert cambios["delivery_date"]["after"] == "2026-06-30"
    assert cambios["delivery_place"]["after"] == f"Puerto Aéreo {ids['sufijo']}"
    assert despues["exchange_rate"] == cambios["exchange_rate"]["after"]
    assert antes["items"] and despues["items"]
    assert cambios["base_grand_total"]["before"] is None
    assert Decimal(cambios["base_grand_total"]["after"]) > 0
    assert antes["tax_summary"] is None
    assert despues["tax_lines"] == []


def test_snapshot_incluye_evidencia_fiscal_antes_de_editar(app, authenticated_client, factura_editable):
    """El estado capturado incluye el resumen y las líneas fiscales persistidas (#2143)."""
    ids = factura_editable
    with app.app_context():
        summary = DocumentTaxSummary(
            company="cacao",
            document_type="purchase_invoice",
            document_id=ids["factura"],
            currency="NIO",
            subtotal=Decimal("20"),
            document_tax_total=Decimal("2"),
            grand_total=Decimal("22"),
        )
        database.session.add(summary)
        database.session.flush()
        database.session.add(
            DocumentTaxLine(
                document_tax_summary_id=summary.id,
                line_index=0,
                concept="IVA de prueba",
                tax_type="tax",
                calculation_method="manual",
                amount=Decimal("2"),
            )
        )
        database.session.commit()

    datos = {
        "supplier_id": ids["proveedor"],
        "company": "cacao",
        "posting_date": "2026-05-15",
        "supplier_invoice_no": f"FAC-ORIGEN-{ids['sufijo']}",
        "tax_template_id": ids["plantilla"],
        "remarks": "Edición con evidencia fiscal",
        "item_code_0": "ART01",
        "item_name_0": "Articulo Comercial",
        "qty_0": "2",
        "uom_0": "UND",
        "rate_0": "10",
        "amount_0": "20",
    }
    _editar_factura(authenticated_client, ids["factura"], datos)

    _cambios, antes, despues = _ultimo_cambio_de_factura(app, ids["factura"])
    assert antes["tax_summary"]["document_id"] == ids["factura"]
    assert antes["tax_summary"]["document_tax_total"] == "2.0000"
    assert antes["tax_lines"][0]["concept"] == "IVA de prueba"
    assert "tax_summary" in despues


@pytest.fixture
def cotizacion_con_landed_cost(app, entorno_contable):
    """Cotización de proveedor borrador con un estimado inicial de landed costs."""
    sufijo = uuid4().hex[:10]
    inicial = json.dumps([{"concept": "Flete inicial", "amount": "10"}], ensure_ascii=False, separators=(",", ":"))
    with app.app_context():
        proveedor = Party(code=f"PRV-LC-{sufijo}", name=f"Proveedor LC {sufijo}", is_supplier=True)
        database.session.add(proveedor)
        database.session.flush()
        cotizacion = SupplierQuotation(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=0,
            document_no=f"SQ-LC-{sufijo}",
            supplier_id=proveedor.id,
            supplier_name=proveedor.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            landed_cost_estimates_json=inicial,
        )
        database.session.add(cotizacion)
        database.session.flush()
        database.session.add(
            SupplierQuotationItem(
                supplier_quotation_id=cotizacion.id,
                item_code="ART01",
                qty=Decimal("2"),
                qty_in_base_uom=Decimal("2"),
                uom="UND",
                rate=Decimal("3"),
                amount=Decimal("6"),
            )
        )
        database.session.commit()
        ids = {"cotizacion": cotizacion.id, "proveedor": proveedor.id, "inicial": inicial}
    yield ids
    with app.app_context():
        database.session.execute(
            database.delete(SupplierQuotationItem).where(SupplierQuotationItem.supplier_quotation_id == ids["cotizacion"])
        )
        cotizacion = database.session.get(SupplierQuotation, ids["cotizacion"])
        if cotizacion is not None:
            database.session.delete(cotizacion)
        proveedor = database.session.get(Party, ids["proveedor"])
        if proveedor is not None:
            database.session.delete(proveedor)
        database.session.commit()


def _datos_cotizacion(ids, landed_cost: str | None = None) -> dict:
    """Formulario de edición de la cotización con los landed costs indicados."""
    datos = {
        "supplier_id": ids["proveedor"],
        "company": "cacao",
        "posting_date": "2026-05-15",
        "remarks": "Edición con landed costs",
        "item_code_0": "ART01",
        "item_name_0": "Articulo Comercial",
        "qty_0": "2",
        "uom_0": "UND",
        "rate_0": "3",
        "amount_0": "6",
    }
    if landed_cost is not None:
        datos["landed_cost_estimates_json"] = landed_cost
    return datos


def _ultimo_cambio_cotizacion(app, cotizacion_id):
    """Devuelve la última entrada de auditoría de actualización de la cotización."""
    with app.app_context():
        entrada = database.session.execute(
            database.select(AuditTrail)
            .filter_by(document_type="supplier_quotation", document_id=cotizacion_id, action="updated")
            .order_by(AuditTrail.timestamp.desc(), AuditTrail.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        assert entrada is not None, "La edición no registró una entrada de auditoría."
        return (
            json.loads(entrada.changes_json),
            json.loads(entrada.before_json),
            json.loads(entrada.after_json),
        )


def test_edicion_cotizacion_registra_landed_costs_en_auditoria(app, authenticated_client, cotizacion_con_landed_cost):
    """El cambio de landed_cost_estimates_json queda registrado con antes y después."""
    ids = cotizacion_con_landed_cost
    nuevo = json.dumps([{"concept": "Flete editado", "amount": "15"}], ensure_ascii=False, separators=(",", ":"))

    respuesta = authenticated_client("admin").post(
        f"/buying/supplier-quotation/{ids['cotizacion']}/edit",
        data=_datos_cotizacion(ids, nuevo),
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    cambios, antes, despues = _ultimo_cambio_cotizacion(app, ids["cotizacion"])
    assert cambios["landed_cost_estimates_json"]["before"] == ids["inicial"]
    assert cambios["landed_cost_estimates_json"]["after"] == nuevo
    assert antes["landed_cost_estimates_json"] == ids["inicial"]
    assert despues["landed_cost_estimates_json"] == nuevo


def test_edicion_cotizacion_rechaza_landed_cost_invalido_sin_nueva_auditoria(
    app, authenticated_client, cotizacion_con_landed_cost
):
    """Un JSON inválido se rechaza sin mutar el documento ni generar auditoría."""
    ids = cotizacion_con_landed_cost
    with app.app_context():
        total_antes = database.session.execute(
            database.select(database.func.count())
            .select_from(AuditTrail)
            .where(
                AuditTrail.document_type == "supplier_quotation",
                AuditTrail.document_id == ids["cotizacion"],
                AuditTrail.action == "updated",
            )
        ).scalar_one()

    respuesta = authenticated_client("admin").post(
        f"/buying/supplier-quotation/{ids['cotizacion']}/edit",
        data=_datos_cotizacion(ids, "{no es json"),
        follow_redirects=True,
    )

    assert respuesta.status_code == 200
    assert "landed costs estimados deben ser un JSON válido" in respuesta.get_data(as_text=True)
    with app.app_context():
        cotizacion = database.session.get(SupplierQuotation, ids["cotizacion"])
        assert cotizacion.landed_cost_estimates_json == ids["inicial"]
        total_despues = database.session.execute(
            database.select(database.func.count())
            .select_from(AuditTrail)
            .where(
                AuditTrail.document_type == "supplier_quotation",
                AuditTrail.document_id == ids["cotizacion"],
                AuditTrail.action == "updated",
            )
        ).scalar_one()
        assert total_despues == total_antes
