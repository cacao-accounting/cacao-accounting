# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes
"""Idempotent seeds for built-in print templates."""

from __future__ import annotations

from sqlalchemy import select

from cacao_accounting.database import database
from cacao_accounting.printing.models import PrintTemplate
from cacao_accounting.printing.registry import PRINTABLE_DOCUMENTS, init_printing_registry

BASE_CSS = """
@page { size: letter portrait; margin: 15mm; }
body { font-family: Arial, sans-serif; font-size: 12px; color: #1f2937; line-height: 1.4; position: relative; }
.print-header {
  display: flex;
  justify-content: space-between;
  border-bottom: 1px solid #d1d5db;
  padding-bottom: 10px;
  margin-bottom: 16px;
}
.company-info h1 { margin: 0 0 4px; font-size: 18px; }
.document-info { text-align: right; }
.document-info h2 { margin: 0 0 6px; font-size: 16px; }
.status-badge {
  display: inline-block;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: bold;
  border-radius: 3px;
  text-transform: uppercase;
  margin-top: 4px;
}
.status-posted, .status-submitted, .status-approved, .status-closed {
  background-color: #d1fae5;
  color: #065f46;
  border: 1px solid #a7f3d0;
}
.status-draft, .status-borrador {
  background-color: #fef3c7;
  color: #92400e;
  border: 1px solid #fde68a;
}
.status-cancelled, .status-anulado, .status-void, .status-rejected {
  background-color: #fee2e2;
  color: #991b1b;
  border: 1px solid #fca5a5;
}
.items-table { width: 100%; border-collapse: collapse; margin: 14px 0; }
.items-table th, .items-table td { border: 1px solid #e5e7eb; padding: 6px; }
.items-table th { background: #f9fafb; }
.text-right { text-align: right; }
.totals { margin-left: auto; width: 260px; border-collapse: collapse; }
.totals td { padding: 4px 6px; }
.validation-block { margin-top: 16px; display: flex; align-items: center; gap: 10px; font-size: 10px; color: #374151; }
.qr-code { width: 72px; height: 72px; }
.validation-text { line-height: 1.3; }
.print-footer { margin-top: 32px; font-size: 10px; color: #6b7280; border-top: 1px solid #e5e7eb; padding-top: 8px; }
.watermark {
  position: fixed;
  top: 35%;
  left: 10%;
  width: 80%;
  text-align: center;
  font-size: 54pt;
  font-weight: bold;
  opacity: 0.15;
  transform: rotate(-30deg);
  text-transform: uppercase;
  pointer-events: none;
  z-index: 1000;
}
.watermark-draft { color: #d97706; }
.watermark-cancelled { color: #dc2626; }
thead { display: table-header-group; }
tfoot { display: table-footer-group; }
"""

JOURNAL_TEMPLATE = (
    """
{% set current_status = journal_entry.status | default_text('') | lower %}
{% if current_status in ['draft', 'borrador'] %}
<div class="watermark watermark-draft">BORRADOR</div>
{% elif current_status in ['cancelled', 'anulado', 'void', 'rejected'] %}
<div class="watermark watermark-cancelled">ANULADO</div>
{% endif %}
<div class="print-header">
  <div class="company-info">
    <h1>{{ company.name }}</h1>
    <div>{{ company.tax_id }}</div>
    <div>{{ company.address }}</div>
  </div>
  <div class="document-info">
    <h2>Comprobante contable</h2>
    <div>{{ journal_entry.number }}</div>
    <div>{{ journal_entry.date }}</div>
    <div class="status-badge status-{{ current_status }}">{{ journal_entry.status | status_label }}</div>
  </div>
</div>
<p>{{ journal_entry.memo | default_text }}</p>
<table class="items-table">
  <thead>
    <tr>
      <th>Account</th>
      <th>Description</th>
      <th class="text-right">Debit</th>
      <th class="text-right">Credit</th>
    </tr>
  </thead>
  <tbody>
    {% for item in journal_entry['items'] %}
    <tr>
      <td>{{ item.account_code }} {{ item.account_name }}</td>
      <td>{{ item.description }}</td>
      <td class="text-right">{{ item.debit | money(journal_entry.currency) }}</td>
      <td class="text-right">{{ item.credit | money(journal_entry.currency) }}</td>
    </tr>
    {% endfor %}
  </tbody>
  <tfoot>
    <tr>
      <th colspan="2">Total</th>
      <th class="text-right">{{ journal_entry.total_debit | money(journal_entry.currency) }}</th>
      <th class="text-right">{{ journal_entry.total_credit | money(journal_entry.currency) }}</th>
    </tr>
  </tfoot>
</table>
"""
    + """
{% if validation is defined and validation and validation.enabled and validation.qr_data_uri %}
<div class="validation-block">
  <img src="{{ validation.qr_data_uri }}" class="qr-code" alt="Document validation QR">
  <div class="validation-text"><strong>Validate document</strong><br>Scan this QR code to verify this document.</div>
</div>
{% endif %}
<div class="print-footer">Printed by {{ audit.printed_by }} at {{ audit.printed_at }}</div>
"""
)

