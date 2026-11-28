# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La solicitud de cotización solo acepta terceros proveedores.

Escenario de negocio (issue #2136): el alta y la edición manual guardaban el
nombre de cualquier ``supplier_id`` enviado, sin comprobar ``is_supplier``.
La RFQ interna puede no llevar proveedor, pero un ID informado debe tener el
rol correcto.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from flask import get_flashed_messages
from flask_login import login_user

from cacao_accounting.compras.services import (
    _create_purchase_quotation_from_request,
    _handle_purchase_quotation_edit_post,
)
from cacao_accounting.database import (
    CompanyParty,
    DocumentRelation,
    Party,
    PurchaseQuotation,
    PurchaseQuotationItem,
    PurchaseRequest,
    PurchaseRequestItem,
    User,
    database,
)

FECHA = date(2026, 5, 15)


def _formulario(supplier_id: str | None, *, version: int | None = None) -> dict[str, str]:
    """Datos mínimos que el formulario transaccional envía al alta y edición."""
    datos = {
        "company": "cacao",
        "currency": "NIO",
        "posting_date": FECHA.isoformat(),
        "item_code_0": "ART01",
        "item_name_0": "Articulo Comercial",
        "qty_0": "1",
        "uom_0": "UND",
    }
    if supplier_id:
        datos["supplier_id"] = supplier_id
    if version is not None:
        datos["version"] = str(version)
    return datos


def _tercero(app, *, is_supplier: bool, activo: bool = True, miembro: bool = True) -> str:
    """Crea un tercero con el rol, vigencia y vínculo indicados."""
    suffix = uuid4().hex[:8]
    with app.app_context():
        party = Party(
            code=f"RFQ-{suffix}",
            name=f"Tercero {suffix}",
            is_supplier=is_supplier,
            is_customer=not is_supplier,
            is_active=activo,
        )
        database.session.add(party)
        database.session.flush()
        if is_supplier and miembro:
            database.session.add(CompanyParty(company="cacao", party_id=party.id, is_active=True))
        database.session.commit()
        return str(party.id)


def _invocar_alta(app, supplier_id: str | None):
    """Ejecuta el handler de alta con la identidad del administrador."""
    with app.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        with app.test_request_context("/", method="POST", data=_formulario(supplier_id)):
            login_user(admin)
            return _create_purchase_quotation_from_request()


def test_el_alta_rechaza_un_cliente_como_proveedor(app, entorno_contable):
    """Un Party sin rol proveedor no se persiste."""
    cliente_id = _tercero(app, is_supplier=False)
    with app.app_context():
        antes = database.session.execute(database.select(PurchaseQuotation)).scalars().all()

    assert _invocar_alta(app, cliente_id) is None

    with app.app_context():
        despues = database.session.execute(database.select(PurchaseQuotation)).scalars().all()
        assert len(despues) == len(antes)


def test_el_alta_rechaza_un_proveedor_inexistente(app, entorno_contable):
    """Un ID que no existe tampoco crea la solicitud ni deja mutaciones."""
    with app.app_context():
        antes = database.session.execute(database.select(PurchaseQuotation)).scalars().all()

    assert _invocar_alta(app, "NO-EXISTE") is None

    with app.app_context():
        despues = database.session.execute(database.select(PurchaseQuotation)).scalars().all()
        assert len(despues) == len(antes)


def test_el_alta_acepta_proveedor_y_solicitud_sin_proveedor(app, entorno_contable):
    """El control positivo conserva ambos caminos válidos."""
    proveedor_id = _tercero(app, is_supplier=True)

    assert _invocar_alta(app, proveedor_id) is not None
    assert _invocar_alta(app, None) is not None

    with app.app_context():
        cotizaciones = database.session.execute(database.select(PurchaseQuotation)).scalars().all()
        assert {cotizacion.supplier_id for cotizacion in cotizaciones} == {proveedor_id, None}


def test_la_edicion_no_muta_la_cabecera_con_un_cliente(app, entorno_contable):
    """La edición rechaza el cambio y conserva el proveedor original."""
    proveedor_id = _tercero(app, is_supplier=True)
    cliente_id = _tercero(app, is_supplier=False)
    with app.app_context():
        cotizacion = PurchaseQuotation(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            supplier_id=proveedor_id,
            supplier_name="Proveedor original",
            transaction_currency="NIO",
        )
        database.session.add(cotizacion)
        database.session.commit()
        cotizacion_id = cotizacion.id
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        with app.test_request_context("/", method="POST", data=_formulario(cliente_id, version=cotizacion.version)):
            login_user(admin)
            respuesta = _handle_purchase_quotation_edit_post(cotizacion)

        assert respuesta is not None
        registro = database.session.execute(database.select(PurchaseQuotation).filter_by(id=cotizacion_id)).scalar_one()
        assert registro.supplier_id == proveedor_id
        assert registro.supplier_name == "Proveedor original"


_CAMPOS_CABECERA_RFQ = (
    "id",
    "document_no",
    "company",
    "posting_date",
    "docstatus",
    "supplier_id",
    "supplier_name",
    "remarks",
    "transaction_currency",
    "base_currency",
    "exchange_rate",
    "total",
    "base_total",
    "grand_total",
)
_CAMPOS_LINEA_RFQ = (
    "id",
    "item_code",
    "item_name",
    "description",
    "qty",
    "qty_in_base_uom",
    "uom",
    "rate",
    "amount",
    "base_rate",
    "base_amount",
)
_CAMPOS_RELACION_RFQ = (
    "id",
    "source_type",
    "source_id",
    "source_item_id",
    "target_type",
    "target_id",
    "target_item_id",
    "company",
    "qty",
    "qty_in_base_uom",
    "uom",
    "rate",
    "amount",
    "relation_type",
    "revision",
    "status",
    "reversed_at",
    "reversed_by",
    "reversal_reason",
)


def _sembrar_rfq_vinculada(app, supplier_id: str) -> str:
    """Crea una RFQ borrador con solicitud origen, línea y relación activa."""
    sufijo = uuid4().hex[:8]
    with app.app_context():
        solicitud = PurchaseRequest(
            company="cacao",
            posting_date=FECHA,
            document_no=f"REQ-1947-{sufijo}",
            remarks="Solicitud origen",
            docstatus=1,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            total=Decimal("20"),
            base_total=Decimal("20"),
            grand_total=Decimal("20"),
        )
        database.session.add(solicitud)
        database.session.flush()
        solicitud_linea = PurchaseRequestItem(
            purchase_request_id=solicitud.id,
            item_code="ART01",
            item_name="Artículo origen",
            qty=Decimal("2"),
            qty_in_base_uom=Decimal("2"),
            uom="UND",
            rate=Decimal("10"),
            amount=Decimal("20"),
        )
        cotizacion = PurchaseQuotation(
            company="cacao",
            posting_date=FECHA,
            document_no=f"RFQ-1947-{sufijo}",
            remarks="Borrador original",
            docstatus=0,
            supplier_id=supplier_id,
            supplier_name="Proveedor original",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            total=Decimal("20"),
            base_total=Decimal("20"),
            grand_total=Decimal("20"),
        )
        database.session.add_all([solicitud_linea, cotizacion])
        database.session.flush()
        cotizacion_linea = PurchaseQuotationItem(
            purchase_quotation_id=cotizacion.id,
            item_code="ART01",
            item_name="Artículo original",
            description="Especificación original",
            qty=Decimal("2"),
            qty_in_base_uom=Decimal("2"),
            uom="UND",
            rate=Decimal("10"),
            amount=Decimal("20"),
            base_rate=Decimal("10"),
            base_amount=Decimal("20"),
        )
        database.session.add(cotizacion_linea)
        database.session.flush()
        database.session.add(
            DocumentRelation(
                source_type="purchase_request",
                source_id=solicitud.id,
                source_item_id=solicitud_linea.id,
                target_type="purchase_quotation",
                target_id=cotizacion.id,
                target_item_id=cotizacion_linea.id,
                company="cacao",
                qty=Decimal("2"),
                qty_in_base_uom=Decimal("2"),
                uom="UND",
                rate=Decimal("10"),
                amount=Decimal("20"),
                relation_type="quotation",
                revision=1,
                status="active",
            )
        )
        database.session.commit()
        return str(cotizacion.id)


def _estado_rfq(quotation_id: str) -> dict[str, object]:
    """Captura cabecera, líneas y relaciones para comparar en sesión fresca."""
    cotizacion = database.session.get(PurchaseQuotation, quotation_id)
    assert cotizacion is not None
    lineas = (
        database.session.execute(
            database.select(PurchaseQuotationItem)
            .filter_by(purchase_quotation_id=quotation_id)
            .order_by(PurchaseQuotationItem.id)
        )
        .scalars()
        .all()
    )
    relaciones = (
        database.session.execute(
            database.select(DocumentRelation)
            .filter_by(target_type="purchase_quotation", target_id=quotation_id)
            .order_by(DocumentRelation.id)
        )
        .scalars()
        .all()
    )
    return {
        "cabecera": {campo: getattr(cotizacion, campo) for campo in _CAMPOS_CABECERA_RFQ},
        "lineas": [{campo: getattr(linea, campo) for campo in _CAMPOS_LINEA_RFQ} for linea in lineas],
        "relaciones": [{campo: getattr(relacion, campo) for campo in _CAMPOS_RELACION_RFQ} for relacion in relaciones],
    }


@pytest.mark.parametrize(
    ("cantidad", "mensaje"),
    [
        (None, "El documento requiere al menos una línea."),
        ("0", "La cantidad del item ART01 debe ser mayor a cero."),
        ("-1", "La cantidad del item ART01 debe ser mayor a cero."),
        ("abc", "El campo qty_0 debe ser un número válido."),
    ],
    ids=["sin_lineas", "cantidad_cero", "cantidad_negativa", "cantidad_no_numerica"],
)
def test_edicion_http_con_linea_invalida_conserva_borrador(app, entorno_contable, authenticated_client, cantidad, mensaje):
    """#1947: el POST real muestra el error y revierte toda la edición vinculada."""
    proveedor_id = _tercero(app, is_supplier=True)
    cotizacion_id = _sembrar_rfq_vinculada(app, proveedor_id)
    with app.app_context():
        estado_antes = _estado_rfq(cotizacion_id)
        version = database.session.get(PurchaseQuotation, cotizacion_id).version

    datos = _formulario(proveedor_id, version=version)
    datos.update({"posting_date": "2026-05-16", "remarks": "Edición inválida"})
    if cantidad is None:
        for campo in ("item_code_0", "item_name_0", "qty_0", "uom_0"):
            datos.pop(campo)
    else:
        datos.update({"item_code_0": "ART01", "item_name_0": "Artículo inválido", "qty_0": cantidad, "rate_0": "1"})

    endpoint = f"/buying/request-for-quotation/{cotizacion_id}/edit"
    respuesta = authenticated_client().post(endpoint, data=datos, follow_redirects=True)

    assert respuesta.status_code == 200
    assert len(respuesta.history) == 1
    assert respuesta.history[0].status_code == 302
    assert respuesta.request.path == f"/buying/request-for-quotation/{cotizacion_id}"
    assert mensaje in respuesta.get_data(as_text=True)
    assert "Solicitud de cotizacion actualizada correctamente." not in respuesta.get_data(as_text=True)
    with app.app_context():
        database.session.remove()
        assert _estado_rfq(cotizacion_id) == estado_antes


@pytest.mark.parametrize(
    ("caso", "mensaje"),
    [
        ("inactivo", "no está habilitado como proveedor"),
        ("sin_vinculo", "no está habilitado para la compañía"),
        ("vinculo_inactivo", "no está habilitado para la compañía"),
    ],
)
def test_alta_rfq_rechaza_proveedor_no_vigente(app, entorno_contable, caso, mensaje):
    """#2319: el proveedor informado debe estar activo y vinculado a la compañía."""
    if caso == "inactivo":
        proveedor_id = _tercero(app, is_supplier=True, activo=False)
    elif caso == "sin_vinculo":
        proveedor_id = _tercero(app, is_supplier=True, miembro=False)
    else:
        proveedor_id = _tercero(app, is_supplier=True)
        with app.app_context():
            vinculo = database.session.execute(
                database.select(CompanyParty).filter_by(party_id=proveedor_id, company="cacao")
            ).scalar_one()
            vinculo.is_active = False
            database.session.commit()
    with app.app_context():
        antes = database.session.execute(database.select(database.func.count()).select_from(PurchaseQuotation)).scalar_one()

    with app.app_context(), app.test_request_context("/", method="POST", data=_formulario(proveedor_id)):
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        login_user(admin)
        assert _create_purchase_quotation_from_request() is None
        assert mensaje in " ".join(str(item) for item in get_flashed_messages())

    with app.app_context():
        despues = database.session.execute(database.select(database.func.count()).select_from(PurchaseQuotation)).scalar_one()
        assert despues == antes


@pytest.mark.parametrize("caso", ["inactivo", "vinculo_inactivo"])
def test_edicion_rfq_no_cambia_proveedor_no_vigente(app, entorno_contable, caso):
    """#2319: la edición no sustituye un proveedor válido por uno no vigente."""
    proveedor_id = _tercero(app, is_supplier=True)
    candidato_id = _tercero(app, is_supplier=True)
    with app.app_context():
        if caso == "inactivo":
            database.session.get(Party, candidato_id).is_active = False
        else:
            vinculo = database.session.execute(
                database.select(CompanyParty).filter_by(party_id=candidato_id, company="cacao")
            ).scalar_one()
            vinculo.is_active = False
        cotizacion = PurchaseQuotation(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            supplier_id=proveedor_id,
            supplier_name="Proveedor original",
            transaction_currency="NIO",
        )
        database.session.add(cotizacion)
        database.session.commit()
        cotizacion_id = cotizacion.id
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        with app.test_request_context("/", method="POST", data=_formulario(candidato_id, version=cotizacion.version)):
            login_user(admin)
            assert _handle_purchase_quotation_edit_post(cotizacion) is not None

        registro = database.session.get(PurchaseQuotation, cotizacion_id)
        assert registro is not None
        assert registro.supplier_id == proveedor_id
        assert registro.supplier_name == "Proveedor original"


def test_historico_rfq_sigue_consultable_si_proveedor_se_desactiva(app, entorno_contable):
    """La lectura histórica no depende de la vigencia actual del proveedor."""
    proveedor_id = _tercero(app, is_supplier=True)
    with app.app_context():
        cotizacion = PurchaseQuotation(
            company="cacao",
            posting_date=FECHA,
            docstatus=1,
            supplier_id=proveedor_id,
            supplier_name="Proveedor historico",
            transaction_currency="NIO",
        )
        database.session.add(cotizacion)
        database.session.commit()
        cotizacion_id = cotizacion.id
        database.session.get(Party, proveedor_id).is_active = False
        database.session.commit()
        database.session.remove()

        leida = database.session.get(PurchaseQuotation, cotizacion_id)
        assert leida is not None
        assert leida.supplier_id == proveedor_id
