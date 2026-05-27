òRequerimiento formal de desarrollo

Servicio reusable de impresión para Cacao Accounting

1. Objetivo

Implementar un servicio reusable de impresión para Cacao Accounting que permita generar documentos imprimibles en HTML y PDF para las transacciones del sistema, utilizando plantillas administrables en base de datos.

El servicio debe permitir que el administrador del sistema cree, duplique, edite, publique, archive y configure formatos de impresión por tipo de documento, sin que cada módulo implemente su propia lógica de impresión.

El sistema debe soportar:

Plantillas HTML/Jinja2 almacenadas en base de datos.

CSS separado almacenado en base de datos.

Previsualización en iframe.

Exportación a PDF usando WeasyPrint.

Contextos de datos estables, documentados y en inglés.

Helpers, filtros, snippets y documentación para el diseñador de formatos.

Formatos básicos de sistema para cada transacción imprimible.

Seguridad estricta en el renderizado de plantillas.



---

2. Decisiones funcionales obligatorias

2.1 Los formatos son scope del administrador

Los formatos de impresión pertenecen al ámbito administrativo del sistema.

Los usuarios operativos pueden:

Previsualizar documentos.

Imprimir documentos.

Exportar PDF.


Siempre que tengan permiso sobre el documento fuente.

Los usuarios operativos no pueden:

Crear formatos.

Editar formatos.

Duplicar formatos.

Publicar formatos.

Archivar formatos.

Marcar formatos como predeterminados.


Estas acciones quedan reservadas a administradores o usuarios con permisos explícitos de administración de formatos.


---

2.2 El sistema debe incluir formatos básicos

Cacao Accounting debe incluir un formato de impresión básico de sistema para cada transacción imprimible.

Ejemplos mínimos:

Comprobante contable
Comprobante de revaluación
Pago bancario
Nota de débito bancaria
Nota de crédito bancaria
Transferencia bancaria
Factura de venta
Nota de crédito de venta
Nota de débito de venta
Factura de compra
Nota de crédito de compra
Nota de débito de compra
Orden de compra
Entrada de inventario
Salida de inventario
Ajuste de inventario
Transferencia de inventario

Cada formato básico debe sembrarse como plantilla de sistema.

Las plantillas de sistema:

Deben venir publicadas.

Deben estar disponibles por defecto.

No deben editarse directamente.

Pueden duplicarse para crear una plantilla personalizada.



---

2.3 No se guardarán snapshots

El sistema no guardará snapshots de HTML o PDF generados.

Cada vez que se previsualice, imprima o exporte a PDF un documento, el sistema usará siempre la última versión publicada disponible de la plantilla seleccionada o predeterminada.

Implicaciones:

No se almacenará copia congelada del HTML.

No se almacenará copia congelada del PDF.

Si la plantilla cambia, futuras impresiones del mismo documento reflejarán el nuevo formato.

El versionado de plantillas sirve para historial, control administrativo y restauración, no para reproducir impresiones pasadas.



---

3. Alcance

3.1 Incluido

El desarrollo debe incluir:

Módulo reusable printing.

Modelos de datos para plantillas, versiones y logs.

Servicio central de impresión.

Registry de documentos imprimibles.

Context builders por tipo de documento.

Sample context builders por tipo de documento.

Schema de variables disponibles por tipo de documento.

Editor administrativo de HTML/Jinja2.

Editor administrativo de CSS.

Preview en iframe.

Exportación PDF con WeasyPrint.

Validación de plantillas.

Filtros/helpers Jinja2 seguros.

Snippets para diseñador.

Documentación completa en docs/.

Tests unitarios, funcionales y de seguridad.

Seeds de formatos básicos por transacción imprimible.



---

3.2 No incluido en esta fase

No se debe implementar en esta fase:

Diseñador visual drag-and-drop.

Snapshots de PDF o HTML generado.

Firma digital avanzada.

Motor de plantillas externo.

JavaScript dentro de formatos de impresión.

Cálculos contables, fiscales o comerciales dentro de la plantilla.

Editor WYSIWYG complejo.

Almacenamiento histórico de cada documento impreso.



---

4. Arquitectura general

El flujo general debe ser:

Documento fuente
    ↓
Context builder del módulo
    ↓
Contexto serializado y estable
    ↓
Resolución de plantilla publicada
    ↓
Render Jinja2 sandbox
    ↓
Inserción de CSS
    ↓
HTML final
    ↓
Preview iframe / PDF WeasyPrint

La arquitectura debe separar claramente:

Módulo propietario del documento
    └── Construye datos de impresión

Servicio de impresión
    └── Valida, resuelve plantilla, renderiza HTML/PDF

Administrador de formatos
    └── Crea, edita, duplica, publica y archiva plantillas


---

5. Estructura sugerida del módulo