LINES_TEMPLATE = """
{% set current_status = doc.status | default_text('') | lower %}
{% if current_status in ['draft', 'borrador'] %}
<div class="watermark watermark-draft">BORRADOR</div>
{% elif current_status in ['cancelled', 'anulado', 'void', 'rejected'] %}
<div class="watermark watermark-cancelled">ANULADO</div>
{% endif %}
<div class="print-header">
  <div class="company-info">
    <h1>{{ company.name }}</h1>
    <div>{{ company.tax_id }}</div>
    <div>{{ company.address }}</div>
  </div>
  <div class="document-info">
    <h2>{{ title }}</h2>
    <div>{{ doc.number }}</div>
    <div>{{ doc.date }}</div>
    <div class="status-badge status-{{ current_status }}">{{ doc.status | status_label }}</div>
  </div>
</div>
<table class="items-table">
  <thead>
    <tr>
      <th>Code</th>
      <th>Description</th>
      <th class="text-right">Qty</th>
      <th class="text-right">Unit Price</th>
      <th class="text-right">Total</th>
    </tr>
  </thead>
  <tbody>
    {% for item in doc['items'] %}
    <tr>
      <td>{{ item.item_code }}</td>
      <td>{{ item.description }}</td>
      <td class="text-right">{{ item.quantity | number }}</td>
      <td class="text-right">{{ item.unit_price | money(doc.get('currency', company.default_currency)) }}</td>
      <td class="text-right">{{ item.line_total | money(doc.get('currency', company.default_currency)) }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
<table class="totals">
  {% set doc_curr = doc.get('currency', company.default_currency) %}
  <tr><td>Subtotal</td><td class="text-right">{{ (doc.get('subtotal', 0)) | money(doc_curr) }}</td></tr>
  <tr><td>Taxes</td><td class="text-right">{{ (doc.get('taxes', 0)) | money(doc_curr) }}</td></tr>
  <tr>
    <td><strong>Grand total</strong></td>
    <td class="text-right"><strong>{{ (doc.get('grand_total', 0)) | money(doc_curr) }}</strong></td>
  </tr>
</table>
{% if validation is defined and validation and validation.enabled and validation.qr_data_uri %}
<div class="validation-block">
  <img src="{{ validation.qr_data_uri }}" class="qr-code" alt="Document validation QR">
  <div class="validation-text"><strong>Validate document</strong><br>Scan this QR code to verify this document.</div>
</div>
{% endif %}
<div class="print-footer">Printed by {{ audit.printed_by }} at {{ audit.printed_at }}</div>
"""

