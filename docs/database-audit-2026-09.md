# Auditoría técnica de SQLAlchemy — septiembre de 2026

## Alcance y método

La revisión cubrió los 174 modelos registrados en la metadata, sus claves,
constraints, índices y relaciones; las consultas de servicios, rutas y reportes;
los límites transaccionales; las pruebas; la configuración de motores y el
historial Alembic. Se inspeccionó el esquema materializado en SQLite mediante
`PRAGMA index_list` y se midieron consultas con eventos de SQLAlchemy.

Los motores Tier 1 son SQLite y PostgreSQL, MySQL es Tier 2, y MariaDB y SQL
Server son Tier 3. Los cambios implementados usan solamente transacciones
anidadas y estrategias de carga ORM portables. No se cambió ninguna regla
contable, resultado numérico, API pública ni dato histórico.

## Hallazgos confirmados

### DB-001 — HIGH — TRANSACTION / INTEGRITY — Corregido

**Problema:** la importación de tasas ejecutaba `rollback()` sobre la
transacción completa cuando una fila encontraba una colisión `UNIQUE` durante
`flush()`. Las filas anteriores dejaban de existir, pero el contador
`inserted` todavía las reportaba.

**Evidencia:** el flujo consulta la clave natural y después hace `flush()` por
fila. La colisión aún es posible entre ambas operaciones. Una prueba que fuerza
la colisión en la segunda fila reprodujo la pérdida de la primera con el manejo
anterior.

**Impacto:** el resumen de importación podía divergir de la base de datos y una
carrera concurrente podía descartar tasas válidas ya procesadas.

**Ubicación:**
`cacao_accounting/contabilidad/exchange_rate_import_service.py`.

**Solución aplicada:** cada inserción se protege con un savepoint
`begin_nested()`. Una colisión revierte solo esa fila y mantiene la transacción
exterior y las filas anteriores.

**Riesgo del cambio:** bajo. Se preserva la importación parcial existente y no
se altera la validación ni el criterio de duplicado.

**Cómo se verificó:** prueba de regresión con una colisión `UNIQUE` real en la
segunda fila y una tercera fila válida, resultado `inserted=2`, `skipped=1` y
ambas tasas válidas persistidas.

### DB-002 — MEDIUM — QUERY / RELATIONSHIP / PERFORMANCE — Corregido

**Problema:** el reporte de estado de órdenes recuperaba las cabeceras y luego
ejecutaba un `SELECT` de líneas dentro del bucle: `1 + N` consultas.

**Evidencia:** con tres órdenes la medición BEFORE produjo cuatro `SELECT`.

**Impacto:** los round trips crecían linealmente con las órdenes aprobadas de
la compañía.

**Ubicación:**
`cacao_accounting/compras/purchase_reconciliation_service.py`.

**Solución aplicada:** `selectinload(PurchaseOrder.items)` en esa consulta
específica. No se cambió la estrategia global de la relación y no se introdujo
un join cartesiano.

**Riesgo del cambio:** bajo. Las mismas entidades y líneas alimentan los mismos
cálculos de cantidades y estados.

**Cómo se verificó:** con tres órdenes, AFTER usa dos `SELECT` (uno para
cabeceras y uno para esas líneas) y conserva los resultados del test funcional
existente. SQLAlchemy divide la carga en lotes cuando el conjunto excede el
límite de `IN`; por tanto, la mejora elimina `1 + N`, pero no promete dos
consultas para un número ilimitado de órdenes.

### DB-003 — HIGH — SCHEMA / MAINTAINABILITY — Pendiente

**Problema:** la única revisión Alembic es una línea base sin operaciones y el
esquema inicial se crea con `create_all()`.

**Evidencia:** `20260809_0001_baseline.py` declara `upgrade()` y `downgrade()`
vacíos. Una instalación existente no recibe cambios de modelo por `create_all`.

**Impacto:** un futuro cambio de índice o constraint que no incluya una nueva
migración no llegará a bases instaladas.

**Ubicación:** `cacao_accounting/migrations/20260809_0001_baseline.py` y
`cacao_accounting/cli.py`.