cacao_accounting/
  printing/
    __init__.py
    models.py
    service.py
    registry.py
    context.py
    validators.py
    permissions.py
    filters.py
    snippets.py
    routes.py
    admin_routes.py
    seed.py
    exceptions.py
    templates/
      admin/
        print_template_list.html
        print_template_form.html
        print_template_preview.html


---

6. Modelos de datos

6.1 PrintTemplate

Modelo principal para formatos de impresión.

class PrintTemplate(db.Model):
    __tablename__ = "print_templates"

    id = db.Column(db.Integer, primary_key=True)

    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=True)

    document_type = db.Column(db.String(80), nullable=False)
    code = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)

    template_body = db.Column(db.Text, nullable=False)
    stylesheet_body = db.Column(db.Text, nullable=True)

    paper_size = db.Column(db.String(20), default="letter", nullable=False)
    orientation = db.Column(db.String(20), default="portrait", nullable=False)

    status = db.Column(db.String(20), default="draft", nullable=False)
    is_system = db.Column(db.Boolean, default=False, nullable=False)
    is_default = db.Column(db.Boolean, default=False, nullable=False)

    version = db.Column(db.Integer, default=1, nullable=False)

    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "company_id",
            "document_type",
            "code",
            name="uq_print_template_company_document_code",
        ),
    )


---

6.2 Estados de plantilla

El campo status debe soportar:

draft
published
archived

Reglas:

draft: puede editarse y previsualizarse, pero no usarse como formato oficial.

published: puede usarse para impresión y PDF.

archived: no se usa para nuevas impresiones, pero queda disponible para historial administrativo.


Solo una plantilla published puede ser is_default=True por combinación de:

company_id + document_type


---

6.3 company_id

El campo company_id define el alcance:

company_id = NULL
    Plantilla global del sistema.

company_id != NULL
    Plantilla específica de una compañía.

Reglas:

Las plantillas globales sirven como base.

Las plantillas de compañía permiten personalización.

Una compañía puede usar una plantilla global si no tiene plantilla propia publicada.

Una plantilla global de sistema no debe editarse directamente.



---

6.4 PrintTemplateVersion

Cada vez que una plantilla sea modificada, se debe registrar una versión anterior.

class PrintTemplateVersion(db.Model):
    __tablename__ = "print_template_versions"

    id = db.Column(db.Integer, primary_key=True)

    template_id = db.Column(
        db.Integer,
        db.ForeignKey("print_templates.id"),
        nullable=False,
    )

    version = db.Column(db.Integer, nullable=False)

    template_body = db.Column(db.Text, nullable=False)
    stylesheet_body = db.Column(db.Text, nullable=True)

    paper_size = db.Column(db.String(20), nullable=False)
    orientation = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False)

    changed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    changed_at = db.Column(db.DateTime, nullable=False)

    change_note = db.Column(db.String(255))

Propósito:

Auditar cambios.

Restaurar versiones anteriores.

Revisar historial de modificaciones.

Evitar pérdida accidental de formatos.



---

6.5 PrintJobLog

Debe registrarse cada intento de previsualización, impresión o generación PDF.

class PrintJobLog(db.Model):
    __tablename__ = "print_job_logs"

    id = db.Column(db.Integer, primary_key=True)

    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    document_type = db.Column(db.String(80), nullable=False)
    document_id = db.Column(db.Integer, nullable=False)

    template_id = db.Column(db.Integer, db.ForeignKey("print_templates.id"), nullable=True)
    template_version = db.Column(db.Integer, nullable=True)

    output_format = db.Column(db.String(20), nullable=False)

    rendered_at = db.Column(db.DateTime, nullable=False)

    success = db.Column(db.Boolean, default=True, nullable=False)
    error_message = db.Column(db.Text)

Valores permitidos para output_format:

html_preview
pdf

Importante:

No se debe guardar snapshot del HTML.

No se debe guardar snapshot del PDF.

El log solo registra auditoría operativa.



---

7. Registry de documentos imprimibles

Debe existir un registry en código para declarar qué documentos son imprimibles.

Ejemplo:

PRINTABLE_DOCUMENTS = {
    "sales_invoice": {
        "label": "Factura de venta",
        "module": "ventas",
        "root_context_name": "invoice",
        "permission": "ventas.view_invoice",
        "context_builder": build_sales_invoice_print_context,
        "sample_context_builder": build_sales_invoice_sample_context,
        "schema": SALES_INVOICE_PRINT_SCHEMA,
        "snippets": SALES_INVOICE_SNIPPETS,
    },
    "journal_entry": {
        "label": "Comprobante contable",
        "module": "contabilidad",
        "root_context_name": "journal_entry",
        "permission": "contabilidad.view_journal_entry",
        "context_builder": build_journal_entry_print_context,
        "sample_context_builder": build_journal_entry_sample_context,
        "schema": JOURNAL_ENTRY_PRINT_SCHEMA,
        "snippets": JOURNAL_ENTRY_SNIPPETS,
    },
}

El registry debe ser obligatorio para:

Evitar documentos arbitrarios.

Asociar permisos.

