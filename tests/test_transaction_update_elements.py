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
    "purchase_receipt": "inventory",
    "purchase_invoice": "purchases",
    "sales_request": "sales",
    "sales_quotation": "sales",
    "sales_order": "sales",
    "delivery_note": "inventory",
    "sales_invoice": "sales",
    "stock_entry": "inventory",
}


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_supplier_quotation_updates_from_purchase_quotation_doctype():
    """Cotización de Proveedor debe actualizar desde Solicitud de Cotización."""
    routes = _read("cacao_accounting/compras/routes.py")
    template = _read("cacao_accounting/compras/templates/compras/cotizacion_proveedor_nueva.html")

    assert '"value": "purchase_request"' in routes
    assert '"value": "purchase_quotation"' in routes
    assert "source_type=purchase_request&target_type=supplier_quotation" in template
    assert "source_type=purchase_quotation&target_type=supplier_quotation" in template
    assert "request_for_quotation" not in routes
    assert "request_for_quotation" not in template


def test_purchase_detail_breadcrumbs_include_their_list_pages():
    """Los detalles de RFQ y oferta deben conservar el contexto de navegación."""
    purchase_quotation = _read("cacao_accounting/compras/templates/compras/solicitud_cotizacion.html")
    supplier_quotation = _read("cacao_accounting/compras/templates/compras/cotizacion_proveedor.html")
    supplier_quotation_new = _read("cacao_accounting/compras/templates/compras/cotizacion_proveedor_nueva.html")

    assert "compras.compras_solicitud_cotizacion_lista" in purchase_quotation
    assert "compras.compras_cotizacion_proveedor_lista" in supplier_quotation
    assert "compras.compras_solicitud_cotizacion" in supplier_quotation_new
    assert "compras.compras_solicitud_compra" in supplier_quotation_new


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


def test_offer_comparison_list_keeps_requests_and_shows_comparison_status():
    """El listado conserva la solicitud y presenta el estado del comparativo."""
    routes = _read("cacao_accounting/compras/routes.py")
    template = _read("cacao_accounting/compras/templates/compras/comparativo_ofertas_lista.html")
    comparison_template = _read("cacao_accounting/compras/templates/compras/comparativo_solicitud.html")
    selector = _read("cacao_accounting/compras/templates/compras/comparativo_ordenes_seleccionar.html")

    assert "PurchaseRequest.docstatus == 1" in routes
    assert "PurchaseRequestComparison.purchase_request_id.in_(request_ids)" in routes
    assert "Finalizado" in template
    assert "Nueva comparativa" in template
    assert "{% endif %} {% if negotiation_rfqs %}" in comparison_template
    assert "Ver comparativo" in template
    assert 'name="supplier_quotation_ids"' in selector
    assert "purchase_order" not in selector


def test_purchase_request_list_does_not_display_total_column():
    """El listado de solicitudes no debe mostrar la columna de total."""
    template = _read("cacao_accounting/compras/templates/compras/solicitud_compra_lista.html")

    assert '<th scope="col">Total</th>' not in template
    assert "item.grand_total" not in template


def test_purchase_quotation_list_does_not_display_total_column():
    """El listado de solicitudes de cotizacion no debe mostrar la columna de total."""
    template = _read("cacao_accounting/compras/templates/compras/solicitud_cotizacion_lista.html")

    assert '<th scope="col">Total</th>' not in template
    assert "item.grand_total" not in template


def test_purchase_request_does_not_expose_department_concept():
    """La solicitud de compra no debe presentar Departamento como atributo."""
    form = _read("cacao_accounting/compras/forms.py")
    new_template = _read("cacao_accounting/compras/templates/compras/solicitud_compra_nueva.html")
    detail_template = _read("cacao_accounting/compras/templates/compras/solicitud_compra.html")

    assert 'department = StringField("Departamento")' not in form
    assert 'requested_by = StringField("Solicitado por")' not in form
    assert "form.department" not in new_template
    assert "form.requested_by" not in new_template
    assert "Departamento" not in detail_template
    assert "<textarea" not in new_template


def test_transaction_lists_show_document_number():
    """Los listados transaccionales deben mostrar el identificador visible."""
    template_paths = [
        *((ROOT / "cacao_accounting/compras/templates/compras").glob("*_lista.html")),
        *((ROOT / "cacao_accounting/ventas/templates/ventas").glob("*_lista.html")),
        ROOT / "cacao_accounting/inventario/templates/inventario/entrada_lista.html",
        ROOT / "cacao_accounting/bancos/templates/bancos/pago_lista.html",
    ]
    excluded = {"comparativo_ofertas_lista.html", "proveedor_lista.html", "cliente_lista.html"}
    for path in template_paths:
        if path.name in excluded:
            continue
        content = path.read_text(encoding="utf-8")
        assert "document_no or item.id" in content, path


def test_transaction_forms_use_one_line_header_observations():
    """Los formularios S2P, O2C e Inventory usan Observaciones en la cabecera."""
    macro = _read("cacao_accounting/templates/transaction_form_macros.html")
    assert 'id="remarks" name="remarks" type="text"' in macro

    form_paths = [
        *((ROOT / "cacao_accounting/compras/templates/compras").glob("*_nuevo.html")),
        *((ROOT / "cacao_accounting/ventas/templates/ventas").glob("*_nuevo.html")),
        *((ROOT / "cacao_accounting/inventario/templates/inventario").glob("*_nuevo.html")),
    ]
    for path in form_paths:
        content = path.read_text(encoding="utf-8")
        if "transaction_form_header" in content:
            assert 'id="remarks"' not in content, path


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
    purchases = _read("cacao_accounting/compras/routes.py")
    sales = _read("cacao_accounting/ventas/routes.py")

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
