# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Idempotent seeds for built-in print templates."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from cacao_accounting.database import database
from cacao_accounting.printing.models import PrintTemplate
from cacao_accounting.i18n import LazyText
from cacao_accounting.printing.registry import PRINTABLE_DOCUMENTS, init_printing_registry

SEED_TEMPLATE_VERSION = 3

BASE_CSS = """
@page { margin: 15mm; }
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
<div class="watermark watermark-draft">{{ _("BORRADOR") }}</div>
{% elif current_status in ['cancelled', 'anulado', 'void', 'rejected'] %}
<div class="watermark watermark-cancelled">{{ _("ANULADO") }}</div>
{% endif %}
<div class="print-header">
  <div class="company-info">
    <h1>{{ company.name }}</h1>
    <div>{{ company.tax_id }}</div>
    <div>{{ company.address }}</div>
  </div>
  <div class="document-info">
    <h2>{{ _("Comprobante contable") }}</h2>
    <div>{{ journal_entry.number }}</div>
    <div>{{ journal_entry.date }}</div>
    <div class="status-badge status-{{ current_status }}">{{ journal_entry.status | status_label }}</div>
  </div>
</div>
<p>{{ journal_entry.memo | default_text }}</p>
<table class="items-table">
  <thead>
    <tr>
      <th>{{ _("Cuenta") }}</th>
      <th>{{ _("Descripción") }}</th>
      <th class="text-right">{{ _("Debe") }}</th>
      <th class="text-right">{{ _("Haber") }}</th>
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
      <th colspan="2">{{ _("Total") }}</th>
      <th class="text-right">{{ journal_entry.total_debit | money(journal_entry.currency) }}</th>
      <th class="text-right">{{ journal_entry.total_credit | money(journal_entry.currency) }}</th>
    </tr>
  </tfoot>
</table>
"""
    + """
{% if validation is defined and validation and validation.enabled and validation.qr_data_uri %}
<div class="validation-block">
  <img src="{{ validation.qr_data_uri }}" class="qr-code" alt="{{ _('Código QR de validación del documento') }}">
  <div class="validation-text">
    <strong>{{ _("Validar documento") }}</strong><br>
    {{ _("Escanee este código QR para verificar el documento.") }}
  </div>
</div>
{% endif %}
<div class="print-footer">
  {{ _("Impreso por") }} {{ audit.printed_by }} {{ _("el") }} {{ audit.printed_at }}<br>
  {{ _("Creado por") }} {{ audit.created_by | default_text('-') }} {{ _("el") }} {{ audit.created_at | default_text('-') }}<br>
  {{ _("Aprobado por") }} {{ audit.approved_by | default_text('-') }} {{ _("el") }} {{ audit.approved_at | default_text('-') }}
</div>
"""
)

LINES_TEMPLATE = """
{% set current_status = doc.status | default_text('') | lower %}
{% if current_status in ['draft', 'borrador'] %}
<div class="watermark watermark-draft">{{ _("BORRADOR") }}</div>
{% elif current_status in ['cancelled', 'anulado', 'void', 'rejected'] %}
<div class="watermark watermark-cancelled">{{ _("ANULADO") }}</div>
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
      <th>{{ _("Código") }}</th>
      <th>{{ _("Descripción") }}</th>
      <th class="text-right">{{ _("Cantidad") }}</th>
      <th class="text-right">{{ _("Precio unitario") }}</th>
      <th class="text-right">{{ _("Total") }}</th>
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
  <tr><td>{{ _("Subtotal") }}</td><td class="text-right">{{ (doc.get('subtotal', 0)) | money(doc_curr) }}</td></tr>
  <tr><td>{{ _("Impuestos") }}</td><td class="text-right">{{ (doc.get('taxes', 0)) | money(doc_curr) }}</td></tr>
  <tr>
    <td><strong>{{ _("Total general") }}</strong></td>
    <td class="text-right"><strong>{{ (doc.get('grand_total', 0)) | money(doc_curr) }}</strong></td>
  </tr>
</table>
{% if validation is defined and validation and validation.enabled and validation.qr_data_uri %}
<div class="validation-block">
  <img src="{{ validation.qr_data_uri }}" class="qr-code" alt="{{ _('Código QR de validación del documento') }}">
  <div class="validation-text">
    <strong>{{ _("Validar documento") }}</strong><br>
    {{ _("Escanee este código QR para verificar el documento.") }}
  </div>
</div>
{% endif %}
<div class="print-footer">
  {{ _("Impreso por") }} {{ audit.printed_by }} {{ _("el") }} {{ audit.printed_at }}<br>
  {{ _("Creado por") }} {{ audit.created_by | default_text('-') }} {{ _("el") }} {{ audit.created_at | default_text('-') }}<br>
  {{ _("Aprobado por") }} {{ audit.approved_by | default_text('-') }} {{ _("el") }} {{ audit.approved_at | default_text('-') }}
</div>
"""