Asociar context builders.

Asociar schemas.

Asociar snippets.

Controlar los tipos de documento disponibles en el editor.



---

8. Context builders

Cada tipo de documento imprimible debe tener un context_builder.

El context_builder recibe:

document_id
user
company
options opcional

Y retorna un diccionario serializado.

Regla obligatoria:

> El contexto de impresión no debe exponer objetos SQLAlchemy crudos.



Correcto:

{
    "invoice": {
        "number": "FAC-000001",
        "grand_total": 1150.00,
    }
}

Incorrecto:

{
    "invoice": invoice_model
}

El contexto debe ser:

Explícito.

Serializable.

Estable.

Documentado.

En inglés.

Seguro para uso en Jinja2.



---

9. Nombres de variables

9.1 Idioma

Todos los nombres de campos disponibles para las plantillas deben estar en inglés.

Correcto:

{{ invoice.date }}
{{ invoice.subtotal }}
{{ invoice.taxes }}
{{ invoice.other_charges }}
{{ invoice.grand_total }}
{{ invoice.customer.legal_name }}
{{ invoice.customer.address }}

Incorrecto:

{{ factura.fecha }}
{{ factura.cliente.razon_social }}
{{ factura.grantotal }}


---

9.2 Formato

Los nombres deben usar snake_case.

Correcto:

grand_total
other_charges
legal_name
commercial_name
unit_of_measure
line_total
printed_at

Incorrecto:

grandTotal
otherCharges
grantotal
razon_social
fecha


---

9.3 Raíces recomendadas por documento

Cada documento debe tener una raíz clara:

sales_invoice        → invoice
purchase_invoice     → invoice o purchase_invoice
journal_entry        → journal_entry
bank_payment         → payment
bank_transfer        → transfer
purchase_order       → purchase_order
sales_order          → sales_order
quote                → quote
inventory_receipt    → receipt
inventory_issue      → issue
inventory_adjustment → adjustment

También deben existir raíces comunes:

company
audit


---

10. Ejemplo de contexto para factura

{
    "company": {
        "name": "Comercial XYZ, S.A.",
        "legal_name": "Comercial XYZ, Sociedad Anónima",
        "tax_id": "J0310000000000",
        "address": "Managua, Nicaragua",
        "phone": "+505 2222 0000",
        "email": "info@example.com",
        "website": "www.example.com",
        "logo_url": "/static/uploads/company/logo.png",
        "default_currency": "NIO",
    },

    "invoice": {
        "number": "FAC-000001",
        "date": "2026-05-26",
        "due_date": "2026-06-25",
        "status": "posted",
        "currency": "NIO",
        "exchange_rate": 1,

        "customer": {
            "code": "CUST-001",
            "legal_name": "Cliente Ejemplo, S.A.",
            "commercial_name": "Cliente Ejemplo",
            "tax_id": "J0310000000001",
            "address": "Carretera a Masaya, Managua",
            "phone": "+505 8888 0000",
            "email": "compras@cliente.com",
        },

        "items": [
            {
                "line_number": 1,
                "item_code": "PROD-001",
                "description": "Producto de ejemplo",
                "quantity": 2,
                "unit_of_measure": "UND",
                "unit_price": 500.00,
                "discount": 0.00,
                "subtotal": 1000.00,
                "taxes": 150.00,
                "other_charges": 0.00,
                "line_total": 1150.00,
            }
        ],

        "subtotal": 1000.00,
        "discount": 0.00,
        "taxes": 150.00,
        "other_charges": 0.00,
        "grand_total": 1150.00,

        "amount_in_words": "Mil ciento cincuenta córdobas netos",
        "notes": "Gracias por su compra.",
    },

    "audit": {
        "created_by": "admin",
        "posted_by": "admin",
        "printed_by": "William",
        "printed_at": "2026-05-26 10:15",
    },
}


---

11. Sample context builders

Cada documento imprimible debe tener un sample_context_builder.

Objetivo:

Permitir previsualizar plantillas sin seleccionar documento real.

Permitir validar plantillas al guardar o publicar.

Permitir mostrar ejemplos al diseñador.

Permitir tests estables.


Ejemplo:

def build_sales_invoice_sample_context(user=None, company=None):
    return {
        "company": {...},
        "invoice": {...},
        "audit": {...},
    }

El sample context debe cubrir:

Encabezado.

Líneas/items.

Totales.

Impuestos.

Cargos adicionales.

Datos de cliente/proveedor.

Auditoría.

Estados relevantes.



---

12. Schema de variables

Cada documento imprimible debe declarar un schema de variables disponibles.

Ejemplo para factura:

