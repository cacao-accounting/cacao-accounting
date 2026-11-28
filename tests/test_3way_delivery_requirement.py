# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1813: la modalidad 3-way exige orden y nota de entrega."""

from datetime import date

import pytest

from cacao_accounting.database import (
    DeliveryNote,
    SalesInvoice,
    SalesMatchingConfig,
    SalesOrder,
    database,
)
from cacao_accounting.ventas.services import _validate_sales_order_requirement

FECHA = date(2026, 5, 15)


def _config(matching_type: str, require_sales_order: bool) -> SalesMatchingConfig:
    """Crea o actualiza la configuración de matching de la compañía."""
    config = database.session.execute(database.select(SalesMatchingConfig).filter_by(company="cacao")).scalar_one_or_none()
    if config is None:
        config = SalesMatchingConfig(company="cacao")
        database.session.add(config)
    config.matching_type = matching_type
    config.require_sales_order = require_sales_order
    database.session.flush()
    return config


def _crear_factura(order_id: str | None, document_no: str, delivery_id: str | None = None) -> SalesInvoice:
    """Crea una factura de venta en borrador con los vínculos indicados."""
    invoice = SalesInvoice(
        company="cacao",
        posting_date=FECHA,
        docstatus=0,
        document_no=document_no,
        customer_name="Cliente 1813",
        sales_order_id=order_id,
        delivery_note_id=delivery_id,
    )
    database.session.add(invoice)
    database.session.flush()
    return invoice


def _orden(document_no: str) -> SalesOrder:
    """Crea una orden de venta aprobada."""
    orden = SalesOrder(
        company="cacao",
        posting_date=FECHA,
        docstatus=1,
        document_no=document_no,
        customer_name="Cliente 1813",
    )
    database.session.add(orden)
    database.session.flush()
    return orden


def _entrega(document_no: str, order_id: str | None) -> DeliveryNote:
    """Crea una nota de entrega aprobada, opcionalmente ligada a una orden."""
    entrega = DeliveryNote(
        company="cacao",
        posting_date=FECHA,
        docstatus=1,
        document_no=document_no,
        customer_name="Cliente 1813",
        sales_order_id=order_id,
    )
    database.session.add(entrega)
    database.session.flush()
    return entrega


def test_2way_conserva_semantica_sin_delivery(entorno_contable_aislado):
    """Modalidad 2-way sin Nota de Entrega no exige el vínculo (#1813)."""
    with entorno_contable_aislado.app.app_context():
        _config("2-way", require_sales_order=True)
        order = _orden("SO-1813-2W")
        invoice = _crear_factura(order.id, "SI-1813-2W")
        database.session.commit()

        _validate_sales_order_requirement(invoice)


def test_2way_sin_flag_permite_factura_sin_vinculos(entorno_contable_aislado):
    """2-way con require_sales_order apagado no impone vínculos."""
    with entorno_contable_aislado.app.app_context():
        _config("2-way", require_sales_order=False)
        invoice = _crear_factura(None, "SI-1813-2W-OFF")
        database.session.commit()

        _validate_sales_order_requirement(invoice)


def test_3way_exige_nota_de_entrega(entorno_contable_aislado):
    """Modalidad 3-way exige la Nota de Entrega antes de aprobar (#1813)."""
    with entorno_contable_aislado.app.app_context():
        _config("3-way", require_sales_order=True)
        order = _orden("SO-1813-3W")
        invoice = _crear_factura(order.id, "SI-1813-3W")
        database.session.commit()

        with pytest.raises(ValueError, match="Nota de Entrega"):
            _validate_sales_order_requirement(invoice)


def test_3way_exige_ambos_vinculos_con_flag_apagado(entorno_contable_aislado):
    """3-way no depende de require_sales_order: exige orden y entrega."""
    with entorno_contable_aislado.app.app_context():
        _config("3-way", require_sales_order=False)
        invoice = _crear_factura(None, "SI-1813-3W-OFF")
        database.session.commit()

        with pytest.raises(ValueError, match="Orden de Venta y una Nota de Entrega"):
            _validate_sales_order_requirement(invoice)


def test_3way_rechaza_entrega_sin_orden(entorno_contable_aislado):
    """Una Nota de Entrega sin Orden de Venta no satisface 3-way."""
    with entorno_contable_aislado.app.app_context():
        _config("3-way", require_sales_order=False)
        delivery = _entrega("DN-1813-SIN-OV", None)
        invoice = _crear_factura(None, "SI-1813-DN-SIN-OV", delivery.id)
        database.session.commit()

        with pytest.raises(ValueError, match="Orden de Venta"):
            _validate_sales_order_requirement(invoice)


def test_3way_rechaza_orden_derivada_no_aprobada(entorno_contable_aislado):
    """La orden referida por la entrega debe seguir aprobada y ser compatible."""
    with entorno_contable_aislado.app.app_context():
        _config("3-way", require_sales_order=False)
        order = _orden("SO-1813-DERIVADA")
        order.docstatus = 0
        delivery = _entrega("DN-1813-DERIVADA", order.id)
        invoice = _crear_factura(None, "SI-1813-DERIVADA", delivery.id)
        database.session.commit()

        with pytest.raises(ValueError, match="debe estar aprobado"):
            _validate_sales_order_requirement(invoice)


def test_3way_acepta_entrega_ligada_a_orden(entorno_contable_aislado):
    """La entrega que pertenece a la orden satisface ambos vínculos."""
    with entorno_contable_aislado.app.app_context():
        _config("3-way", require_sales_order=False)
        order = _orden("SO-1813-3W-OK")
        delivery = _entrega("DN-1813-3W-OK", order.id)
        invoice = _crear_factura(order.id, "SI-1813-3W-OK", delivery.id)
        database.session.commit()

        _validate_sales_order_requirement(invoice)