ROOT_TEMPLATE_MAP = {
    "withholding_certificate": """
{% set current_status = withholding_certificate.status | default_text('') | lower %}
{% if current_status in ['cancelled', 'anulado', 'void'] %}
<div class="watermark watermark-cancelled">{{ _("ANULADO") }}</div>
{% endif %}
<div class="print-header">
  <div class="company-info"><h1>{{ company.name }}</h1><div>{{ company.tax_id }}</div></div>
  <div class="document-info">
    <h2>{{ _("Certificado de retención") }}</h2>
    <div>{{ withholding_certificate.number }}</div>
    <div>{{ withholding_certificate.date }}</div>
    <div class="status-badge status-{{ current_status }}">{{ withholding_certificate.status | status_label }}</div>
  </div>
</div>
<p>{{ _("Proveedor") }}: {{ withholding_certificate.supplier_name }}</p>
<p>{{ _("Pago relacionado") }}: {{ withholding_certificate.payment_number }}</p>
<table class="items-table">
  <thead><tr>
    <th>{{ _("Concepto") }}</th><th class="text-right">{{ _("Base") }}</th>
    <th class="text-right">{{ _("Tasa") }}</th><th class="text-right">{{ _("Retención") }}</th>
  </tr></thead>
  <tbody>{% for line in withholding_certificate.lines %}
    <tr>
      <td>{{ line.concept }}</td>
      <td class="text-right">{{ line.base_amount | money(withholding_certificate.currency) }}</td>
      <td class="text-right">{{ line.rate | percent }}</td>
      <td class="text-right">{{ line.amount | money(withholding_certificate.currency) }}</td>
    </tr>
  {% endfor %}</tbody>
</table>
<table class="totals">
  <tr><td>{{ _("Importe bruto") }}</td><td class="text-right">
    {{ withholding_certificate.gross_amount | money(withholding_certificate.currency) }}</td></tr>
  <tr><td>{{ _("Total retenido") }}</td><td class="text-right">
    {{ withholding_certificate.withheld_amount | money(withholding_certificate.currency) }}</td></tr>
  <tr><td>{{ _("Efectivo pagado") }}</td><td class="text-right">
    {{ withholding_certificate.cash_amount | money(withholding_certificate.currency) }}</td></tr>
</table>
{% if validation is defined and validation and validation.enabled and validation.qr_data_uri %}
<div class="validation-block">
  <img src="{{ validation.qr_data_uri }}" class="qr-code" alt="{{ _('Código QR de validación') }}">
  <div class="validation-text"><strong>{{ _("Validar certificado") }}</strong><br>
    {{ _("Escanee este código QR para verificar su autenticidad.") }}
  </div>
</div>
{% endif %}
<div class="print-footer">{{ _("Impreso por") }} {{ audit.printed_by }} {{ _("el") }} {{ audit.printed_at }}</div>
""",
    "invoice": '{% set doc = invoice %}{% set title = _("Factura") %}' + LINES_TEMPLATE,
    "purchase_order": '{% set doc = purchase_order %}{% set title = _("Orden de compra") %}' + LINES_TEMPLATE,
    "sales_order": '{% set doc = sales_order %}{% set title = _("Orden de venta") %}' + LINES_TEMPLATE,
    "sales_request": '{% set doc = sales_request %}{% set title = _("Solicitud de venta") %}' + LINES_TEMPLATE,
    "purchase_request": '{% set doc = purchase_request %}{% set title = _("Solicitud de compra") %}' + LINES_TEMPLATE,
    "supplier_quotation": '{% set doc = supplier_quotation %}{% set title = _("Cotización de proveedor") %}' + LINES_TEMPLATE,
    "request_for_quotation": '{% set doc = request_for_quotation %}{% set title = _("Solicitud de cotización") %}'
    + LINES_TEMPLATE,
    "purchase_receipt": '{% set doc = purchase_receipt %}{% set title = _("Recepción de compra") %}' + LINES_TEMPLATE,
    "landed_cost": '{% set doc = landed_cost %}{% set title = _("Gasto de importación") %}' + LINES_TEMPLATE,
    "receipt": '{% set doc = receipt %}{% set title = _("Nota de entrega") %}' + LINES_TEMPLATE,
    "adjustment": '{% set doc = adjustment %}{% set title = _("Movimiento de inventario") %}' + LINES_TEMPLATE,
    "quote": '{% set doc = quote %}{% set title = _("Cotización") %}' + LINES_TEMPLATE,
    "payment": """
{% set current_status = payment.status | default_text('') | lower %}
{% if current_status in ['draft', 'borrador'] %}
<div class="watermark watermark-draft">{{ _("BORRADOR") }}</div>
{% elif current_status in ['cancelled', 'anulado', 'void', 'rejected'] %}
<div class="watermark watermark-cancelled">{{ _("ANULADO") }}</div>
{% endif %}
<div class="print-header">
  <div class="company-info"><h1>{{ company.name }}</h1><div>{{ company.tax_id }}</div></div>
  <div class="document-info">
    <h2>{{ _("Comprobante de pago") }}</h2>
    <div>{{ payment.number }}</div>
    <div>{{ payment.date }}</div>
    <div class="status-badge status-{{ current_status }}">{{ payment.status | status_label }}</div>
  </div>
</div>
<p>{{ _("Beneficiario") }}: {{ payment.party_name }}</p>
<p>{{ _("Total") }}: {{ payment.paid_amount | money(payment.currency) }}</p>
{% if validation is defined and validation and validation.enabled and validation.qr_data_uri %}
<div class="validation-block">
  <img src="{{ validation.qr_data_uri }}" class="qr-code" alt="{{ _('Código QR de validación del documento') }}">
  <div class="validation-text">
    <strong>{{ _("Validar documento") }}</strong><br>
    {{ _("Escanee este código QR para verificar el documento.") }}
  </div>
</div>
{% endif %}
<div class="print-footer">
  {{ _("Impreso por") }} {{ audit.printed_by }} {{ _("el") }} {{ audit.printed_at }}<br>
  {{ _("Creado por") }} {{ audit.created_by | default_text('-') }} {{ _("el") }} {{ audit.created_at | default_text('-') }}<br>
  {{ _("Aprobado por") }} {{ audit.approved_by | default_text('-') }} {{ _("el") }} {{ audit.approved_at | default_text('-') }}
</div>
""",
    "check": """
{% set current_status = check.status | default_text('') | lower %}
{% if current_status in ['draft', 'borrador'] %}
<div class="watermark watermark-draft">{{ _("BORRADOR") }}</div>
{% elif current_status in ['cancelled', 'anulado', 'void', 'rejected'] %}
<div class="watermark watermark-cancelled">{{ _("ANULADO") }}</div>
{% endif %}

<div class="check-sheet" style="position: relative; width: 200mm; height: 85mm; font-family: monospace; font-size: 13px;">
  <div class="check-field check-amount" style="position: absolute; top: 12mm; left: 145mm; font-weight: bold;">
    ***{{ check.amount | money(check.currency) }}***
  </div>
  <div class="check-field check-payee" style="position: absolute; top: 24mm; left: 25mm; font-weight: bold;">
    {{ check.payee_name }}
  </div>
  <div class="check-field check-words" style="position: absolute; top: 34mm; left: 25mm; width: 160mm;">
    ***{{ check.amount_in_words }}***
  </div>
  <div class="check-field check-date" style="position: absolute; top: 50mm; left: 25mm;">
    {{ company.address | default_text('Managua') }}, {{ check.day }} de {{ check.month_name }} de {{ check.year }}
  </div>
  <div class="check-field check-memo" style="position: absolute; top: 64mm; left: 25mm; font-size: 11px;">
    {{ _("Cheque N.º") }} {{ check.number }} - {{ check.memo | default_text('') }}
  </div>
</div>
""",
    "revaluation": """
{% set current_status = revaluation.status | default_text('') | lower %}
{% if current_status in ['draft', 'borrador'] %}
<div class="watermark watermark-draft">{{ _("BORRADOR") }}</div>
{% elif current_status in ['cancelled', 'anulado', 'void', 'rejected'] %}
<div class="watermark watermark-cancelled">{{ _("ANULADO") }}</div>
{% endif %}
<div class="print-header">
  <div class="company-info"><h1>{{ company.name }}</h1><div>{{ company.tax_id }}</div></div>
  <div class="document-info">
    <h2>{{ _("Comprobante de revaluación") }}</h2>
    <div>{{ revaluation.number }}</div>
    <div>{{ revaluation.date }}</div>
    <div class="status-badge status-{{ current_status }}">{{ revaluation.status | status_label }}</div>
  </div>
</div>
<table class="items-table">
  <thead>
    <tr>
      <th>{{ _("Referencia") }}</th>
      <th class="text-right">{{ _("Tasa anterior") }}</th>
      <th class="text-right">{{ _("Tasa nueva") }}</th>
      <th class="text-right">{{ _("Diferencia") }}</th>
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
  <img src="{{ validation.qr_data_uri }}" class="qr-code" alt="{{ _('Código QR de validación del documento') }}">
  <div class="validation-text">
    <strong>{{ _("Validar documento") }}</strong><br>
    {{ _("Escanee este código QR para verificar el documento.") }}
  </div>
</div>
{% endif %}
<div class="print-footer">
  {{ _("Impreso por") }} {{ audit.printed_by }} {{ _("el") }} {{ audit.printed_at }}<br>
  {{ _("Creado por") }} {{ audit.created_by | default_text('-') }} {{ _("el") }} {{ audit.created_at | default_text('-') }}<br>
  {{ _("Aprobado por") }} {{ audit.approved_by | default_text('-') }} {{ _("el") }} {{ audit.approved_at | default_text('-') }}
</div>
""",
}