SALES_INVOICE_PRINT_SCHEMA = {
    "company": {
        "name": "Company display name",
        "legal_name": "Company legal name",
        "tax_id": "Company tax identification number",
        "address": "Company address",
        "phone": "Company phone number",
        "email": "Company email address",
        "website": "Company website",
        "logo_url": "Company logo URL",
        "default_currency": "Company default currency code",
    },
    "invoice": {
        "number": "Invoice number",
        "date": "Invoice date",
        "due_date": "Invoice due date",
        "status": "Invoice status",
        "currency": "Invoice currency code",
        "exchange_rate": "Exchange rate used by the invoice",
        "subtotal": "Invoice subtotal before taxes and charges",
        "discount": "Invoice discount amount",
        "taxes": "Total tax amount",
        "other_charges": "Total additional charges",
        "grand_total": "Final invoice total",
        "amount_in_words": "Grand total written in words",
        "notes": "Invoice notes",
        "customer": {
            "code": "Customer code",
            "legal_name": "Customer legal name",
            "commercial_name": "Customer commercial name",
            "tax_id": "Customer tax identification number",
            "address": "Customer address",
            "phone": "Customer phone number",
            "email": "Customer email address",
        },
        "items[]": {
            "line_number": "Line number",
            "item_code": "Item or service code",
            "description": "Line description",
            "quantity": "Quantity",
            "unit_of_measure": "Unit of measure",
            "unit_price": "Unit price",
            "discount": "Line discount amount",
            "subtotal": "Line subtotal",
            "taxes": "Line taxes",
            "other_charges": "Line additional charges",
            "line_total": "Final line total",
        },
    },
    "audit": {
        "created_by": "User who created the document",
        "posted_by": "User who posted the document",
        "printed_by": "User who printed the document",
        "printed_at": "Print date and time",
    },
}

Este schema alimentará:

Panel de variables disponibles.

Documentación.

Validación.

Ayuda contextual del editor.



---

13. Renderizado Jinja2

13.1 Entorno seguro

El renderizado debe usar SandboxedEnvironment.

from jinja2 import BaseLoader, StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

env = SandboxedEnvironment(
    loader=BaseLoader(),
    autoescape=True,
    undefined=StrictUndefined,
)

Reglas:

Usar StrictUndefined.

Usar autoescape.

No exponer objetos internos.

No exponer request.

No exponer session.

No exponer config.

No exponer current_app.

No exponer g.

No exponer db.

No exponer modelos SQLAlchemy.

No exponer funciones Python arbitrarias.



---

13.2 Renderizado desde DB

El servicio no debe usar render_template() para plantillas de impresión, porque la plantilla viene de DB.

Debe usar:

template = env.from_string(print_template.template_body)
rendered_body = template.render(**context)


---

14. CSS separado en DB

Cada PrintTemplate debe tener:

template_body      HTML/Jinja2
stylesheet_body    CSS

Reglas:

template_body contiene estructura HTML y variables Jinja2.

stylesheet_body contiene únicamente CSS.

Ambos viven en DB.

Ambos se versionan juntos.

Ambos se duplican juntos.

Ambos se validan juntos.

Ambos se usan para preview y PDF.



---

14.1 HTML final

El servicio debe construir el HTML final insertando el CSS asociado.

def build_print_html(rendered_body: str, stylesheet_body: str | None) -> str:
    css = stylesheet_body or ""

    return f"""
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
        {css}
        </style>
    </head>
    <body>
        {rendered_body}
    </body>
    </html>
    """


---

14.2 Reglas CSS

El CSS debe estar orientado a impresión y compatible con WeasyPrint.

Debe documentarse el uso recomendado de:

@page {
    size: letter portrait;
    margin: 15mm;
}

thead {
    display: table-header-group;
}

tfoot {
    display: table-footer-group;
}

.page-break {
    page-break-before: always;
}

.text-right {
    text-align: right;
}

No se debe depender de:

JavaScript.

Animaciones.

CSS experimental.

Frameworks externos.

Recursos remotos no controlados.

Layouts innecesariamente complejos.



---

15. Prohibición de JavaScript

Las plantillas de impresión no deben soportar JavaScript.

Reglas:

No permitir <script>.

No permitir eventos inline como onclick, onload, etc.

No depender de JS para preview.

No depender de JS para PDF.

El iframe de preview debe usar sandbox sin scripts.


Ejemplo recomendado:

<iframe sandbox="" src="..."></iframe>

Si se requiere acceso controlado a recursos del mismo origen, evaluar cuidadosamente:

<iframe sandbox="allow-same-origin"></iframe>

No habilitar:

allow-scripts


---

16. Filtros y helpers Jinja2

El entorno Jinja2 debe incluir filtros seguros y documentados.

Filtros mínimos:

money
date
datetime
number
percent
default_text
status_label

Ejemplo de uso:

{{ invoice.grand_total | money(invoice.currency) }}
{{ invoice.date | date }}
{{ audit.printed_at | datetime }}
{{ item.quantity | number(2) }}
{{ invoice.status | status_label }}
{{ invoice.notes | default_text("-") }}


---

16.1 money

Debe formatear valores monetarios.

{{ invoice.grand_total | money(invoice.currency) }}

Salida esperada:

NIO 1,150.00


---

16.2 date

