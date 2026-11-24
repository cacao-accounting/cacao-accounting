# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1953: los encabezados de reportes operativos se traducen en ambos idiomas.

Los msgids fuente viven en español. La interfaz española debe mostrar el
término español y la inglesa su traducción del catálogo; un encabezado sin
traducción inglesa vuelve a filtrar español en la UI inglesa.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from flask_babel import force_locale

from cacao_accounting.database import Party, PurchaseInvoice, User, database
from cacao_accounting.i18n import _
from cacao_accounting.reportes.helpers import _COLUMN_LABELS, _column_label


def test_encabezados_citados_se_traducen_en_espanol_e_ingles(app):
    """Los casos reportados usan el término español y su versión inglesa."""
    with app.app_context():
        with force_locale("es"):
            assert _column_label("posting_date", None) == "Fecha de contabilización"
            assert _column_label("item_name", None) == "Nombre del artículo"
        with force_locale("en"):
            assert _column_label("posting_date", None) == "Posting Date"
            assert _column_label("item_name", None) == "Item Name"


def test_todos_los_encabezados_tienen_traduccion_inglesa(app):
    """Ningún msgid del mapa se queda sin traducción al inglés."""
    with app.app_context(), force_locale("en"):
        sin_traduccion = sorted({origen for origen in _COLUMN_LABELS.values() if _(origen) == origen})

    assert sin_traduccion == []


def test_reportes_de_compras_y_margen_tienen_etiquetas_traducibles(app):
    """Las claves emitidas por compras por proveedor y margen bruto están cubiertas."""
    claves = ("supplier_id", "income", "cogs", "gross_margin")
    with app.app_context():
        with force_locale("es"):
            assert _column_label("supplier_id", None) == "Proveedor"
            assert _column_label("gross_margin", None) == "Margen Bruto"
        with force_locale("en"):
            assert _column_label("supplier_id", None) == "Supplier"
            assert _column_label("gross_margin", None) == "Gross Margin"
            assert _column_label("income", None) == "Income"
            assert _column_label("cogs", None) == "Cost of Goods Sold"
        assert all(clave in _COLUMN_LABELS for clave in claves)


def test_http_compras_por_proveedor_y_margen_bruto_en_ambos_idiomas(app, entorno_contable, authenticated_client):
    """Los reportes reales muestran etiquetas españolas e inglesas, no Supplier Id/Gross Margin crudos."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    with app.app_context():
        proveedor = database.session.execute(database.select(Party).filter_by(code="PRV001")).scalar_one()
        factura = PurchaseInvoice(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"CMP-1953-{sufijo}",
            document_type="purchase_invoice",
            supplier_id=proveedor.id,
            supplier_name=proveedor.name,
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            grand_total=Decimal("10"),
            total=Decimal("10"),
            outstanding_amount=Decimal("10"),
        )
        database.session.add(factura)
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        idioma_original = admin.language
        admin.language = "es"
        database.session.commit()
        factura_id = factura.id

    client = authenticated_client("admin")
    try:
        es_compras = client.get("/reports/purchases-by-supplier?company=cacao").get_data(as_text=True)
        es_margen = client.get("/reports/gross-margin?company=cacao").get_data(as_text=True)
        assert "Proveedor" in es_compras
        assert "Supplier Id" not in es_compras
        assert "Margen Bruto" in es_margen

        with app.app_context():
            admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
            admin.language = "en"
            database.session.commit()
        with force_locale("en"):
            en_compras = client.get("/reports/purchases-by-supplier?company=cacao").get_data(as_text=True)
            en_margen = client.get("/reports/gross-margin?company=cacao").get_data(as_text=True)
        assert "Supplier" in en_compras
        assert "Gross Margin" in en_margen
        assert "Supplier Id" not in en_compras
    finally:
        with app.app_context():
            admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
            admin.language = idioma_original
            factura = database.session.get(PurchaseInvoice, factura_id)
            if factura is not None:
                database.session.delete(factura)
            database.session.commit()
