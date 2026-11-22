# Review QA2 (fix-proposed -> fix-confirmed / needs-work)

- Fecha: 2026-11-22
- Reviewer: QA2 (verificación independiente)
- HEAD base revisado: 85e8ee63 (rama estabilizacion)
- HEAD observado durante revisión (tras trabajo paralelo no relacionado): 402a46c4
- Nota: se verificó que los cambios paralelos observados (bancos/setup/css/auditoría/portal) no modifican la lógica de los 18 issues. Se verificó en HEAD actual que los guards/validaciones de cada issue siguen vigentes.

## Acciones realizadas (QA2)
- Se levantó el entorno (.venv) y se reparó `pathspec` para `mypy` (compatibilidad temporal del entorno de CI local); no se modificó código productivo salvo formateo de 2 archivos por `black==26.5.1` (requerido por CI): `cacao_accounting/contabilidad/balance_confirmation_bp.py`, `cacao_accounting/fiscal_persistence_service.py`. El cambio en `cacao_accounting/portal/__init__.py` observado en el árbol NO fue incluido (trabajo ajeno).
- Se ejecutaron pruebas focales por grupo (según reporte de agentes) y se re-ejecutaron `tests/test_admin_tax_rule_form.py` + `tests/test_balance_confirmation_party_scope.py` tras formateo: 33 passed. Linters CI-local (flake8/ruff/pydocstyle/mypy/complexipy/bandit) ejecutados sobre `cacao_accounting/`; `black --check cacao_accounting/` quedó OK tras formatear los 2 archivos.

## Veredictos (18/18)

### Grupo A (fiscal/contabilidad)
- #2018 TaxRule: validar referencias y compañía -> fix-confirmed
- #1998 Confirmación: limitar formulario al tercero autorizado -> fix-confirmed
- #1353 Filtro fiscal por categoría de artículo -> fix-confirmed (con nota: se formateó `fiscal_persistence_service.py` por black 26.5.1 para cumplir CI)
- #1243 Conciliación AR/AP con valoración del libro seleccionado -> fix-confirmed
- #1163 Respeta libros seleccionados en comprobantes -> fix-confirmed

### Grupo B (S2P)
- #1758 Prorrateo por peso/volumen -> fix-confirmed
- #1433 Facturas duplicadas entre compañías -> fix-confirmed (nota: contrato vigente usa ValueError de negocio; la clase `PurchaseInvoiceDraftError` no existe en HEAD por refactor previo)
- #1432 Bloquea rondas tras cierre manual -> fix-confirmed

### Grupo C (inventario/imports)
- #1346 Importación de maestros descarta filas agrupadas -> fix-confirmed
- #1332 Alinea permisos de líneas en flujos de inventario -> fix-confirmed
- #1301 Imágenes globales: alcance de compañía -> fix-confirmed (decisión explícita documentada en código)
- #1253 Alcance de lotes entre compañías -> fix-confirmed
- #1181 Restringe detalle de artículos a compañías autorizadas -> fix-confirmed

### Grupo D (terceros/API/setup)
- #1299 Retira/integración de preferencias CompanyParty -> fix-confirmed
- #1283 Elimina helpers de terceros sin llamadores -> fix-confirmed
- #1021 Setup solo administradores -> fix-confirmed
- #1019 document-flow ACL por cada origen de líneas y compañía destino -> fix-confirmed
- #998 API permisos en alias de notas documentales -> fix-confirmed

## Notas menores no bloqueantes (registradas)
- #1299: tests heredados en `test_party_company_settings_validation.py` referencian atributos retirados de forma vacua (sugerir limpieza).
- #998: commit listado `d7a6f549` no corresponde al fix de #998 (corresponde a #1998); el fix real está en commits `d6bff718`, `4bc2dc7e`, `c6b848a7`.
- #1021/#1019: suites originales eliminadas por limpieza masiva previa; regresiones re-incorporadas en archivos vigentes.
- CI lint (black 26.5.1): se formatearon `balance_confirmation_bp.py` y `fiscal_persistence_service.py`. `portal/__init__.py` quedó modificado localmente y no se incluye en este cierre.

## Cierre aplicado por QA2 (2026-11-22)
- Se publicaron comentarios de veredicto QA2 en los 18 issues y se movieron de `fix-proposed` a `fix-confirmed` (vía `gh issue edit ... --remove-label fix-proposed --add-label fix-confirmed`).
- Formateo con `black==26.5.1` aplicado a `cacao_accounting/contabilidad/balance_confirmation_bp.py` y `cacao_accounting/fiscal_persistence_service.py`; verificado `black --check cacao_accounting/` OK (250 archivos).
- `cacao_accounting/portal/__init__.py` permanece modificado por trabajo ajeno en el árbol local y **no** se incluyó en este cierre.
- Linters ejecutados (CI-local): flake8/ruff/pydocstyle/mypy/complexipy/bandit OK en `cacao_accounting/`; pruebas focales re-ejecutadas: `test_admin_tax_rule_form.py` + `test_balance_confirmation_party_scope.py` (33 passed).