Debe formatear fechas.

{{ invoice.date | date }}

Salida esperada:

26/05/2026


---

16.3 datetime

Debe formatear fecha y hora.

{{ audit.printed_at | datetime }}

Salida esperada:

26/05/2026 10:15


---

16.4 number

Debe formatear números con decimales.

{{ item.quantity | number(2) }}

Salida esperada:

2.00


---

16.5 percent

Debe formatear porcentajes.

{{ tax.rate | percent }}

Salida esperada:

15%


---

16.6 default_text

Debe mostrar un valor alternativo cuando un campo venga vacío.

{{ invoice.notes | default_text("-") }}


---

16.7 status_label

Debe convertir estados técnicos a etiquetas legibles.

Ejemplo:

draft     → Draft
posted    → Posted
void      → Void
cancelled → Cancelled


---

17. Prohibición de cálculos contables/fiscales en templates

Las plantillas son únicamente de presentación.

No deben calcular:

Impuestos.

Retenciones.

Subtotales.

Descuentos.

Cargos.

Totales.

Diferencias cambiarias.

Asientos contables.

Distribuciones de costo.

Prorrateos.


Incorrecto:

{{ invoice.subtotal * 0.15 }}

Correcto:

{{ invoice.taxes | money(invoice.currency) }}

Regla:

> Todo cálculo contable, fiscal, financiero o comercial debe venir resuelto desde backend en el contexto de impresión.




---

18. Snippets para diseñador

El editor debe incluir snippets insertables por tipo de documento.

Ejemplos mínimos:

18.1 Encabezado de compañía

<div class="company-header">
    <img src="{{ company.logo_url }}" alt="Logo">
    <h1>{{ company.name }}</h1>
    <p>{{ company.tax_id }}</p>
    <p>{{ company.address }}</p>
</div>


---

18.2 Tabla de items de factura

<table class="document-lines">
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
        {% for item in invoice.items %}
        <tr>
            <td>{{ item.item_code }}</td>
            <td>{{ item.description }}</td>
            <td class="text-right">{{ item.quantity | number(2) }}</td>
            <td class="text-right">{{ item.unit_price | money(invoice.currency) }}</td>
            <td class="text-right">{{ item.line_total | money(invoice.currency) }}</td>
        </tr>
        {% endfor %}
    </tbody>
</table>


---

18.3 Totales de factura

<table class="totals-table">
    <tr>
        <td>Subtotal</td>
        <td class="text-right">{{ invoice.subtotal | money(invoice.currency) }}</td>
    </tr>
    <tr>
        <td>Taxes</td>
        <td class="text-right">{{ invoice.taxes | money(invoice.currency) }}</td>
    </tr>
    <tr>
        <td>Other charges</td>
        <td class="text-right">{{ invoice.other_charges | money(invoice.currency) }}</td>
    </tr>
    <tr class="grand-total">
        <td>Grand total</td>
        <td class="text-right">{{ invoice.grand_total | money(invoice.currency) }}</td>
    </tr>
</table>


---

18.4 Auditoría

<div class="audit-footer">
    <p>Created by: {{ audit.created_by }}</p>
    <p>Posted by: {{ audit.posted_by }}</p>
    <p>Printed by: {{ audit.printed_by }}</p>
    <p>Printed at: {{ audit.printed_at | datetime }}</p>
</div>


---

19. Servicio de impresión

Debe implementarse una clase o conjunto de funciones centralizadas.

Ejemplo:

class PrintService:
    def render_preview_html(
        self,
        document_type: str,
        document_id: int | None,
        user,
        template_id: int | None = None,
        sample: bool = False,
    ) -> str:
        ...

    def render_pdf(
        self,
        document_type: str,
        document_id: int,
        user,
        template_id: int | None = None,
    ) -> bytes:
        ...

    def validate_template(
        self,
        template_body: str,
        stylesheet_body: str | None,
        document_type: str,
    ) -> ValidationResult:
        ...

    def resolve_template(
        self,
        document_type: str,
        company_id: int,
        template_id: int | None = None,
    ) -> PrintTemplate:
        ...


---

20. Resolución de plantilla

Cuando se imprima un documento, el sistema debe resolver la plantilla así:

1. Si se envía template_id:
   usar esa plantilla si:
   - existe,
   - está published,
   - corresponde al document_type,
   - pertenece a la compañía o es global,
   - el usuario tiene permiso.

2. Si no se envía template_id:
   buscar plantilla default published de la compañía.

3. Si no existe:
   buscar plantilla default published global.

4. Si no existe:
   retornar error controlado.

Pseudocódigo:

def resolve_template(document_type, company_id, template_id=None):
    if template_id:
        template = PrintTemplate.query.get_or_404(template_id)
        validate_template_access(template, document_type, company_id)
        return template

    company_default = PrintTemplate.query.filter_by(
        company_id=company_id,
        document_type=document_type,
        status="published",
        is_default=True,
    ).first()

    if company_default:
        return company_default

    global_default = PrintTemplate.query.filter_by(
        company_id=None,
        document_type=document_type,
        status="published",
        is_default=True,
    ).first()

    if global_default:
        return global_default

    raise PrintTemplateNotFoundError()


