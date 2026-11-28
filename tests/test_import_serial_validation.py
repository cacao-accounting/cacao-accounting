# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1629: la importación prevalida series y cantidad unitaria."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from cacao_accounting.database import CompanyParty, Item, ItemUOMConversion, Party, SerialNumber, UOM, database
from cacao_accounting.imports.adapters.transaction_documents import (
    DeliveryNoteAdapter,
    PurchaseReceiptAdapter,
    TransactionDocumentAdapter,
)
from cacao_accounting.inventario.service import validate_batch_serial_draft


def _item_serializado() -> str:
    sufijo = uuid4().hex[:6]
    codigo = f"SER-{sufijo}"
    database.session.add(
        Item(
            code=codigo,
            name=f"Item serializado {sufijo}",
            item_type="goods",
            is_stock_item=True,
            is_sale_item=True,
            is_purchase_item=True,
            has_serial_no=True,
            default_uom="UND",
        )
    )
    database.session.commit()
    return codigo


def _habilitar_cliente() -> None:
    """Habilita el tercero del escenario para validar el documento completo."""
    party = database.session.execute(database.select(Party).filter_by(code="CLI001")).scalar_one()
    party.is_active = True
    party.is_customer = True
    vinculo = database.session.execute(
        database.select(CompanyParty).filter_by(company="cacao", party_id=party.id)
    ).scalar_one_or_none()
    if vinculo is None:
        database.session.add(CompanyParty(company="cacao", party_id=party.id, is_active=True))
    else:
        vinculo.is_active = True
    database.session.commit()


def _fila(item_code: str, cantidad: str, serie: str) -> dict[str, str]:
    return {
        "document_ref": f"DN-{uuid4().hex[:6]}",
        "fecha": "2026-05-15",
        "producto": item_code,
        "cantidad": cantidad,
        "precio_unitario": "10",
        "uom": "UND",
        "bodega": "BOD01",
        "numero_serie": serie,
        "tercero": "CLI001",
        "moneda": "NIO",
    }


def test_importacion_rechaza_cantidad_mayor_a_una_unidad_serializada(app, entorno_contable):
    """La prevalidación replica la regla de una unidad por serie."""
    del entorno_contable
    with app.app_context():
        item_code = _item_serializado()
        errores = DeliveryNoteAdapter().validate_document(
            [_fila(item_code, "2", f"SERIE-{item_code}")], {"company_id": "cacao"}
        )

        assert any("exactamente una unidad" in error for error in errores)


def test_importacion_rechaza_serie_faltante(app, entorno_contable):
    """Un item controlado por serie no puede importarse sin número."""
    del entorno_contable
    with app.app_context():
        item_code = _item_serializado()
        errores = DeliveryNoteAdapter().validate_document([_fila(item_code, "1", "")], {"company_id": "cacao"})

        assert any("requiere numero de serie" in error for error in errores)


def test_importacion_rechaza_serie_de_otro_articulo(app, entorno_contable):
    """Una serie existente no puede reutilizarse en un artículo distinto."""
    del entorno_contable
    with app.app_context():
        item_code = _item_serializado()
        serie = f"SERIE-{uuid4().hex[:8]}"
        otro_item = _item_serializado()
        database.session.add(SerialNumber(item_code=otro_item, serial_no=serie, serial_status="available"))
        database.session.commit()

        errores = DeliveryNoteAdapter().validate_document([_fila(item_code, "1", serie)], {"company_id": "cacao"})

        assert any("registrado para otro art" in error for error in errores)


def test_borrador_serializado_exige_una_unidad(app, entorno_contable):
    """La validación de borradores también rechaza cantidades distintas de uno."""
    del entorno_contable
    with app.app_context():
        item_code = _item_serializado()
        linea = SimpleNamespace(
            item_code=item_code,
            serial_no="SER-001",
            qty=2,
            qty_in_base_uom=2,
        )

        with pytest.raises(ValueError, match="exactamente una unidad"):
            validate_batch_serial_draft([linea])