Estado final: todos los 18 issues listados como `fix-proposed` en este lote quedaron con `fix-confirmed` y comentario QA2. EOF
## QA2 independiente — #1053 (2026-11-22)

**Veredicto: no aprobado; permanece `needs-work`.** Revisión estática independiente del diff actual, issue #1053, sus diez comentarios y el criterio aplicable del paraguas #1652. No ejecuté pruebas ni linters y no modifiqué código.

La solución incorpora `linea_origen_id`, rechaza referencias sin pareja documento/línea, verifica pertenencia de línea al documento, estado aprobado, compañía y artículo, y crea las relaciones mediante `create_document_relation`. La agregación entre grupos de documento es necesaria para evitar aceptar sobreasignación durante la validación del lote. El uso del servicio central también vuelve a comprobar y serializa el consumo al persistir.

**Hallazgo bloqueante:** las validaciones previas de cantidad llaman `pending_qty()` sin `exclude_draft_targets=True` (`_validate_source_quantities` y `validate_batch_documents`). La propia creación centralizada de relaciones usa `exclude_draft_targets=True`, y `consumed_qty_for_source()` documenta que ese parámetro excluye destinos en borrador. Por tanto, una línea fuente con relaciones activas a documentos destino en borrador puede ser rechazada falsamente por la importación aunque el servicio central permitiría la relación. Alinear ambas lecturas con la semántica del servicio de creación.

**Hallazgo adicional:** el `pending_qty()` del hook `validate_batch_documents()` no captura `ValueError`/`DocumentFlowError`. `_validate_source_quantities()` sí captura `ValueError`, por lo que un dato de relación corrupto (por ejemplo, evidencia activa sin `qty_in_base_uom`) puede registrarse como error de negocio y luego volver a propagar desde el hook, convirtiendo la validación del lote en error fatal. Capturar y convertir esa condición en error de validación de lote, o evitar repetir la consulta si ya falló en la validación por documento.

La etiqueta permanece sin cambios; no apliqué `fix-confirmed` ni cierre, conforme a la instrucción del usuario de detener el avance en `fix-proposed`.

### Re-revisión QA2 tras correcciones

**Veredicto: aprobado estáticamente.** El implementador alineó ambas consultas de cantidad con `exclude_draft_targets=True`, añadió captura de `ValueError` en la validación batch y agregó una regresión para relaciones activas a destinos en borrador. Volví a contrastar estas rutas con `create_document_relation()` y `consumed_qty_for_source()`: la validación previa usa ahora la misma convención de consumo que la creación y la condición de evidencia inválida se comunica como error de validación en lugar de propagarse como error fatal.

El resto de la implementación cubre las condiciones del issue: cada fila vinculada necesita ID de línea estable; el ID se resuelve dentro del documento declarado y se comprueba estado, compañía, tercero y artículo; el servicio central crea y revalida la relación real para la línea destino; las cantidades parciales y artículos repetidos conservan el ID explícito; y la suma entre grupos del mismo archivo se valida antes de persistir. No encontré defectos bloqueantes pendientes en la inspección estática actual. No ejecuté pruebas ni linters. Conforme a la instrucción explícita del usuario, no cambié estado ni etiqueta; el flujo debe detenerse en `fix-proposed`.

### Revisión estática del lote de regresiones ampliado

Inspeccioné además la versión actualizada de `tests/test_import_source_line_relations.py` y el hook `_collect_business_errors()`. La prueba de sobreasignación entre referencias distintas ahora recorre el hook de `ImportService`, verifica que se inserte `ImportBatchError` y por ello cubre la validación previa que el worker consulta antes de llamar `_process_all_documents()`. Revisé también los nuevos casos de cantidad inválida y de fuente que se vuelve inválida entre preflight y persistencia: el primero no se incorpora al agregado batch, y el segundo causa excepción antes de terminar la transacción del documento, que se revierte en el caller.

La evidencia añadida cubre los dos hallazgos anteriores y mejora la verificación del requisito “rechazar antes de persistir”. Mantengo el veredicto **aprobado estáticamente** para el diff actual. Revisión solamente estática; no ejecuté tests/linters ni cambié estado/etiqueta. El issue debe quedar en `fix-proposed` según instrucción del usuario.
