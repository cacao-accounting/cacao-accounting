# QA1 feedback — issue #1053

Fecha: 2026-11-22

## Veredicto: rechazado

La implementación incorpora `linea_origen_id`, conserva la relación mediante
`create_document_relation()` y prevalida cantidades en los grupos del archivo.
La revisión estática encontró una inconsistencia entre ese preflight y el
servicio central:

- `TransactionDocumentAdapter._validate_source_quantities()` y
  `validate_batch_documents()` llaman `pending_qty()` con el valor por defecto
  `exclude_draft_targets=False`.
- `create_document_relation()` consulta disponibilidad con
  `exclude_draft_targets=True` e `include_target_id=target_id`.
- `consumed_qty_for_source()` documenta que con esa opción los destinos en
  borrador no consumen cantidad. El preflight, en cambio, los cuenta y puede
  rechazar importaciones que el servicio central permitiría.

### Corrección requerida

Alinear ambas validaciones con la consulta de disponibilidad de
`create_document_relation()` y añadir una regresión que cree una relación activa
hacia un destino borrador, luego demuestre que el preflight permite el saldo que
el servicio central considera disponible. Mantener cobertura para el exceso
acumulado dentro de un documento y entre documentos del mismo lote.

El issue permanece en `needs-work`; QA1 no aprobó `fix-proposed`. Revisión
estática únicamente; no ejecuté pruebas ni linters.

Refs: #1053

## Tercera revisión QA1 — 2026-11-22

### Veredicto: aprobado para `fix-proposed`

La iteración actual corrige los hallazgos de las revisiones anteriores. La
implementación requiere una referencia estable de línea junto con el
documento origen, rechaza referencias faltantes, ajenas o ambiguas y verifica
estado aprobado, compañía, tercero y artículo. No infiere por posición ni por
artículo. Valida el consumo parcial en UOM base dentro del documento y a
nivel del archivo antes de persistir, excluyendo destinos borrador según el
contrato de `create_document_relation()`. La persistencia crea cada vínculo
mediante el servicio centralizado y vuelve a resolver la fuente antes de
crear la relación. El `PurchaseOrderAdapter` registrado también permite
conservar referencias upstream.

La cobertura visible incluye la integración del hook de `ImportService`
mediante `_collect_business_errors()`, con errores `ImportBatchError`
persistidos para sobreasignación entre grupos. El implementador reporta 32
pruebas focales y 142/142 sentencias ejecutables nuevas cubiertas entre
`transaction_documents.py` e `import_service.py`; no ejecuté pruebas ni
linters durante QA1.

No encuentro defectos bloqueantes pendientes. El issue #1053 avanzó a
`fix-proposed`; no se cerró ni se marcó `fix-confirmed`.

Refs: #1053 #1652

## Segunda revisión QA1 — 2026-11-22

La primera observación quedó corregida: los preflights ahora excluyen destinos
borrador, al igual que `create_document_relation()`, y el test nuevo cubre esa
ruta. Se verificó estáticamente el uso del servicio central y el preflight de
cantidades entre documentos del lote.

### Veredicto: rechazado; cobertura pendiente

Las pruebas visibles aún no cubren varias ramas nuevas de validación: documento
origen no aprobado o de otra compañía; tercero/artículo de origen incompatible;
errores de disponibilidad de `pending_qty()` en ambas validaciones; y
identificación ambigua entre tipos de origen. No se aportó evidencia de que la
lógica productiva nueva alcance el mínimo de 90 % requerido por AGENTS.md.

Agregar regresiones representativas y verificar cobertura antes de solicitar
otra revisión. Issue permanece en `needs-work`. No ejecuté pruebas ni linters.

Refs: #1053