**Solución propuesta:** crear una revisión incremental, reversible y probada
por cada cambio físico futuro.

**Riesgo del cambio:** medio; requiere validar upgrades desde bases con volumen
en SQLite, PostgreSQL y MySQL.

**Cómo verificar la mejora:** ejecutar `upgrade -> downgrade -> upgrade` contra
copias de cada motor y comparar metadata y datos.

### DB-004 — MEDIUM — INDEX / PERFORMANCE — Pendiente

**Problema:** cerca de 150 PK de texto también declaran `index=True`, creando
un índice secundario redundante con el índice de la clave primaria.

**Evidencia:** SQLite materializa, por ejemplo, `ix_gl_entry_id` además de
`sqlite_autoindex_gl_entry_1`; se observó el mismo patrón en `accounts` y
`stock_ledger_entry`.

**Impacto:** espacio y amplificación de escritura innecesarios, especialmente
en GL, inventario, AR/AP y auditoría.

**Ubicación:** `BaseTabla.id` y PK explícitas en
`cacao_accounting/database/__init__.py`.

**Solución propuesta:** retirar gradualmente `index=True` de PK y eliminar los
índices `ix_*_id` mediante una migración. Comenzar por tablas append-only de
alto crecimiento y medir tamaño y throughput.

**Riesgo del cambio:** bajo en el modelo, medio en despliegue por el número de
índices. No se implementó para evitar una migración masiva sin datos reales.

**Cómo verificar la mejora:** comparar tamaño, tiempo de inserción y planes de
búsqueda por PK antes y después en cada motor.

### DB-005 — MEDIUM — INDEX / PERFORMANCE — Pendiente

**Problema:** existen índices no únicos exactamente duplicados por constraints
`UNIQUE`, entre ellos `(entity, code)` en `book`, `accounts` y `cost_center`.

**Evidencia:** la metadata y `PRAGMA index_list(accounts)` muestran tanto el
índice explícito como el autoíndice del constraint único.

**Impacto:** almacenamiento y mantenimiento de escrituras sin una ruta de
acceso adicional.

**Ubicación:** modelos `Book`, `Accounts`, `CostCenter`,
`ArApReconciliationPolicy`, `DocumentTransition`, `WithholdingCertificate` y
`PurchaseReconciliation`.

**Solución propuesta:** eliminar únicamente el índice no único duplicado y
conservar el constraint. No eliminar constraints de unicidad redundantes sin
confirmar primero la regla de negocio.

**Riesgo del cambio:** bajo funcionalmente, medio durante DDL en bases grandes.

**Cómo verificar la mejora:** inspección de índices, planes de igualdad,
benchmark de escritura y ciclo de migración por motor.

### DB-006 — HIGH — QUERY / SCALABILITY — Pendiente

**Problema:** `rebuild_stock_bins` ejecuta una consulta de grupos y dos
consultas por cada combinación compañía/artículo/bodega (`1 + 2G`).

**Evidencia:** por grupo calcula un `SUM` y recupera el `StockBin` separado.

**Impacto:** round trips lineales sobre un ledger histórico append-only.

**Ubicación:** `cacao_accounting/inventario/service.py`.

**Solución propuesta:** un `GROUP BY` para los totales y una precarga conjunta
de bins, preservando `reserved_qty` y valoración.

**Riesgo del cambio:** medio por las invariantes de inventario. Se documenta,
pero no se implementa sin un benchmark y matriz de casos FIFO/promedio.

**Cómo verificar la mejora:** presupuesto constante de consultas para varios
grupos y comparación exacta de cantidades, valores, tasas y reservas.

### DB-007 — MEDIUM — QUERY / SCALABILITY — Pendiente

**Problema:** la creación de asignaciones de notas de crédito ejecuta entre dos
y cinco consultas por línea.

**Evidencia:** por línea consulta existencia, suma asignada y, en devoluciones
físicas, tres vínculos/sumas adicionales.

**Impacto:** hasta `5N` consultas en un flujo financiero sensible.

**Ubicación:**
`cacao_accounting/compras/purchase_reconciliation_service.py`.

