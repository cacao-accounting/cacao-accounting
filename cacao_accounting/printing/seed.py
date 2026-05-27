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
body { font-family: Arial, sans-serif; font-size: 12px; color: #1f2937; line-height: 1.4; }
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
thead { display: table-header-group; }
tfoot { display: table-footer-group; }
"""

JOURNAL_TEMPLATE = (
    """
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
    <div>{{ journal_entry.status | status_label }}</div>
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
    {% for item in journal_entry.items %}
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
{% if validation.enabled and validation.qr_data_uri %}
<div class="validation-block">
  <img src="{{ validation.qr_data_uri }}" class="qr-code" alt="Document validation QR">
  <div class="validation-text"><strong>Validate document</strong><br>Scan this QR code to verify this document.</div>
</div>
{% endif %}
<div class="print-footer">Printed by {{ audit.printed_by }} at {{ audit.printed_at }}</div>
"""
)

LINES_TEMPLATE = """
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
    <div>{{ doc.status | status_label }}</div>
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
    {% for item in doc.items %}
    <tr>
      <td>{{ item.item_code }}</td>
      <td>{{ item.description }}</td>
      <td class="text-right">{{ item.quantity | number }}</td>
      <td class="text-right">{{ item.unit_price | money(doc.currency) }}</td>
      <td class="text-right">{{ item.line_total | money(doc.currency) }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
<table class="totals">
  <tr><td>Subtotal</td><td class="text-right">{{ doc.subtotal | money(doc.currency) }}</td></tr>
  <tr><td>Taxes</td><td class="text-right">{{ doc.taxes | money(doc.currency) }}</td></tr>
  <tr>
    <td><strong>Grand total</strong></td>
    <td class="text-right"><strong>{{ doc.grand_total | money(doc.currency) }}</strong></td>
  </tr>
</table>
{% if validation.enabled and validation.qr_data_uri %}
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
    "receipt": "{% set doc = receipt %}{% set title = 'Nota de entrega' %}" + LINES_TEMPLATE,
    "adjustment": "{% set doc = adjustment %}{% set title = 'Movimiento de inventario' %}" + LINES_TEMPLATE,
    "quote": "{% set doc = quote %}{% set title = 'Cotizacion' %}" + LINES_TEMPLATE,
    "payment": """
<div class="print-header">
  <div class="company-info"><h1>{{ company.name }}</h1><div>{{ company.tax_id }}</div></div>
  <div class="document-info"><h2>Comprobante de pago</h2><div>{{ payment.number }}</div><div>{{ payment.date }}</div></div>
</div>
<p>Party: {{ payment.party_name }}</p>
<p>Total: {{ payment.paid_amount | money(payment.currency) }}</p>
{% if validation.enabled and validation.qr_data_uri %}
<div class="validation-block">
  <img src="{{ validation.qr_data_uri }}" class="qr-code" alt="Document validation QR">
  <div class="validation-text"><strong>Validate document</strong><br>Scan this QR code to verify this document.</div>
</div>
{% endif %}
<div class="print-footer">Printed by {{ audit.printed_by }} at {{ audit.printed_at }}</div>
""",
    "revaluation": """
<div class="print-header">
  <div class="company-info"><h1>{{ company.name }}</h1><div>{{ company.tax_id }}</div></div>
  <div class="document-info">
    <h2>Comprobante de revaluacion</h2>
    <div>{{ revaluation.number }}</div>
    <div>{{ revaluation.date }}</div>
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
    {% for item in revaluation.items %}
    <tr>
      <td>{{ item.reference_type }} {{ item.reference_id }}</td>
      <td class="text-right">{{ item.old_rate | number }}</td>
      <td class="text-right">{{ item.new_rate | number }}</td>
      <td class="text-right">{{ item.difference_amount | money(revaluation.currency) }}</td>
    </tr>
    {% endfor %}
  </tbody>
</table>
{% if validation.enabled and validation.qr_data_uri %}
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
    if existing is not None:
        return
    template_body = JOURNAL_TEMPLATE if root_name == "journal_entry" else ROOT_TEMPLATE_MAP[root_name]
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
