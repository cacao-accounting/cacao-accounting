Requerimiento Técnico — Servicio Centralizado de Importación Tabular

Proyecto: Cacao Accounting

1. Objetivo

Implementar un servicio centralizado de importación tabular para Cacao Accounting, capaz de importar registros masivos desde archivos:

CSV
XLS
XLSX
ODS

El servicio debe soportar:

Importaciones simples.

Importaciones transaccionales con encabezado y detalle.

Validación estructural.

Validación de negocio.

Vista previa antes de confirmar.

Ejecución síncrona o asíncrona según volumen.

Auditoría.

Reutilización por múltiples módulos.


La funcionalidad está orientada principalmente a:

Implementaciones iniciales.

Migraciones.

Cargas masivas operativas.

Integración tabular controlada.



---

2. Restricción por modo de operación

Regla

La funcionalidad no debe estar disponible cuando el sistema opere en:

Desktop Mode

Backend

Toda ruta relacionada debe validar:

if current_app.config["DESKTOP_MODE"]:
    abort(403)

Frontend

No mostrar:

Menú.

Accesos rápidos.

Botones.

Rutas navegables.



---

3. Arquitectura general

Debe existir un único framework de importación reutilizable.

Estructura sugerida

cacao_accounting/
    imports/
        adapters/
        readers/
        services/
        validators/
        templates/
        models/
        routes/
        utils/


---

4. Filosofía de diseño

Principio fundamental

El archivo tabular NO define el contexto del documento.

El contexto se define previamente en UI mediante un lote de importación.

El archivo solo contiene:

Datos variables.

Líneas.

Referencias externas.

Valores operativos.



---

5. Flujo funcional

Paso 1 — Crear importación

Usuario selecciona:

Compañía
Tipo de registro
Serie/secuencia si aplica
Libro contable solo para comprobantes manuales

Paso 2 — Crear lote

Se crea:

ImportBatch(status=0)

Paso 3 — Descargar plantilla

La plantilla se genera dinámicamente según:

tipo de registro

Paso 4 — Subir archivo

El usuario carga:

csv
xls
xlsx
ods

Paso 5 — Validación

El sistema:

Lee archivo.

Normaliza datos.

Valida estructura.

Valida negocio.

Genera preview.


Paso 6 — Confirmación

Usuario confirma.

Paso 7 — Ejecución

Dependiendo del tamaño:

<= 100 filas → sync
> 100 filas → async thread

Paso 8 — Resultado

Mostrar:

Documentos creados.

Errores.

Advertencias.

Estado final.

Reporte descargable.



---

6. Modelo principal

ImportBatch

class ImportBatch(db.Model):
    id
    company_id
    record_type
    sequence_id
    accounting_book_id
    source_format
    source_filename
    source_path
    total_rows
    processed_rows
    success_rows
    error_rows
    warning_rows
    status
    cancel_requested
    created_by_id
    created_at
    started_at
    completed_at


---

7. Estados

0 = no iniciado
1 = archivo cargado
2 = validado
3 = listo para importar
4 = procesando
5 = completado
6 = completado con errores
7 = fallido
8 = cancelado


---

8. Modelo de errores

class ImportBatchError(db.Model):
    id
    batch_id
    row_number
    document_ref
    field_name
    error_type
    message
    created_at


---

9. Contexto obligatorio en UI

Debe seleccionarse antes de cargar archivo

company_id
record_type
sequence_id

Solo para comprobantes manuales

accounting_book_id

El archivo NO puede redefinir:

company_id
record_type
sequence_id
accounting_book_id


---

10. Columnas reservadas prohibidas

Rechazar archivos que contengan:

company_id
empresa
compañía
record_type
tipo_registro
sequence_id
serie
secuencia
accounting_book_id
libro_contable


---

11. Formatos soportados

CSV

Reader:

csv

XLSX

Reader:

openpyxl

XLS

Reader:

xlrd

ODS

Reader:

odfpy


---

12. Pipeline de lectura

Todos los formatos deben normalizarse a:

NormalizedTable(
    columns=[],
    rows=[],
    source_format=""
)

Después del parseo, todo el pipeline debe ser idéntico.


---

13. Readers

Estructura

readers/
    base.py
    csv_reader.py
    xls_reader.py
    xlsx_reader.py
    ods_reader.py

Interface

class BaseReader:
    def read(self, file_path) -> NormalizedTable:
        ...


---

14. Servicio central

Clase principal

class ImportService:
    def validate(batch_id)
    def preview(batch_id)
    def execute(batch_id)
    def cancel(batch_id)


---

15. Adaptadores por módulo

