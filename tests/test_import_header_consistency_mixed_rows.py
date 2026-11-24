# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1628: filas agrupadas deben compartir la cabecera del documento."""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.imports.adapters.transaction_documents import SalesRequestAdapter


def _fila(moneda: str, tasa: str) -> dict[str, str]:
    return {
        "document_ref": f"SR-MIX-{uuid4().hex[:6]}",
        "fecha": "2026-05-15",
        "producto": "ART01",
        "cantidad": "1",
        "precio_unitario": "10",
        "uom": "UND",
        "tercero": "CLI001",
        "moneda": moneda,
        "tipo_cambio": tasa,
    }


def test_rechaza_moneda_y_tasa_distintas_en_el_mismo_documento(app, entorno_contable):
    """La segunda fila no puede redefinir la moneda/tasa del encabezado."""
    del entorno_contable
    with app.app_context():
        filas = [_fila("NIO", "1"), _fila("USD", "36.5")]
        filas[1]["document_ref"] = filas[0]["document_ref"]

        errores = SalesRequestAdapter().validate_document(filas, {"company_id": "cacao"})

        assert any("moneda" in error and "no coincide" in error for error in errores)
        assert any("tipo_cambio" in error and "no coincide" in error for error in errores)


def test_rechaza_fecha_y_tercero_distintos_en_el_mismo_documento(app, entorno_contable):
    """Las demás cabeceras repetidas también deben coincidir entre filas."""
    del entorno_contable
    with app.app_context():
        filas = [_fila("NIO", "1"), _fila("NIO", "1")]
        filas[1]["document_ref"] = filas[0]["document_ref"]
        filas[1]["fecha"] = "2026-05-16"
        filas[1]["tercero"] = "CLI002"

        errores = SalesRequestAdapter().validate_document(filas, {"company_id": "cacao"})

        assert any("fecha" in error and "no coincide" in error for error in errores)
        assert any("tercero" in error and "no coincide" in error for error in errores)
