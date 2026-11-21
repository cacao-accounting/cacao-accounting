# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1813: la modalidad 3-way exige la nota de entrega."""

import pytest
from datetime import date

from cacao_accounting.database import SalesInvoice, SalesMatchingConfig, SalesOrder, database
from cacao_accounting.ventas.services import _validate_sales_order_requirement


FECHA = date(2026, 5, 15)


def _crear_factura(order_id: str, document_no: str) -> SalesInvoice:
    """Crea una factura de venta en borrador vinculada a la orden."""
    invoice = SalesInvoice(
        company="cacao",
        posting_date=FECHA,
        docstatus=0,
        document_no=document_no,
        customer_name="Cliente 1813",
        sales_order_id=order_id,
    )
    database.session.add(invoice)
    database.session.flush()
    return invoice


def test_2way_conserva_semantica_sin_delivery(app):
    """Modalidad 2-way sin Nota de Entrega no exige el vínculo (#1813)."""
    with app.app_context():
        database.session.add(SalesMatchingConfig(company="cacao", matching_type="2-way", require_sales_order=True))
        database.session.flush()
        order = SalesOrder(
            company="cacao", posting_date=FECHA, docstatus=1, document_no="SO-1813-2W", customer_name="Cliente 1813"
        )
        database.session.add(order)
        database.session.flush()
        invoice = _crear_factura(order.id, "SI-1813-2W")
        database.session.commit()

        _validate_sales_order_requirement(invoice)


def test_3way_exige_nota_de_entrega(app):
    """Modalidad 3-way exige la Nota de Entrega antes de aprobar (#1813)."""
    with app.app_context():
        config = database.session.execute(database.select(SalesMatchingConfig).filter_by(company="cacao")).scalar_one()
        config.matching_type = "3-way"
        database.session.flush()
        order = SalesOrder(
            company="cacao", posting_date=FECHA, docstatus=1, document_no="SO-1813-3W", customer_name="Cliente 1813"
        )
        database.session.add(order)
        database.session.flush()
        invoice = _crear_factura(order.id, "SI-1813-3W")
        database.session.commit()

        with pytest.raises(ValueError, match="Nota de Entrega"):
            _validate_sales_order_requirement(invoice)
