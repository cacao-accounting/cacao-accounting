# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2107: el precio de catálogo se convierte a la moneda del documento antes de usarse."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from cacao_accounting.database import (
    CompanyParty,
    Currency,
    Item,
    ItemPrice,
    Party,
    PriceList,
    SalesRequest,
    User,
    database,
)
from cacao_accounting.document_identifiers import ensure_default_naming_series_for_company
from cacao_accounting.ventas import services as sales_services
from cacao_accounting.ventas.services import resolve_sales_catalog_price

FECHA = date(2026, 5, 15)
SIN_TASA = date(2026, 4, 30)
URL_API = "/api/sales/catalog-price"


def _sembrar_lista(entorno, *, currency: str | None) -> tuple[str, str]:
    """Crea la lista de venta por defecto con un precio de 100 en la moneda indicada."""
    sufijo = uuid4().hex[:8]
    with entorno.app.app_context():
        cliente = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
        item = database.session.execute(database.select(Item).filter_by(code="ART01")).scalar_one()
        lista = PriceList(
            name=f"Lista {sufijo}",
            company="cacao",
            currency=currency,
            is_selling=True,
            is_buying=False,
            is_default=True,
            is_active=True,
        )
        database.session.add(lista)
        database.session.flush()
        database.session.add(
            ItemPrice(
                item_code=item.code,
                price_list_id=lista.id,
                uom="UND",
                price=Decimal("100"),
            )
        )
        vinculo = database.session.execute(
            database.select(CompanyParty).filter_by(company="cacao", party_id=cliente.id)
        ).scalar_one()
        vinculo.default_price_list_id = lista.id
        database.session.commit()
        return cliente.id, item.code


def _cliente_http(application):
    """Devuelve un cliente autenticado para la app aislada del escenario."""
    with application.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        user_id = str(admin.id)
        auth_version = admin.auth_version
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True
    return client


def _consulta_api(customer_id: str, item_code: str, currency: str, posting_date: date) -> dict[str, str]:
    """Construye la consulta de precio de catálogo para la moneda y fecha indicadas."""
    return {
        "company": "cacao",
        "customer_id": customer_id,
        "item_code": item_code,
        "uom": "UND",
        "qty": "1",
        "currency": currency,
        "posting_date": posting_date.isoformat(),
    }


def test_resolver_convierte_con_tasa_historica_y_respeta_misma_moneda(entorno_contable_aislado):
    """La lista USD se convierte a NIO con la tasa vigente y sin conversión si coincide."""
    customer_id, item_code = _sembrar_lista(entorno_contable_aislado, currency="USD")
    with entorno_contable_aislado.app.app_context():
        convertido = resolve_sales_catalog_price("cacao", customer_id, item_code, Decimal("1"), "UND", FECHA, "NIO")
        directo = resolve_sales_catalog_price("cacao", customer_id, item_code, Decimal("1"), "UND", FECHA, "USD")

    assert convertido is not None
    assert convertido.price == Decimal("3650.0000")
    assert convertido.price_list_currency == "USD"
    assert convertido.transaction_currency == "NIO"
    assert convertido.exchange_rate == Decimal("36.50")
    assert directo is not None
    assert directo.price == Decimal("100.0000")
    assert directo.exchange_rate == Decimal("1")


def test_api_expone_precio_convertido_y_referencia_monetaria(entorno_contable_aislado):
    """La API devuelve el precio en la moneda pedida y la tasa utilizada."""
    customer_id, item_code = _sembrar_lista(entorno_contable_aislado, currency="USD")
    cliente = _cliente_http(entorno_contable_aislado.app)

    respuesta = cliente.get(URL_API, query_string=_consulta_api(customer_id, item_code, "NIO", FECHA))
    datos = respuesta.get_json()

    assert respuesta.status_code == 200
    assert datos["price"] == "3650.0000"
    assert datos["price_list_currency"] == "USD"
    assert datos["transaction_currency"] == "NIO"
    assert Decimal(datos["exchange_rate"]) == Decimal("36.50")


