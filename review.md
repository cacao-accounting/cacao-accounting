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