Estructura

adapters/
    journal_entry.py
    purchase_order.py
    customer.py
    vendor.py

Interface

class BaseImportAdapter:
    columns = []
    required_columns = []

    def validate_row()
    def validate_document()
    def build_document()
    def persist_document()


---

16. Agrupación de documentos

Regla

Los documentos se agrupan mediante:

document_ref

document_ref

Debe poder persistirse como:

factura proveedor,

referencia externa,

referencia contable,

documento fuente,

referencia migración,

etc.


Regla

document_ref NO reemplaza numeración interna.

La serie/secuencia oficial la genera el backend.


---

17. Ejemplo — comprobante contable

Columnas

document_ref
fecha
cuenta
centro_costo
tercero
descripcion
debito
credito
referencia

Validaciones

mínimo dos líneas,

balanceado,

cuenta válida,

período abierto,

no débito y crédito simultáneo,

montos válidos.



---

18. Ejemplo — orden de compra

Columnas

document_ref
fecha
proveedor
producto
descripcion
cantidad
precio_unitario
impuesto
bodega


---

19. Validación estructural

Validar

extensión,

formato,

columnas requeridas,

columnas duplicadas,

archivo vacío,

filas máximas,

tamaño máximo.



---

20. Validación de negocio

Validar

compañía,

permisos,

serie,

período abierto,

cuentas,

terceros,

productos,

impuestos,

monedas,

tipos de cambio.



---

21. Validación de período contable

Obligatoria

Antes de postear:

assert_period_open(company_id, date)

Debe ejecutarse:

durante preview,

antes de persistir.



---

22. Ejecución síncrona/asíncrona

Configuración

IMPORT_SYNC_MAX_ROWS = 100

Reglas

<= 100 filas → sync
> 100 filas → background thread


---

23. Async simple

Tecnología

threading.Thread

No usar inicialmente

Redis

Celery

RabbitMQ

RQ



---

24. Background executor

Requerimiento

El thread debe llamar exactamente el mismo pipeline:

ImportService.execute(batch_id)

No duplicar lógica.


---

25. Recuperación ante reinicio

Al iniciar la app:

Buscar lotes:

status = procesando

Con timeout excedido.

Marcarlos como:

fallido/interrumpido


---

26. Idempotencia

No permitir ejecutar dos veces el mismo lote.

Validar

if batch.status != READY:
    reject()


---

27. Persistencia de archivo

Guardar archivo en:

instance/imports/<batch_id>/

Nunca depender del archivo temporal del request.


---

28. Seguridad

Prohibido

macros,

fórmulas ejecutables,

xlsm,

scripts embebidos.


Validar

tamaño,

mime type,

extensión,

sanitización nombre archivo.



---

29. Fórmulas

Rechazar fórmulas en campos críticos:

fecha
cuenta
debito
credito
cantidad
precio


---

30. Preview obligatorio

Antes de importar mostrar:

documentos detectados,

filas,

errores,

advertencias,

primeras líneas.



---

31. Cancelación

Permitir:

cancel_requested = True

El proceso debe verificarlo entre documentos.


---

32. Transaccionalidad

Regla

Procesar documento por documento.

No usar

Una transacción gigante para miles de filas.


---

33. Integración con dominio

La importación NO debe hacer inserts directos.

Debe usar servicios del dominio.

Correcto

ImportService
→ JournalService
→ PostingService

Incorrecto

Excel → INSERT SQL directo


---

34. Historial

Pantalla con:

fecha,

usuario,

tipo,

estado,

filas,

errores,

duración.



---

35. Reporte de errores

Debe poder descargarse:

fila
document_ref
campo
valor
mensaje_error


---

36. Plantillas

Generar plantillas para:

xlsx
ods
csv


---

37. Compatibilidad

Compatible con:

Microsoft Excel,

LibreOffice Calc,

OpenOffice.



---

38. Permisos

Nuevos permisos

imports.view
imports.create
imports.upload
imports.validate
imports.execute
imports.cancel
imports.download_template


---

39. Módulos iniciales soportados

Primera fase:

comprobantes contables,

órdenes de compra,

clientes,

proveedores,

catálogo de cuentas.



---

40. Criterios de aceptación

La funcionalidad se considera completa cuando:

existe un único framework centralizado,

soporta csv/xls/xlsx/ods,

funciona con sync/async,

respeta períodos cerrados,

usa contexto desde UI,

no permite redefinir contexto en archivo,

soporta preview,

soporta errores descargables,

soporta importaciones multi-documento,

utiliza servicios del dominio,

funciona sin infraestructura adicional,

no está disponible en desktop mode.