---

21. Validación de plantillas

Antes de publicar una plantilla o marcarla como default, el sistema debe validar:

Sintaxis Jinja2.

Renderizado exitoso con sample context.

Uso de variables disponibles.

CSS no vacío si el formato lo requiere.

Ausencia de <script>.

Ausencia de eventos inline peligrosos.

Generación HTML exitosa.

Generación PDF exitosa, al menos en validación explícita o publicación.


Validación mínima:

Guardar draft:
    validar sintaxis básica.

Publicar:
    validar sintaxis,
    render con sample context,
    validar restricciones de seguridad,
    validar PDF con WeasyPrint.

Marcar default:
    solo si está published y valida correctamente.

El sistema debe mostrar errores claros.

Ejemplo:

Template validation failed:
'invoice.grantotal' is undefined.


---

22. UI administrativa

22.1 Menú

Agregar entrada:

Administración > Formatos de impresión


---

22.2 Lista de formatos

La lista debe mostrar:

Documento
Código
Nombre
Compañía / Global
Estado
Sistema
Default
Versión
Última modificación
Acciones

Acciones:

Ver
Editar
Duplicar
Previsualizar
Publicar
Archivar
Marcar default
Ver historial
Restaurar versión

Reglas:

Plantillas de sistema no se editan directamente.

Plantillas de sistema no se eliminan.

Plantillas de sistema pueden duplicarse.

Plantillas archivadas no pueden marcarse como default.

Solo plantillas publicadas pueden marcarse como default.



---

22.3 Formulario de edición

El formulario debe incluir:

Document type
Code
Name
Description
Paper size
Orientation
Status
Is default
Template body HTML/Jinja2
Stylesheet body CSS

Diseño recomendado:

┌───────────────────────────────────────────────┬──────────────────────────────┐
│ Editor HTML/Jinja2                            │ Preview iframe               │
│                                               │                              │
│                                               │                              │
├───────────────────────────────────────────────┤                              │
│ Editor CSS                                    │                              │
│                                               │                              │
└───────────────────────────────────────────────┴──────────────────────────────┘

Panel inferior:
- Available variables
- Filters
- Snippets
- Validation errors


---

22.4 Panel de ayuda

Debe mostrar, según document_type:

Variables disponibles.

Descripción de cada variable.

Filtros disponibles.

Snippets.

Ejemplos de loops.

Notas de CSS/WeasyPrint.

Restricciones de seguridad.



---

23. Preview en iframe

23.1 Modos de preview

Debe soportar:

Preview con datos de muestra
Preview con documento real autorizado


---

23.2 Preview con datos de muestra

Debe usar el sample_context_builder.

Este modo no requiere permiso sobre documentos reales.

Sí requiere permiso para administrar o visualizar plantillas.


---

23.3 Preview con documento real

Debe usar el context_builder real.

Reglas:

El usuario debe tener permiso sobre el documento.

El documento debe pertenecer a una compañía permitida para el usuario.

El document_type debe coincidir con la plantilla.



---

23.4 Endpoint sugerido

GET /admin/print-templates/<template_id>/preview?sample=1
GET /admin/print-templates/<template_id>/preview?document_id=123

El endpoint devuelve HTML renderizado para iframe.


---

24. PDF con WeasyPrint

24.1 Endpoint sugerido

GET /print/<document_type>/<int:document_id>/pdf

Parámetro opcional:

?template_id=10

Si no se envía template_id, se usa la plantilla predeterminada.


---

24.2 Flujo PDF

context = context_builder(document_id=document_id, user=current_user)
template = resolve_template(document_type, company_id, template_id)
rendered_body = render_jinja(template.template_body, context)
html = build_print_html(rendered_body, template.stylesheet_body)

pdf = HTML(
    string=html,
    base_url=base_url,
).write_pdf()


---

24.3 Base URL y assets

El servicio debe permitir resolver assets seguros:

Logo de compañía.

QR.

Firmas.

Sellos.

Imágenes autorizadas.


La plantilla debe usar URLs expuestas en el contexto:

<img src="{{ company.logo_url }}">

No se debe permitir acceso arbitrario al filesystem.


---

25. Permisos

Permisos sugeridos:

printing.template.view
printing.template.create
printing.template.edit
printing.template.duplicate
printing.template.publish
printing.template.archive
printing.template.set_default
printing.template.restore_version

printing.document.preview
printing.document.pdf

Reglas:

Administrar plantillas requiere permisos administrativos.

Imprimir un documento requiere permiso sobre ese documento.

Editar una plantilla no implica permiso para ver documentos reales.

Previsualizar con sample context no requiere acceso a documentos reales.

Previsualizar con documento real requiere permiso sobre ese documento.

