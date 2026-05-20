Requerimiento técnico: Importación de líneas de detalle

1. Objetivo

Implementar una funcionalidad reutilizable para importar líneas de detalle dentro de documentos existentes o en edición, mediante pegado desde hojas de cálculo o carga de archivo .xlsx, validando las líneas contra backend antes de insertarlas en el formulario.

La funcionalidad no debe crear documentos completos ni guardar automáticamente el registro.


---

2. Alcance funcional

2.1 Documentos objetivo iniciales

Prioridad de implementación:

1. Solicitud de compra


2. Orden de compra


3. Cotización de venta


4. Orden de venta


5. Comprobante contable


6. Facturas


7. Bancos / inventario



La prioridad inicial debe enfocarse en documentos que inician procesos:

Source to Pay:
Solicitud de compra → Orden de compra → Recepción → Factura proveedor → Pago

Order to Cash:
Cotización → Orden de venta → Entrega → Factura cliente → Cobro


---

3. UX requerida

Cada formulario con líneas de detalle debe incluir un botón:

Importar líneas

Al hacer clic, se abre un modal.


---

4. Modal de importación

4.1 Contenido del modal

El modal debe mostrar:

Nombre del documento.

Columnas aceptadas.

Columnas requeridas.

Área para pegar desde Excel/LibreOffice/Google Sheets.

Opción para descargar plantilla .xlsx.

Opción para cargar archivo .xlsx.

Vista previa de líneas parseadas.

Errores por fila y columna.

Nota visual indicando:


Las líneas importadas se agregarán al final del detalle actual.


---

5. Estados del modal

5.1 Estado inicial

Cancelar | Validar

El botón Insertar líneas no debe mostrarse inicialmente.


---

5.2 Después de pegar o cargar archivo

Cancelar | Validar

El usuario puede revisar la vista previa.


---

5.3 Después de validación fallida

Cancelar | Validar

Se muestran errores por fila/campo.


---

5.4 Después de validación exitosa

Cancelar | Insertar líneas

El botón Validar se oculta y aparece Insertar líneas.


---

5.5 Si el usuario modifica datos después de validar

El estado debe volver automáticamente a:

Cancelar | Validar

La validación previa queda invalidada.


---

6. Reglas funcionales

6.1 Importar líneas no guarda el documento

La acción Insertar líneas solo agrega líneas al formulario actual.

El guardado final debe hacerse usando el botón normal del documento.

Importar líneas ≠ Guardar documento


---

6.2 Cancelar

La acción Cancelar debe cerrar el modal sin modificar el formulario.


---

6.3 Insertar líneas

La acción Insertar líneas solo debe estar disponible si el backend validó correctamente todas las líneas.

Al insertar:

Se agregan las líneas al detalle del formulario.

Se recalculan totales visuales.

Se disparan eventos normales del formulario.

El documento queda pendiente de guardar.



---

7. Regla crítica: append-only

La funcionalidad de importación debe ser estrictamente append-only.

7.1 Comportamiento obligatorio

Las líneas importadas:

Deben agregarse al final del detalle.

No deben reemplazar líneas existentes.

No deben borrar líneas existentes.

No deben modificar líneas existentes.

No deben reordenar líneas existentes.


7.2 Ejemplo esperado

Si el documento tiene:

3 líneas manuales

Y el usuario importa:

10 líneas válidas

El resultado debe ser:

13 líneas totales

Las líneas originales deben permanecer intactas.


---

8. Arquitectura propuesta

8.1 Frontend

Crear una librería JavaScript reutilizable:

lineImport({
  doctype: "purchase_request",
  targetTable: "#items-table",
  context: {
    company_id: 1,
    currency_id: 2
  }
})

La librería frontend no debe contener lógica específica por documento.

Debe obtener del backend el schema de columnas soportadas.


---

8.2 Backend

Crear un registro central de schemas:

LineImportSchemaRegistry

Cada documento debe registrar su definición:

purchase_request
purchase_order
sales_quote
sales_order
journal_entry
purchase_invoice
sales_invoice
bank_transaction


---

9. API requerida

9.1 Obtener schema de importación

GET /api/line-import/schema?doctype=purchase_request

Respuesta esperada:

{
  "doctype": "purchase_request",
  "label": "Solicitud de compra",
  "columns": [
    {
      "key": "item_code",
      "label": "Artículo",
      "required": true,
      "type": "string",
      "aliases": ["producto", "item", "codigo", "código"]
    },
    {
      "key": "description",
      "label": "Descripción",
      "required": false,
      "type": "string"
    },
    {
      "key": "quantity",
      "label": "Cantidad",
      "required": true,
      "type": "decimal"
    },
    {
      "key": "uom",
      "label": "Unidad",
      "required": true,
      "type": "string"
    },
    {
      "key": "required_date",
      "label": "Fecha requerida",
      "required": false,
      "type": "date"
    }
  ]
}


---

9.2 Validar líneas antes de insertar

POST /api/line-import/validate

Payload:

{
  "doctype": "purchase_request",
  "context": {
    "company_id": 1,
    "currency_id": 2
  },
  "rows": [
    {
      "item_code": "ITEM-001",
      "description": "Laptop",
      "quantity": 2,
      "uom": "Unidad",
      "required_date": "2026-05-20"
    }
  ]
}

Respuesta exitosa:

{
  "valid": true,
  "rows": [
    {
      "item_id": 15,
      "item_code": "ITEM-001",
      "description": "Laptop",
      "quantity": 2,
      "uom_id": 1,
      "uom": "Unidad",
      "required_date": "2026-05-20"
    }
  ],
  "errors": []
}

