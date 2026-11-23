# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2095: los formularios de compras rechazan decimales inválidos."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from cacao_accounting.compras import routes as compras_routes
from cacao_accounting.compras import services as compras_services
from cacao_accounting.compras.services import _form_decimal
from cacao_accounting.database import (
    Party,
    PurchaseRequest,
    PurchaseRequestItem,
    SupplierQuotation,
    SupplierQuotationItem,
    database,
)

DECIMALES_INVALIDOS = [
    ("qty_0", "abc", "válido"),
    ("qty_0", "NaN", "finito"),
    ("qty_0", "sNaN", "finito"),
    ("qty_0", "Infinity", "finito"),
    ("qty_0", "-Infinity", "finito"),
    ("rate_0", "abc", "válido"),
    ("rate_0", "NaN", "finito"),
    ("rate_0", "Infinity", "finito"),
]


@pytest.mark.parametrize(("campo", "valor", "mensaje"), DECIMALES_INVALIDOS)
def test_decimal_invalido_se_convierte_en_validacion(app, campo, valor, mensaje):
    """Sintaxis inválida o valores no finitos no escapan como InvalidOperation."""
    with app.test_request_context("/", method="POST", data={campo: valor}):
        with pytest.raises(ValueError, match=mensaje):
            _form_decimal(campo)


@pytest.mark.parametrize(
    ("valor", "mensaje"),
    [
        ("abc", "El campo qty_0 debe ser un número válido."),
        ("NaN", "El campo qty_0 debe ser un número finito."),
    ],
)
def test_mensaje_de_validacion_usa_catalogo_traducido(app, valor, mensaje):
    """Los mensajes reutilizan entradas ya presentes en el catálogo inglés."""
    with app.test_request_context("/", method="POST", data={"qty_0": valor}):
        with pytest.raises(ValueError) as error:
            _form_decimal("qty_0")
    assert str(error.value) == mensaje


def test_decimal_valido_se_conserva(app):
    with app.test_request_context("/", method="POST", data={"qty_0": "12.5"}):
        assert _form_decimal("qty_0") == Decimal("12.5")


def _supplier_id(app) -> str:
    """Obtiene el tercero sembrado dentro de un contexto fresco."""
    with app.app_context():
        return str(database.session.execute(database.select(Party.id).filter_by(code="PRV001")).scalar_one())


def _sin_identificador(monkeypatch):
    """Aísla la validación decimal del experimento de numeración."""
    monkeypatch.setattr(compras_routes, "assign_document_identifier", lambda **kwargs: None)
    monkeypatch.setattr(compras_services, "assign_document_identifier", lambda **kwargs: None)


def _datos_linea(remarks: str, campo: str, valor: str, supplier_id: str) -> dict:
    return {
        "company": "cacao",
        "transaction_currency": "NIO",
        "posting_date": "2026-05-15",
        "remarks": remarks,
        "supplier_id": supplier_id,
        "item_code_0": "ART01",
        "item_name_0": "Articulo Comercial",
        "uom_0": "UND",
        campo: valor,
    }


@pytest.mark.parametrize(("campo", "valor", "mensaje"), [caso for caso in DECIMALES_INVALIDOS if caso[0] == "qty_0"])
def test_alta_solicitud_rechaza_decimal_invalido(
    app, entorno_contable, authenticated_client, monkeypatch, campo, valor, mensaje
):
    """El POST real no persiste la solicitud ni deja escapar la excepción."""
    _sin_identificador(monkeypatch)
    marcadir = f"DEC-SOL-{uuid4().hex[:8]}"
    respuesta = authenticated_client().post(
        "/buying/purchase-request/new",
        data=_datos_linea(marcadir, campo, valor, _supplier_id(app)),
    )

    assert respuesta.status_code == 200
    assert mensaje in respuesta.get_data(as_text=True)
    with app.app_context():
        assert (
            database.session.execute(database.select(PurchaseRequest.id).filter_by(remarks=marcadir)).scalar_one_or_none()
            is None
        )