def test_importacion_rechaza_serial_no_disponible_para_salida(app, entorno_contable):
    """#1629 QA: salida no puede importar serial ya entregado."""
    del entorno_contable
    with app.app_context():
        item_code = _item_serializado()
        serie = f"SERIE-{uuid4().hex[:8]}"
        database.session.add(SerialNumber(item_code=item_code, serial_no=serie, serial_status="delivered", warehouse="BOD01"))
        database.session.commit()
        errores = DeliveryNoteAdapter().validate_document([_fila(item_code, "1", serie)], {"company_id": "cacao"})
        assert any("disponible para salida" in e for e in errores)


def test_importacion_rechaza_serial_duplicado_en_documento(app, entorno_contable):
    """#1629 QA: detecta duplicado intra-documento antes de persistir."""
    del entorno_contable
    with app.app_context():
        item_code = _item_serializado()
        serie = f"SERIE-{uuid4().hex[:8]}"
        filas = [_fila(item_code, "1", serie), _fila(item_code, "1", serie)]
        filas[1]["document_ref"] = filas[0]["document_ref"]
        errores = DeliveryNoteAdapter().validate_document(filas, {"company_id": "cacao"})
        assert any("duplicado" in e.lower() for e in errores)


def test_recepcion_rechaza_serial_entregado_sin_devolucion(entorno_contable_aislado):
    """Una recepción normal no puede reingresar un serial ya entregado."""
    app = entorno_contable_aislado.app
    with app.app_context():
        item_code = _item_serializado()
        serie = f"SERIE-{uuid4().hex[:8]}"
        database.session.add(SerialNumber(item_code=item_code, serial_no=serie, serial_status="delivered", warehouse="BOD01"))
        database.session.commit()
        fila = _fila(item_code, "1", serie)
        fila["tercero"] = "PRV001"

        errores = PurchaseReceiptAdapter().validate_document([fila], {"company_id": "cacao"})

        assert any("solo puede cambiar de bodega" in error for error in errores)


def test_importacion_permite_transferencia_de_serial_disponible(entorno_contable_aislado):
    """La prevalidación respeta allow_transfer igual que el posting."""
    app = entorno_contable_aislado.app
    with app.app_context():
        item_code = _item_serializado()
        serie = f"SERIE-{uuid4().hex[:8]}"
        database.session.add(SerialNumber(item_code=item_code, serial_no=serie, serial_status="available", warehouse="BOD01"))
        database.session.commit()
        config = replace(DeliveryNoteAdapter().config, serial_outgoing=False, serial_allow_transfer=True)
        adapter = TransactionDocumentAdapter(config)
        _habilitar_cliente()

        errores = adapter.validate_document([_fila(item_code, "1", serie)], {"company_id": "cacao"})

        assert not any("serial" in error.lower() for error in errores)


def test_importacion_convierte_uom_antes_de_validar_serial(entorno_contable_aislado):
    """Dos cajas de 0.5 unidades representan una unidad base serializada."""
    app = entorno_contable_aislado.app
    with app.app_context():
        item_code = _item_serializado()
        serie = f"SERIE-{uuid4().hex[:8]}"
        database.session.add(UOM(code="CAJA", name="Caja"))
        database.session.flush()
        database.session.add(
            ItemUOMConversion(item_code=item_code, from_uom="CAJA", to_uom="UND", conversion_factor=Decimal("0.5"))
        )
        database.session.add(SerialNumber(item_code=item_code, serial_no=serie, serial_status="available", warehouse="BOD01"))
        database.session.commit()
        fila = _fila(item_code, "2", serie)
        fila["uom"] = "CAJA"
        _habilitar_cliente()

        errores = DeliveryNoteAdapter().validate_document([fila], {"company_id": "cacao"})

        assert not any("serial" in error.lower() for error in errores)
