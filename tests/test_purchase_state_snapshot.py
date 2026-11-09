# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""El snapshot de compras cubre los campos que la edición muta.

Escenario de negocio (issue #2137): ``_capture_purchase_state`` solo incluía
cinco campos de cabecera. Cambios de número de factura del proveedor,
plantilla fiscal, moneda/tasa, logística y vínculos de origen no aparecían en
``AuditTrail.changes_json``.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from cacao_accounting.audit_trail_service import log_update
from cacao_accounting.compras.services import _capture_purchase_state
from cacao_accounting.database import (
    AuditTrail,
    PurchaseInvoice,
    PurchaseOrder,
    database,
)

FECHA = date(2026, 10, 15)


def test_la_factura_incluye_numero_y_plantilla_fiscal(app):
    """Los campos mutables por la edición de factura llegan al snapshot."""
    with app.app_context():
        factura = PurchaseInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            supplier_invoice_no="FAC-PROV-1",
            tax_template_id="TAX-1",
            transaction_currency="NIO",
            exchange_rate=Decimal("1.0000"),
            total=Decimal("100.00"),
        )
        estado = _capture_purchase_state(factura)

        assert estado["supplier_invoice_no"] == "FAC-PROV-1"
        assert estado["tax_template_id"] == "TAX-1"
        assert estado["transaction_currency"] == "NIO"
        assert estado["exchange_rate"] == "1.0000"
        assert estado["posting_date"] == "2026-10-15"


def test_la_orden_incluye_logistica_y_origen(app):
    """Moneda, logística y vínculo de origen se auditan."""
    with app.app_context():
        orden = PurchaseOrder(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            transaction_currency="USD",
            exchange_rate=Decimal("36.5000"),
            incoterm_code="FOB",
            incoterm_version="2020",
            delivery_date=FECHA,
            delivery_place="Managua",
            purchase_terms="Crédito 30 días",
            purchase_award_id="AWARD-1",
        )
        estado = _capture_purchase_state(orden)

        assert estado["transaction_currency"] == "USD"
        assert estado["incoterm_code"] == "FOB"
        assert estado["delivery_date"] == "2026-10-15"
        assert estado["delivery_place"] == "Managua"
        assert estado["purchase_terms"] == "Crédito 30 días"
        assert estado["purchase_award_id"] == "AWARD-1"


def test_el_cambio_de_numero_aparece_en_changes_json(app):
    """log_update detecta el cambio de supplier_invoice_no."""
    with app.app_context():
        factura = PurchaseInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            supplier_invoice_no="FAC-ANTES",
            transaction_currency="NIO",
        )
        database.session.add(factura)
        database.session.commit()

        antes = _capture_purchase_state(factura)
        factura.supplier_invoice_no = "FAC-DESPUES"
        despues = _capture_purchase_state(factura)
        log_update(factura, before=antes, after=despues)
        database.session.commit()

        entrada = (
            database.session.execute(database.select(AuditTrail).filter_by(document_id=factura.id, action="updated"))
            .scalars()
            .first()
        )

        assert entrada is not None
        cambios = json.loads(entrada.changes_json)
        assert cambios["supplier_invoice_no"] == {"before": "FAC-ANTES", "after": "FAC-DESPUES"}