def _get_base_locale() -> str:
    """Return the installation/base locale for deterministic system template seeding."""
    try:
        from cacao_accounting.setup.service import SETUP_LANGUAGE, get_setup_value

        return get_setup_value(SETUP_LANGUAGE, "es")
    except Exception:
        return "es"


def seed_print_templates() -> None:
    """Seed global system default templates for every registered document."""
    if not PRINTABLE_DOCUMENTS:
        init_printing_registry()

    base_locale = _get_base_locale()
    try:
        _begin_seed_transaction()
        from flask_babel import force_locale

        with force_locale(base_locale):
            _seed_print_templates_internal()
            database.session.commit()
    except Exception:
        database.session.rollback()
        raise


def _seed_print_templates_internal() -> None:
    for document_type, definition in PRINTABLE_DOCUMENTS.items():
        _ensure_system_template(document_type, definition["label"], definition["root_context_name"])


def _begin_seed_transaction() -> None:
    """Serializa escritores SQLite y mantiene los savepoints en la transacción."""
    connection = database.session.connection()
    if connection.dialect.name == "sqlite" and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")


def _ensure_system_template(document_type: str, label: LazyText | str, root_name: str) -> None:
    label_str = str(label)
    code = f"system_default_{document_type}"
    existing = _find_system_template(document_type, code)
    template_body = (
        JOURNAL_TEMPLATE
        if root_name == "journal_entry"
        else ROOT_TEMPLATE_MAP.get(
            root_name, "{% set doc = " + root_name + " %}{% set title = '" + label_str + "' %}" + LINES_TEMPLATE
        )
    )
    if existing is not None:
        _update_system_template(existing, template_body)
        return
    try:
        with database.session.begin_nested():
            template = PrintTemplate(
                company_code=None,
                document_type=document_type,
                code=code,
                name=f"{label_str} basico",
                template_body=template_body,
                stylesheet_body=BASE_CSS,
                paper_size="letter",
                orientation="portrait",
                is_system=True,
                is_default=True,
                status="published",
                version=SEED_TEMPLATE_VERSION,
            )
            database.session.add(template)
            database.session.flush()
    except IntegrityError:
        existing = _find_system_template(document_type, code, for_update=True)
        if existing is None:
            raise
        _update_system_template(existing, template_body)


def _find_system_template(document_type: str, code: str, *, for_update: bool = False) -> PrintTemplate | None:
    """Busca una plantilla global de sistema por tipo y código."""
    query = select(PrintTemplate).filter_by(company_code=None, document_type=document_type, code=code)
    if for_update:
        query = query.with_for_update()
    return database.session.execute(query).scalars().first()


def _update_system_template(template: PrintTemplate, template_body: str) -> None:
    """Actualiza solo las plantillas de sistema con una versión anterior."""
    if (template.version or 1) < SEED_TEMPLATE_VERSION:
        template.template_body = template_body
        template.stylesheet_body = BASE_CSS
        template.version = SEED_TEMPLATE_VERSION