Exportar PDF requiere permiso sobre ese documento.



---

26. Seguridad

26.1 Reglas obligatorias

El servicio debe proteger contra:

Acceso a documentos de otra compañía.

Acceso a módulos sin permiso.

Uso de document_type no registrado.

Uso de template_id de otro document_type.

Uso de template_id de otra compañía no permitida.

Ejecución de código en Jinja2.

Acceso a objetos internos de Flask.

Acceso a objetos SQLAlchemy.

JavaScript en preview.

Rutas arbitrarias de archivos.

Variables inexistentes silenciosas.



---

26.2 Reglas de template

No permitir:

<script>

No permitir atributos:

onclick
onload
onerror
onmouseover
onfocus

No exponer:

request
session
config
current_app
g
db
models

No pasar objetos con métodos peligrosos.


---

27. Documentación en docs/

Debe generarse documentación comprensiva bajo:

docs/
  print-formats/
    index.md
    designer-guide.md
    jinja-context-reference.md
    css-guide.md
    filters-and-helpers.md
    snippets.md
    developer-guide.md
    examples/
      sales-invoice.md
      journal-entry.md
      bank-payment.md


---

27.1 index.md

Debe explicar:

Qué son los formatos de impresión.

Qué puede hacer el administrador.

Flujo general de impresión.

Diferencia entre preview y PDF.

Alcance administrativo.

Decisión de no guardar snapshots.



---

27.2 designer-guide.md

Debe explicar:

Cómo crear una plantilla.

Cómo duplicar una plantilla de sistema.

Cómo editar HTML/Jinja2.

Cómo editar CSS.

Cómo validar.

Cómo previsualizar.

Cómo publicar.

Cómo marcar default.

Cómo archivar.



---

27.3 jinja-context-reference.md

Debe documentar variables por document_type.

Cada documento debe incluir:

Root context name.

Variables comunes.

Variables específicas.

Colecciones.

Ejemplos de loops.



---

27.4 css-guide.md

Debe explicar:

CSS soportado por WeasyPrint.

Uso de @page.

Tamaños de papel.

Márgenes.

Saltos de página.

Tablas largas.

Encabezados repetibles.

Buenas prácticas.

Limitaciones.



---

27.5 filters-and-helpers.md

Debe documentar:

money

date

datetime

number

percent

default_text

status_label


Con ejemplos.


---

27.6 snippets.md

Debe incluir snippets reutilizables:

Encabezado de compañía.

Tabla de líneas.

Bloque de totales.

Bloque de auditoría.

Firmas.

Marca de agua para borrador/anulado.

QR opcional.



---

27.7 developer-guide.md

Debe explicar cómo un desarrollador registra un nuevo documento imprimible:

Agregar document_type al registry.

Crear context_builder.

Crear sample_context_builder.

Crear schema.

Crear snippets.

Crear seed de plantilla básica.

Agregar tests.



---

28. Seeds de plantillas básicas

Debe existir un mecanismo para sembrar plantillas de sistema.

Ejemplo:

def seed_print_templates():
    ensure_system_template(
        document_type="sales_invoice",
        code="system_default_sales_invoice",
        name="Factura de venta básica",
        template_body=SALES_INVOICE_TEMPLATE,
        stylesheet_body=SALES_INVOICE_CSS,
        paper_size="letter",
        orientation="portrait",
        is_default=True,
        status="published",
    )

Reglas:

El seed debe ser idempotente.

No debe sobrescribir personalizaciones de compañía.

Puede actualizar plantillas de sistema si se maneja una versión controlada.

Debe garantizar que cada transacción imprimible tenga al menos una plantilla básica publicada.



---

29. Comportamiento en modo desktop/cloud

El servicio debe funcionar tanto en modo desktop como cloud.

En modo desktop:

Solo existirá un usuario administrador.

Los formatos siguen siendo scope del administrador.

Las plantillas pueden ser globales o de la única compañía disponible.

No debe requerir servicios externos.


En modo cloud:

Debe respetar permisos y compañías.

Debe permitir plantillas por compañía.

Debe impedir acceso cruzado entre compañías.



---

30. Tests requeridos

30.1 Tests de modelos

Validar:

Creación de PrintTemplate.

Unicidad de company_id + document_type + code.

Estados válidos.

Versionado.

Log de impresión.



---

30.2 Tests del servicio

Validar:

Resolución de plantilla por template_id.

Resolución de plantilla default de compañía.

Fallback a plantilla global.

Error controlado si no hay plantilla.

Render HTML exitoso.

Render PDF exitoso.

Uso de CSS en HTML final.

Registro de PrintJobLog.

Uso de última versión publicada.



---

30.3 Tests de seguridad

Validar:

No se puede usar document_type no registrado.

No se puede usar plantilla de otro document_type.

No se puede usar plantilla de otra compañía sin permiso.

No se puede imprimir documento de otra compañía.

No se puede renderizar <script>.

No se puede usar variable inexistente sin error.