def test_api_bloquea_sin_moneda_transaccional(entorno_contable_aislado):
    """Una consulta sin moneda no puede caer en un precio sin convertir."""
    customer_id, item_code = _sembrar_lista(entorno_contable_aislado, currency="USD")
    consulta = _consulta_api(customer_id, item_code, "NIO", FECHA)
    consulta.pop("currency")
    cliente = _cliente_http(entorno_contable_aislado.app)

    respuesta = cliente.get(URL_API, query_string=consulta)

    assert respuesta.status_code == 400


def test_api_bloquea_sin_tasa_para_la_fecha(entorno_contable_aislado):
    """Sin tasa histórica se devuelve error, nunca el importe origen etiquetado como NIO."""
    customer_id, item_code = _sembrar_lista(entorno_contable_aislado, currency="USD")
    cliente = _cliente_http(entorno_contable_aislado.app)

    respuesta = cliente.get(URL_API, query_string=_consulta_api(customer_id, item_code, "NIO", SIN_TASA))

    assert respuesta.status_code == 400
    assert "No existe tipo de cambio" in respuesta.get_json()["error"]


def test_api_bloquea_lista_sin_moneda(entorno_contable_aislado):
    """Una lista sin moneda no se usa ni se infiere desde la compañía."""
    customer_id, item_code = _sembrar_lista(entorno_contable_aislado, currency=None)
    cliente = _cliente_http(entorno_contable_aislado.app)

    respuesta = cliente.get(URL_API, query_string=_consulta_api(customer_id, item_code, "NIO", FECHA))

    assert respuesta.status_code == 400
    assert "no tiene moneda configurada" in respuesta.get_json()["error"]


def test_guardado_rechaza_precio_origin_y_acepta_conversion(entorno_contable_aislado, monkeypatch):
    """El guardado usa la misma conversión que la API antes de persistir la línea."""
    customer_id, _item_code = _sembrar_lista(entorno_contable_aislado, currency="USD")
    application = entorno_contable_aislado.app
    with application.app_context():
        ensure_default_naming_series_for_company("cacao", ["sales_request"])
    monkeypatch.setattr(sales_services, "is_sales_price_editor", lambda *_args, **_kwargs: False)
    cliente = _cliente_http(application)
    datos = {
        "company": "cacao",
        "currency": "NIO",
        "posting_date": FECHA.isoformat(),
        "customer_id": customer_id,
        "item_code_0": "ART01",
        "item_name_0": "Linea de prueba",
        "qty_0": "1",
        "rate_0": "100",
        "uom_0": "UND",
    }

    rechazado = cliente.post("/sales/sales-request/new", data=datos)

    assert rechazado.status_code == 200
    assert "puede modificar un precio de venta" in rechazado.get_data(as_text=True)
    with application.app_context():
        assert database.session.execute(database.select(SalesRequest)).scalars().all() == []

    datos["rate_0"] = "3650"
    aceptado = cliente.post("/sales/sales-request/new", data=datos)

    assert aceptado.status_code == 302
    with application.app_context():
        assert len(database.session.execute(database.select(SalesRequest)).scalars().all()) == 1


def test_guardado_bloquea_precio_de_lista_sin_tasa_vigente(entorno_contable_aislado, monkeypatch):
    """El formulario no persiste un precio origen cuando falta conversión histórica."""
    application = entorno_contable_aislado.app
    with application.app_context():
        if database.session.get(Currency, "EUR") is None:
            database.session.add(Currency(code="EUR", name="Euro", decimals=2, active=True, default=False))
            database.session.commit()
    customer_id, _item_code = _sembrar_lista(entorno_contable_aislado, currency="EUR")
    with application.app_context():
        ensure_default_naming_series_for_company("cacao", ["sales_request"])
    monkeypatch.setattr(sales_services, "is_sales_price_editor", lambda *_args, **_kwargs: False)
    client = _cliente_http(application)

    response = client.post(
        "/sales/sales-request/new",
        data={
            "company": "cacao",
            "currency": "NIO",
            "posting_date": FECHA.isoformat(),
            "customer_id": customer_id,
            "item_code_0": "ART01",
            "item_name_0": "Linea sin tasa",
            "qty_0": "1",
            "rate_0": "100",
            "uom_0": "UND",
        },
    )

    assert response.status_code == 200
    assert "No existe tipo de cambio" in response.get_data(as_text=True)
    with application.app_context():
        assert database.session.execute(database.select(SalesRequest)).scalars().all() == []