def test_alta_solicitud_con_hueco_guarda_linea_posterior(app, authenticated_client):
    """Una fila inicial vacía no hace que la solicitud se persista sin su artículo."""
    marker = f"GAP-PR-{uuid4().hex[:8]}"
    form = {
        "company": "cacao",
        "transaction_currency": "NIO",
        "posting_date": "2026-05-15",
        "remarks": marker,
        "item_code_0": "",
        "item_code_1": "ART01",
        "item_name_1": "Articulo Comercial",
        "qty_1": "2",
        "uom_1": "UND",
    }

    response = authenticated_client().post("/buying/purchase-request/new", data=form)

    assert response.status_code == 302
    with app.app_context():
        request_record = database.session.execute(database.select(PurchaseRequest).filter_by(remarks=marker)).scalar_one()
        items = (
            database.session.execute(database.select(PurchaseRequestItem).filter_by(purchase_request_id=request_record.id))
            .scalars()
            .all()
        )
        assert len(items) == 1
        assert items[0].item_code == "ART01"
        assert items[0].qty == Decimal("2.0000")


@pytest.mark.parametrize(("campo", "valor", "mensaje"), DECIMALES_INVALIDOS)
def test_alta_cotizacion_rechaza_decimal_invalido(
    app, entorno_contable, authenticated_client, monkeypatch, campo, valor, mensaje
):
    """El POST real no persiste la cotización ni deja escapar la excepción."""
    _sin_identificador(monkeypatch)
    marcadir = f"DEC-COT-{uuid4().hex[:8]}"
    respuesta = authenticated_client().post(
        "/buying/supplier-quotation/new",
        data=_datos_linea(marcadir, campo, valor, _supplier_id(app)),
    )

    assert respuesta.status_code == 200
    assert mensaje in respuesta.get_data(as_text=True)
    with app.app_context():
        assert (
            database.session.execute(database.select(SupplierQuotation.id).filter_by(remarks=marcadir)).scalar_one_or_none()
            is None
        )


def _solicitud_inicial(app) -> tuple[str, str]:
    sufijo = uuid4().hex[:8]
    with app.app_context():
        solicitud = PurchaseRequest(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=0,
            document_no=f"DEC-PR-{sufijo}",
            remarks=f"DEC-PR-{sufijo}",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
        )
        database.session.add(solicitud)
        database.session.flush()
        database.session.add(
            PurchaseRequestItem(
                purchase_request_id=solicitud.id,
                item_code="ART01",
                qty=Decimal("2"),
                qty_in_base_uom=Decimal("2"),
                uom="UND",
                rate=Decimal("0"),
                amount=Decimal("0"),
            )
        )
        database.session.commit()
        return str(solicitud.id), sufijo


def test_edicion_solicitud_conserva_lineas_con_decimal_invalido(app, entorno_contable, authenticated_client):
    """Una edición inválida revierte el borrado previo de líneas."""
    solicitud_id, _sufijo = _solicitud_inicial(app)
    respuesta = authenticated_client().post(
        f"/buying/purchase-request/{solicitud_id}/edit",
        data=_datos_linea("edición inválida", "qty_0", "NaN", _supplier_id(app)),
    )

    assert respuesta.status_code == 200
    assert "finito" in respuesta.get_data(as_text=True)
    with app.app_context():
        lineas = database.session.execute(
            database.select(PurchaseRequestItem.qty, PurchaseRequestItem.uom).filter_by(purchase_request_id=solicitud_id)
        ).all()
        assert lineas == [(Decimal("2"), "UND")]


def _cotizacion_inicial(app, supplier_id: str) -> tuple[str, str]:
    sufijo = uuid4().hex[:8]
    with app.app_context():
        cotizacion = SupplierQuotation(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=0,
            document_no=f"DEC-SQ-{sufijo}",
            remarks=f"DEC-SQ-{sufijo}",
            supplier_id=supplier_id,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
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
        return str(cotizacion.id), sufijo


def test_edicion_cotizacion_conserva_lineas_con_decimal_invalido(app, entorno_contable, authenticated_client):
    """La edición de cotizaciones tampoco propaga ValueError."""
    cotizacion_id, _sufijo = _cotizacion_inicial(app, _supplier_id(app))
    respuesta = authenticated_client().post(
        f"/buying/supplier-quotation/{cotizacion_id}/edit",
        data=_datos_linea("edición inválida", "rate_0", "Infinity", _supplier_id(app)),
    )

    assert respuesta.status_code == 200
    assert "finito" in respuesta.get_data(as_text=True)
    with app.app_context():
        lineas = database.session.execute(
            database.select(SupplierQuotationItem.qty, SupplierQuotationItem.rate, SupplierQuotationItem.amount).filter_by(
                supplier_quotation_id=cotizacion_id
            )
        ).all()
        assert lineas == [(Decimal("2"), Decimal("3"), Decimal("6"))]