ROOT_TEMPLATE_MAP = {
    "invoice": "{% set doc = invoice %}{% set title = 'Factura' %}" + LINES_TEMPLATE,
    "purchase_order": "{% set doc = purchase_order %}{% set title = 'Orden de compra' %}" + LINES_TEMPLATE,
    "sales_order": "{% set doc = sales_order %}{% set title = 'Orden de venta' %}" + LINES_TEMPLATE,
    "sales_request": "{% set doc = sales_request %}{% set title = 'Solicitud de venta' %}" + LINES_TEMPLATE,
    "purchase_request": "{% set doc = purchase_request %}{% set title = 'Solicitud de compra' %}" + LINES_TEMPLATE,
    "supplier_quotation": "{% set doc = supplier_quotation %}{% set title = 'Cotizacion de proveedor' %}" + LINES_TEMPLATE,
    "request_for_quotation": "{% set doc = request_for_quotation %}{% set title = 'Solicitud de cotizacion' %}"
    + LINES_TEMPLATE,
    "purchase_receipt": "{% set doc = purchase_receipt %}{% set title = 'Recepcion de compra' %}" + LINES_TEMPLATE,
    "landed_cost": "{% set doc = landed_cost %}{% set title = 'Gasto de importacion' %}" + LINES_TEMPLATE,
    "receipt": "{% set doc = receipt %}{% set title = 'Nota de entrega' %}" + LINES_TEMPLATE,
    "adjustment": "{% set doc = adjustment %}{% set title = 'Movimiento de inventario' %}" + LINES_TEMPLATE,
    "quote": "{% set doc = quote %}{% set title = 'Cotizacion' %}" + LINES_TEMPLATE,
    "payment": """
{% set current_status = payment.status | default_text('') | lower %}
{% if current_status in ['draft', 'borrador'] %}
<div class="watermark watermark-draft">BORRADOR</div>
{% elif current_status in ['cancelled', 'anulado', 'void', 'rejected'] %}
<div class="watermark watermark-cancelled">ANULADO</div>
{% endif %}
<div class="print-header">
  <div class="company-info"><h1>{{ company.name }}</h1><div>{{ company.tax_id }}</div></div>
  <div class="document-info">
    <h2>Comprobante de pago</h2>
    <div>{{ payment.number }}</div>
    <div>{{ payment.date }}</div>
    <div class="status-badge status-{{ current_status }}">{{ payment.status | status_label }}</div>
  </div>
</div>
<p>Party: {{ payment.party_name }}</p>
<p>Total: {{ payment.paid_amount | money(payment.currency) }}</p>
{% if validation is defined and validation and validation.enabled and validation.qr_data_uri %}
<div class="validation-block">
  <img src="{{ validation.qr_data_uri }}" class="qr-code" alt="Document validation QR">
  <div class="validation-text"><strong>Validate document</strong><br>Scan this QR code to verify this document.</div>
</div>
{% endif %}
<div class="print-footer">Printed by {{ audit.printed_by }} at {{ audit.printed_at }}</div>
""",
    "revaluation": """
{% set current_status = revaluation.status | default_text('') | lower %}
{% if current_status in ['draft', 'borrador'] %}
<div class="watermark watermark-draft">BORRADOR</div>
{% elif current_status in ['cancelled', 'anulado', 'void', 'rejected'] %}
<div class="watermark watermark-cancelled">ANULADO</div>
{% endif %}
<div class="print-header">
  <div class="company-info"><h1>{{ company.name }}</h1><div>{{ company.tax_id }}</div></div>
  <div class="document-info">
    <h2>Comprobante de revaluacion</h2>
    <div>{{ revaluation.number }}</div>
    <div>{{ revaluation.date }}</div>
    <div class="status-badge status-{{ current_status }}">{{ revaluation.status | status_label }}</div>
  </div>
</div>
<table class="items-table">
  <thead>
    <tr>
      <th>Reference</th>
      <th class="text-right">Old rate</th>
      <th class="text-right">New rate</th>
      <th class="text-right">Difference</th>
    </tr>
  </thead>
  <tbody>
    {% for item in revaluation['items'] %}
    <tr>
      <td>{{ item.reference_type }} {{ item.reference_id }}</td>
      <td class="text-right">{{ item.old_rate | number }}</td>
      <td class="text-right">{{ item.new_rate | number }}</td>
      <td class="text-right">{{ item.difference_amount | money(revaluation.currency) }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% if validation is defined and validation and validation.enabled and validation.qr_data_uri %}
<div class="validation-block">
  <img src="{{ validation.qr_data_uri }}" class="qr-code" alt="Document validation QR">
  <div class="validation-text"><strong>Validate document</strong><br>Scan this QR code to verify this document.</div>
</div>
{% endif %}
<div class="print-footer">Printed by {{ audit.printed_by }} at {{ audit.printed_at }}</div>
""",
}


def seed_print_templates() -> None:
    """Seed global system default templates for every registered document."""
    if not PRINTABLE_DOCUMENTS:
        init_printing_registry()
    for document_type, definition in PRINTABLE_DOCUMENTS.items():
        _ensure_system_template(document_type, definition["label"], definition["root_context_name"])


def _ensure_system_template(document_type: str, label: str, root_name: str) -> None:
    code = f"system_default_{document_type}"
    existing = database.session.execute(select(PrintTemplate).filter_by(code=code, company_code=None)).scalars().first()
    template_body = (
        JOURNAL_TEMPLATE
        if root_name == "journal_entry"
        else ROOT_TEMPLATE_MAP.get(
            root_name, "{% set doc = " + root_name + " %}{% set title = '" + label + "' %}" + LINES_TEMPLATE
        )
    )
    if existing is not None:
        existing.template_body = template_body
        existing.stylesheet_body = BASE_CSS
        database.session.commit()
        return
    database.session.add(
        PrintTemplate(
            company_code=None,
            document_type=document_type,
            code=code,
            name=f"{label} basico",
            template_body=template_body,
            stylesheet_body=BASE_CSS,
            paper_size="letter",
            orientation="portrait",
            is_system=True,
            is_default=True,
            status="published",
        )
    )
    database.session.commit()
