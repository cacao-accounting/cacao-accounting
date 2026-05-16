Observaciones generales a los formulación de Compras, Ventas e Inventarios:

Los formularios de estos tres modulos tienen la caracteristica de que a nivel de detalle comparten la gestión de Items.

Por este motivo se ha empleado un framework unificado basado en:

- cacao_accounting/static/js/transaction-form.js
- cacao_accounting/templates/transaction_form_macros.html
- cacao_accounting/templates/detail_view_macros.html

Tambien la implementación de smartselect es importante:

- cacao_accounting/static/js/smart-select.js

El formulario de referencia es el comprobante contable:

- cacao_accounting/contabilidad/templates/contabilidad/journal_nuevo.html
- cacao_accounting/contabilidad/templates/contabilidad/journal.html

Los siguientos lineamientos generales aplican a todos los formularios de Compras, Ventas e Inventarios:

- En los formulario el primer campo seleccionable siempre debe ser el campo de compañia ya que ese es el campo que los demas usan para filtrar.
- El campo de secuencia siempre de estar visible.
- El campo de selección de moneda de la selección siempre debe estar visible
- El breadcrumb siempre debe estar visible para facilitar navegación
- Uniformar encabezado para seguir un layout uniforme:


breadcrump / navigation / section
| Tipo de Documento | |
|---|---|
| Compañía | Secuencia o Serie |
| Moneda | Fecha |
| campos específicos al formulario | campos específicos al formulario |
| campos específicos al formulario | campos específicos al formulario |
| campos específicos al formulario | campos específicos al formulario |
| campos específicos al formulario | campos específicos al formulario |
| Comentario | |

Grid de items

- En el grid de items los campos seleccionables deben usar smarselect para ofrecer una expereciencia de usuario uniforme, principalmente el codigo de producto y la unidad de medida
- El grid de items debe permitir buscar items por codigo y descripción
- En el modal de cada linea del grid de items Cuenta, Centro de Costos, Unidad de Negocio y Proyecto deben usar smart-select
- En el modal En el modal de cada linea del grid de items la relación se debe expresar pot tipo de documento e identificar del documento (usar la secuencia o serie como identificador visible al usuario)

Formularios a revisar:

- /sales/sales-request/new
- /sales/sales-order/new
- /sales/request-for-quotation/new
- /sales/delivery-note/new
- /sales/sales-invoice/new
- /inventory/stock-entry/adjustment-negative/new?purpose=material_transfer
- /inventory/stock-entry/adjustment-negative/new
- /inventory/stock-entry/adjustment-negative/new?purpose=material_issue
- /inventory/stock-entry/adjustment-negative/new?purpose=material_receipt
- /buying/purchase-invoice/new?document_type=purchase_invoice
- /buying/purchase-receipt/new
- /buying/purchase-order/new
- /buying/request-for-quotation/new
- /buying/supplier-quotation/new
- /buying/request-for-quotation/new
- /buying/purchase-request/new

No veo en ningun formulario la implementación de "Actualizar Elementos" en ningún formulario observo la opción de importar lineas de items existentes en otros registros ya existenten que coinciden con el match de Compañia, Tipo de Tercero, Tercero y items pendientes de completar.