**Solución propuesta:** precargar por conjuntos y usar agregados agrupados sin
retirar la revalidación de capacidad ni el control de concurrencia.

**Riesgo del cambio:** alto. No se implementó por riesgo contable.

**Cómo verificar la mejora:** query budget multilínea junto con pruebas de
capacidad, importes, cantidades y concurrencia.

### DB-008 — MEDIUM — MASS PROCESSING / TRANSACTION — Pendiente

**Problema:** la importación bancaria realiza aproximadamente dos lecturas y un
`flush` por fila; el servicio genérico de importación realiza aproximadamente
dos commits por documento.

**Evidencia:** el adaptador recupera cuenta, busca duplicado y hace flush por
movimiento. El orquestador confirma documento y luego progreso por separado.

**Impacto:** round trips y commits lineales con el volumen importado.

**Ubicación:** `cacao_accounting/imports/adapters/bank_statement.py` y
`cacao_accounting/imports/services/import_service.py`.

**Solución propuesta:** precarga por conjuntos y consolidación del progreso en
el commit documental, conservando recuperación parcial y cancelación.

**Riesgo del cambio:** medio-alto. La semántica de duplicados y recuperación es
deliberada; no se modificó.

**Cómo verificar la mejora:** benchmark de queries/commits con pruebas de
reimportación, duplicados legítimos en el mismo archivo, fallo parcial y
cancelación.

## Optimizaciones potenciales que requieren evidencia adicional

- **MEDIUM — INDEX / SCALABILITY:** evaluar en GL
  `(company, ledger_id, account_id, posting_date)`. El índice actual coloca
  `account_id` después del rango de fecha. No se agrega sin `EXPLAIN` sobre una
  distribución representativa y sin decidir si reemplaza
  `ix_gl_entry_report_scope`.
- **MEDIUM — INDEX / SCALABILITY:** evaluar un índice de Stock Ledger que
  comience por `(company, voucher_type, voucher_id, item_code, warehouse)` para
  el rastreo de devoluciones. Su selectividad y frecuencia deben medirse.
- **MEDIUM — INDEX / SCALABILITY:** evaluar `(company_id, created)` para el
  listado de lotes de importación con volumen real.
- **LOW — RELATIONSHIP:** `ImportBatch.book` se carga globalmente con joined
  loading sin uso demostrado en varias rutas. Es una sobrecarga potencial, no
  un issue confirmado.
- **MEDIUM — RELATIONSHIP / INTEGRITY:** `PurchaseOrder.items` permite
  `delete-orphan` mientras la FK usa `ON DELETE RESTRICT`. No se encontró un
  borrado productivo que demuestre una violación append-only; requiere una
  decisión de negocio antes de cambiarlo.

## Índices implementados

No se agregó, eliminó ni modificó ningún índice. Los candidatos de GL, Stock
Ledger e importaciones permanecen explícitamente condicionados a planes y datos
representativos. Esto evita aumentar escrituras o almacenamiento por heurística.

## Migraciones

No hubo cambio físico de esquema, por lo que no corresponde crear una revisión
Alembic. Los dos cambios aplicados actúan en la consulta y en el límite del
savepoint. Los hallazgos de índices pendientes sí deberán implementarse con una
nueva revisión; nunca modificando la línea base publicada.

## Resultado BEFORE / AFTER

| Flujo | BEFORE | AFTER | Semántica |
| --- | ---: | ---: | --- |
| Estado de 3 órdenes de compra | 4 `SELECT` | 2 `SELECT` | idénticos totales y estados |
| Colisión en segunda tasa | rollback global; resumen inconsistente | rollback de una fila; `2` insertadas y `1` omitida | filas anterior y posterior preservadas |

## Riesgos y recomendaciones

Priorizar después `rebuild_stock_bins`, pero solo con pruebas de presupuesto de
consultas y reconciliación exacta. Para índices, capturar `EXPLAIN` y métricas
de cardinalidad de producción anonimizadas en SQLite y PostgreSQL; verificar
MySQL antes de promover el cambio. No se recomienda particionamiento mientras
Desktop dependa de SQLite y no exista evidencia de volumen que lo justifique.
