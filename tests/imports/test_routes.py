# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Pruebas de rutas y plantillas del módulo de importaciones."""

from pathlib import Path

from cacao_accounting import create_app
from cacao_accounting.database import database
from cacao_accounting.imports.services.import_service import ImportService
from cacao_accounting.modulos import init_modulos

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "cacao_accounting" / "imports" / "templates" / "imports"


def test_imports_disabled_in_desktop_mode():
    """El módulo de importaciones no está disponible en modo escritorio."""
    app = create_app(
        {
            "TESTING": True,
            "MODO_ESCRITORIO": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    with app.app_context():
        database.create_all()
    with app.test_client() as client:
        response = client.get("/imports/")
        assert response.status_code == 403


def test_imports_enabled_in_web_mode():
    """En modo web la ruta existe y redirige al login si no hay sesión."""
    app = create_app(
        {
            "TESTING": True,
            "MODO_ESCRITORIO": False,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    with app.app_context():
        database.create_all()
        init_modulos()
    with app.test_client() as client:
        response = client.get("/imports/")
        assert response.status_code == 302
        assert "/login" in response.location


def test_new_template_has_single_record_type_field():
    """El formulario de nuevo lote solo debe tener un selector de tipo."""
    content = (TEMPLATES_DIR / "new.html").read_text(encoding="utf-8")

    assert content.count('name="record_type"') == 1


def test_new_template_uses_smart_select_for_context_fields():
    """Compañía, serie y libro deben usar el smart-select estándar."""
    content = (TEMPLATES_DIR / "new.html").read_text(encoding="utf-8")

    assert 'smart_select_field("Compañía", "company_id", "company"' in content
    assert 'smart_select_field("Serie / Secuencia", "sequence_id", "naming_series"' in content
    assert 'smart_select_field("Libro Contable", "accounting_book_id", "book"' in content
    assert '"entity_type": {"selector": "#import-entity-type"}' in content
    assert '["company", "entity_type"]' in content
    assert 'name="company_id"' not in content
    assert 'name="sequence_id"' not in content
    assert 'name="accounting_book_id"' not in content


def test_import_service_exposes_source_to_pay_and_order_to_cash_adapters():
    """El servicio debe soportar el flujo operativo completo de compras y ventas."""
    expected_record_types = {
        "purchase_request",
        "purchase_quotation",
        "supplier_quotation",
        "purchase_order",
        "purchase_receipt",
        "purchase_invoice",
        "sales_request",
        "sales_quotation",
        "sales_order",
        "delivery_note",
        "sales_invoice",
    }

    assert expected_record_types.issubset(ImportService.ADAPTERS)


def test_new_template_groups_source_to_pay_and_order_to_cash_options():
    """El selector debe mostrar los flujos S2P y O2C agrupados."""
    routes_path = Path(__file__).resolve().parents[2] / "cacao_accounting" / "imports" / "routes.py"
    content = routes_path.read_text(encoding="utf-8")

    assert "Source to Pay" in content
    assert "Order to Cash" in content
    assert "purchase_request" in content
    assert "purchase_invoice" in content
    assert "sales_request" in content
    assert "sales_invoice" in content


def test_new_template_orders_company_record_type_then_sequence():
    """La captura debe guiar compañía, tipo de registro y luego secuencia."""
    content = (TEMPLATES_DIR / "new.html").read_text(encoding="utf-8")

    company_position = content.index('smart_select_field("Compañía"')
    record_type_position = content.index('id="import-record-type"')
    sequence_position = content.index('smart_select_field("Serie / Secuencia"')

    assert company_position < record_type_position < sequence_position


def test_smart_select_macro_uses_full_width_layout():
    """El macro compartido debe ocupar el ancho disponible del contenedor."""
    macro_path = (
        Path(__file__).resolve().parents[2] / "cacao_accounting" / "reportes" / "templates" / "reportes" / "report_macros.html"
    )
    content = macro_path.read_text(encoding="utf-8")

    assert '<label class="form-label mb-0 w-100">' in content


def test_import_templates_render_in_base_content_block():
    """Las plantillas deben usar el bloque que realmente pinta base.html."""
    for template_name in ("index.html", "new.html", "detail.html"):
        content = (TEMPLATES_DIR / template_name).read_text(encoding="utf-8")
        assert "{% block contenido %}" in content
        assert "{% block content %}" not in content


def test_index_template_has_empty_state():
    """El listado debe mostrar una pantalla útil cuando no hay lotes."""
    content = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")

    assert "No hay lotes de importación" in content
    assert "Nueva Importación" in content
