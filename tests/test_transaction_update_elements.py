# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Contratos de UI para actualizar elementos en formularios transaccionales."""

from pathlib import Path

from cacao_accounting.api.line_import import DOCTYPES_MODULES
from cacao_accounting.api.line_import_registry import LineImportSchemaRegistry
from cacao_accounting.document_flow.registry import ALLOWED_FLOWS

ROOT = Path(__file__).resolve().parents[1]
OPERATIONAL_DOCTYPES = {
    "purchase_request": "purchases",
    "purchase_quotation": "purchases",
    "supplier_quotation": "purchases",
    "purchase_order": "purchases",
    "purchase_receipt": "purchases",
    "purchase_invoice": "purchases",
    "sales_request": "sales",
    "sales_quotation": "sales",
    "sales_order": "sales",
    "delivery_note": "sales",
    "sales_invoice": "sales",
    "stock_entry": "inventory",
}


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_supplier_quotation_updates_from_purchase_quotation_doctype():
    """Cotización de Proveedor debe actualizar desde Solicitud de Cotización."""
    routes = _read("cacao_accounting/compras/__init__.py")
    template = _read("cacao_accounting/compras/templates/compras/cotizacion_proveedor_nueva.html")

    assert '"value": "purchase_request"' in routes
    assert '"value": "purchase_quotation"' in routes
    assert "source_type=purchase_request&target_type=supplier_quotation" in template
    assert "source_type=purchase_quotation&target_type=supplier_quotation" in template
    assert "request_for_quotation" not in routes
    assert "request_for_quotation" not in template


def test_purchase_request_shortcuts_include_company_and_autofill_lines():
    """Los atajos S2P deben cargar y aplicar las líneas de la solicitud origen."""
    macro = _read("cacao_accounting/templates/transaction_form_macros.html")
    supplier_quotation = _read("cacao_accounting/compras/templates/compras/cotizacion_proveedor_nueva.html")
    purchase_order = _read("cacao_accounting/compras/templates/compras/orden_compra_nuevo.html")

    assert "x-init='loadSourceFromUrl(" in macro
    assert ").then(() => applySource())'" in macro
    assert "target_type=supplier_quotation&source_id=" in supplier_quotation
    assert '"&company=" ~ solicitud_origen.company' in supplier_quotation
    assert '"&company=" ~ rfq_origen.company' in supplier_quotation
    assert '"&company=" ~ solicitud_origen.company' in purchase_order
    assert '"&company=" ~ rfq_origen.company' in purchase_order
    assert '"&company=" ~ supplier_quotation_origen.company' in purchase_order


def test_purchase_request_list_displays_generated_document_number():
    """El listado de solicitudes debe mostrar y enlazar el número generado."""
    template = _read("cacao_accounting/compras/templates/compras/solicitud_compra_lista.html")

    assert '<th scope="col">Número</th>' in template
    assert "item.document_no or item.id" in template
    assert "compras.compras_solicitud_compra" in template


def test_derived_document_pending_line_urls_are_company_scoped():
    """Todos los prellenados documentales deben enviar la compañía al API."""
    template_paths = [
        *((ROOT / "cacao_accounting/ventas/templates/ventas").glob("*_nuevo.html")),
        *((ROOT / "cacao_accounting/compras/templates/compras").glob("*_nuevo.html")),
        ROOT / "cacao_accounting/inventario/templates/inventario/entrada_nuevo.html",
    ]
    for path in template_paths:
        content = path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if "pending-lines?" in line:
                assert "company" in line, path


def test_update_elements_sources_are_configured_for_derived_documents():
    """Documentos derivados deben ofrecer Actualizar Elementos desde su origen real."""
    purchases = _read("cacao_accounting/compras/__init__.py")
    sales = _read("cacao_accounting/ventas/__init__.py")

    assert '"value": "purchase_request"' in purchases
    assert '"value": "purchase_quotation"' in purchases
    assert '{"value": "sales_request", "label": _(_LABEL_PEDIDO_VENTA)}' in sales
    assert '{"value": "sales_order", "label": _(_LABEL_ORDEN_VENTA)}' in sales


def test_line_import_is_enabled_for_operational_flows():
    """Source to Pay, Order to Cash e Inventario deben mostrar Importar líneas."""
    script = _read("cacao_accounting/static/js/transaction-form.js")
    import_set = script.split("const LINE_IMPORT_DOCUMENT_TYPES = new Set([", 1)[1].split("]);", 1)[0]

    for doctype, module in OPERATIONAL_DOCTYPES.items():
        assert f"'{doctype}'" in import_set
        assert DOCTYPES_MODULES[doctype] == module
        assert LineImportSchemaRegistry.get_schema(doctype) is not None


def test_update_elements_self_sources_are_enabled_for_operational_flows():
    """Cada documento operativo debe poder traer líneas de registros existentes del mismo tipo."""
    for doctype in OPERATIONAL_DOCTYPES:
        assert (doctype, doctype) in ALLOWED_FLOWS


def test_transaction_buttons_include_icons():
    """El macro transaccional debe usar iconos en acciones visibles."""
    template = _read("cacao_accounting/templates/transaction_form_macros.html")

    for label in [
        "Actualizar Elementos",
        "Añadir múltiple",
        "Añadir fila",
        "Importar líneas",
        "Cancelar",
        "Validar datos",
        "Insertar líneas",
        "Restablecer",
    ]:
        before_label = template.split(label, 1)[0]
        button_start = before_label.rfind("<button")
        icon_start = before_label.rfind("<i")
        assert button_start < icon_start, label