No se exponen objetos Flask internos.

No se exponen objetos SQLAlchemy.

No se permite JavaScript en iframe.



---

30.4 Tests de permisos

Validar:

Usuario sin permiso no puede administrar plantillas.

Usuario con permiso operativo puede imprimir documento autorizado.

Usuario con permiso operativo no puede editar plantilla.

Administrador puede crear/duplicar/publicar/archivar.

Preview con documento real requiere permiso sobre documento.

Preview con sample context no requiere permiso sobre documentos reales.



---

30.5 Tests por documento imprimible

Para cada document_type registrado:

Existe plantilla básica seed.

Existe schema.

Existe sample context.

El sample context renderiza.

El PDF se genera.

El HTML contiene datos esperados.

No quedan variables sin resolver.



---

30.6 Tests de documentación

Validar que existan los archivos mínimos en docs/print-formats/.

Validar que al registrar un nuevo document_type, exista documentación o referencia generada/manual para sus variables.


---

31. Criterios de aceptación

La implementación se considera completa cuando:

1. Existe módulo reusable printing.


2. Las plantillas HTML/Jinja2 se almacenan en DB.


3. El CSS se almacena separado en DB.


4. HTML y CSS se versionan juntos.


5. El servicio renderiza preview HTML.


6. El preview se muestra en iframe sandbox.


7. El servicio genera PDF con WeasyPrint.


8. Existen plantillas básicas de sistema para cada transacción imprimible.


9. Las plantillas de sistema no se editan directamente.


10. Las plantillas de sistema pueden duplicarse.


11. El administrador puede crear, editar, duplicar, publicar, archivar y marcar default.


12. Los usuarios operativos pueden imprimir solo documentos autorizados.


13. El renderizado usa SandboxedEnvironment.


14. El renderizado usa StrictUndefined.


15. No se exponen objetos SQLAlchemy al template.


16. No se expone contexto Flask interno al template.


17. No se permite JavaScript en plantillas.


18. No se hacen cálculos contables/fiscales en templates.


19. Cada document_type tiene context builder.


20. Cada document_type tiene sample context builder.


21. Cada document_type tiene schema de variables.


22. Las variables están en inglés y snake_case.


23. Existen filtros/helpers documentados.


24. Existen snippets reutilizables.


25. Existe documentación comprensiva bajo docs/print-formats/.


26. No se guardan snapshots de HTML ni PDF.


27. Siempre se usa la última versión publicada disponible de la plantilla.


28. Existen tests de modelos, servicio, seguridad, permisos y renderizado.




---

32. Plan de implementación recomendado

Fase 1: Base técnica

Implementar:

Modelos PrintTemplate, PrintTemplateVersion, PrintJobLog.

Registry PRINTABLE_DOCUMENTS.

PrintService.

Render Jinja2 sandbox.

Render PDF con WeasyPrint.

Inserción de CSS en HTML final.

Validación básica.

Log de impresión.



---

Fase 2: Administración

Implementar:

Lista de formatos.

Crear plantilla.

Editar plantilla.

Duplicar plantilla.

Publicar plantilla.

Archivar plantilla.

Marcar default.

Ver historial.

Restaurar versión.



---

Fase 3: Preview y diseñador

Implementar:

Preview en iframe.

Preview con sample context.

Preview con documento real autorizado.

Panel de variables disponibles.

Panel de filtros.

Panel de snippets.

Validación visual de errores.



---

Fase 4: Seeds y documentos iniciales

Implementar formatos básicos para:

Comprobante contable.

Pago bancario.

Transferencia bancaria.

Factura de venta.

Factura de compra.

Orden de compra.

Movimiento de inventario.


Luego extender al resto de transacciones.


---

Fase 5: Documentación y pruebas

Implementar:

Documentación en docs/print-formats/.

Tests unitarios.

Tests funcionales.

Tests de seguridad.

Tests por documento imprimible.

Tests de PDF no vacío.



---

33. Resumen ejecutivo

El servicio de impresión de Cacao Accounting debe ser una capacidad transversal del sistema.

Su diseño final queda definido así:

PrintTemplate en DB
  ├── template_body HTML/Jinja2
  ├── stylesheet_body CSS
  ├── document_type
  ├── company_id opcional
  ├── status
  ├── version
  └── default/system flags

PrintableDocumentRegistry en código
  ├── context_builder
  ├── sample_context_builder
  ├── schema
  ├── snippets
  └── permission

PrintService
  ├── resolve_template
  ├── validate_template
  ├── render_html
  ├── render_pdf
  └── log_print_job

Print Designer UI
  ├── HTML/Jinja2 editor
  ├── CSS editor
  ├── iframe preview
  ├── variables
  ├── filters
  ├── snippets
  └── validation errors

Este diseño permite formatos flexibles y administrables, mantiene el control técnico del sistema, evita sobreingeniería y protege la integridad contable al impedir que las plantillas realicen cálculos o accedan a objetos internos.