Respuesta con errores:

{
  "valid": false,
  "rows": [],
  "errors": [
    {
      "row": 3,
      "field": "item_code",
      "message": "El artículo no existe."
    },
    {
      "row": 5,
      "field": "quantity",
      "message": "La cantidad debe ser mayor que cero."
    }
  ]
}


---

10. Procesamiento frontend

La librería debe soportar:

10.1 Pegado desde hoja de cálculo

El usuario puede copiar desde:

Excel

LibreOffice Calc

Google Sheets


Y pegar directamente en el modal.

El frontend debe interpretar:

Tabulaciones como columnas.

Saltos de línea como filas.

Primera fila como encabezado, cuando aplique.



---

10.2 Carga de archivo .xlsx

Solo se soporta .xlsx en la primera versión.

No se soporta inicialmente:

.xls

.ods

.csv

importación asíncrona

workers

procesamiento backend de archivos



---

10.3 Plantilla .xlsx

El frontend debe generar o descargar una plantilla basada en el schema enviado por backend.

La plantilla debe incluir:

Encabezados de columnas.

Indicador de columnas requeridas.

Opcionalmente una fila de ejemplo.



---

11. Validaciones

11.1 Validación frontend básica

El frontend puede validar:

Columnas requeridas presentes.

Tipos simples.

Filas vacías.

Números inválidos.

Fechas inválidas.

Columnas desconocidas.

Datos faltantes.


Estas validaciones son solo auxiliares.


---

11.2 Validación backend obligatoria

El backend es la autoridad.

Debe validar:

Permisos del usuario.

Compañía.

Documento soportado.

Campos requeridos.

Existencia de productos.

Existencia de cuentas contables.

Unidades de medida.

Impuestos.

Centros de costo.

Proyectos.

Bodegas.

Moneda.

Reglas contables.

Reglas del documento.

Cantidades mayores que cero.

Montos válidos.

Compatibilidad con el contexto del documento.



---

12. Contrato de columnas

Cada columna debe definirse con metadata mínima:

{
  "key": "quantity",
  "label": "Cantidad",
  "required": true,
  "type": "decimal",
  "aliases": ["cantidad", "qty"],
  "default": null,
  "help": "Cantidad solicitada"
}

Tipos soportados inicialmente:

string
decimal
integer
date
boolean
currency


---

13. Seguridad

La funcionalidad debe cumplir:

No confiar en datos validados solo por frontend.

Validar permisos en backend.

Validar acceso a compañía.

No guardar archivos subidos.

No persistir líneas hasta que el usuario guarde el documento.

Limitar cantidad máxima de filas por importación.

Rechazar archivos que no sean .xlsx.

Manejar errores sin exponer trazas internas.


Límite inicial recomendado:

500 líneas por importación client-side


---

14. Comportamiento esperado por documento

14.1 Solicitud de compra

Columnas mínimas:

Artículo
Descripción
Cantidad
Unidad
Fecha requerida
Centro de costo
Proyecto


---

14.2 Orden de compra

Columnas mínimas:

Artículo
Descripción
Cantidad
Unidad
Precio
Impuesto
Centro de costo
Proyecto
Fecha requerida


---

14.3 Cotización de venta

Columnas mínimas:

Artículo
Descripción
Cantidad
Unidad
Precio
Descuento
Impuesto


---

14.4 Orden de venta

Columnas mínimas:

Artículo
Descripción
Cantidad
Unidad
Precio
Descuento
Impuesto
Bodega
Fecha de entrega


---

14.5 Comprobante contable

Columnas mínimas:

Cuenta
Descripción
Débito
Crédito
Centro de costo
Proyecto
Referencia


---

15. Criterios de aceptación

La implementación se considera completa cuando:

1. Existe botón Importar líneas en los documentos priorizados.


2. El modal carga el schema desde backend según doctype.


3. El modal muestra columnas soportadas y requeridas.


4. El usuario puede pegar datos desde una hoja de cálculo.


5. El usuario puede descargar plantilla .xlsx.


6. El usuario puede subir plantilla .xlsx.


7. El frontend parsea datos y muestra vista previa.


8. El modal inicia mostrando solo Cancelar y Validar.


9. El botón Insertar líneas no aparece antes de validar.


10. La validación se ejecuta en backend.


11. Los errores se muestran por fila y campo.


12. Si hay errores, no se permite insertar líneas.


13. Si la validación es exitosa, se oculta Validar y aparece Insertar líneas.


14. Si el usuario modifica datos después de validar, debe validar nuevamente.


15. Insertar líneas agrega datos al formulario, pero no guarda el documento.


16. Cancelar no modifica el formulario.


17. El guardado final sigue usando el flujo normal del documento.


18. El backend vuelve a validar el documento completo al guardar.


19. Insertar líneas debe ser estrictamente append-only.


20. Las líneas existentes antes de la importación deben conservarse intactas.


21. Las líneas importadas deben agregarse al final del detalle.


22. Cancelar o fallar validación no debe modificar líneas existentes.




---

16. No incluido en la primera versión

Queda fuera del alcance inicial:

Importación masiva de documentos completos.

Procesamiento backend de archivos.

Workers.

Colas.

.csv.

.xls.

.ods.

Guardado automático.

Importación asíncrona.

Mapeo visual avanzado de columnas.

Transformaciones complejas de datos.



---

17. Resultado esperado

Una funcionalidad transversal llamada Importar líneas, basada en una librería frontend genérica y schemas definidos por backend, que permita reducir drásticamente la digitación manual en documentos de compra, venta, contabilidad e inventario, sin comprometer la validación contable ni la seguridad del sistema.
