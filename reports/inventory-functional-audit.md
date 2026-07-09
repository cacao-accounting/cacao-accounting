# INFORME DE AUDITORÍA FUNCIONAL — GESTIÓN DE INVENTARIO (INVENTORY MANAGEMENT)

**Fecha:** 2026-07-09
**Alcance:** Recepción de Mercancías, Entrega de Mercancías, Traslados, Ajustes (cantidad/valoración), Costeo FIFO
**Módulo:** Inventario
**Versión del código:** commits hasta `487cd6e`

---

## RESUMEN EJECUTIVO

| Categoría | Cantidad |
|-----------|----------|
| Riesgo ALTO | 3 |
| Riesgo MEDIO | 7 |
| Riesgo BAJO | 4 |
| **Total** | **14** |

---

## HALLAZGOS DETALLADOS

### INV-01 [MEDIO] — Verificación de stock negativo ocurre después de upsert de StockBin

**Descripción:** En `_create_stock_movement`, el check `qty_after < 0` y la validación de `allow_negative_stock` ocurren DESPUÉS de que `_upsert_stock_bin` ya ha actualizado la base de datos. Aunque la transacción se revierte si hay error, el patrón es frágil.

**Impacto:** Cualquier código futuro que haga un flush temprano entre el upsert y el check podría dejar la BD en estado inconsistente.

**Recomendación:** Mover el check `allow_negative_stock` ANTES de llamar `_upsert_stock_bin`.

**Evidencia:**
- `cacao_accounting/contabilidad/posting.py:1681-1696`

---

### INV-02 [BAJO] — Check de stock negativo en traslados funciona pero mensaje no específico

**Evidencia:**
- `cacao_accounting/contabilidad/posting.py:1869-1897`

---

### INV-03 [MEDIO] — Filtro de compañía en almacén inconsistente con `WarehouseCompanyAccount`

**Evidencia:**
- `cacao_accounting/database/__init__.py:927-956`
- `cacao_accounting/inventario/__init__.py:969-974, 1176-1180`

---

### INV-04 [MEDIO] — Conversión de UOM en reconciliación falla silenciosamente

**Evidencia:**
- `cacao_accounting/inventario/__init__.py:911-919`
- `cacao_accounting/contabilidad/posting.py:1165-1178`

---

### INV-05 [BAJO] — `qty_in_base_uom` no persiste al guardar entrada de stock

**Evidencia:**
- `cacao_accounting/inventario/__init__.py:839-865`
- `cacao_accounting/contabilidad/posting.py:1165-1178`

---

### INV-06 [ALTO] — `_stock_qty_after` sin `FOR UPDATE` — riesgo de condición de carrera

**Descripción:** `_stock_qty_after` ejecuta un `SUM` agregado sin `FOR UPDATE`. Bajo carga concurrente, dos emisiones de material para el mismo ítem pueden pasar ambas el check `qty_after < 0`, resultando en stock negativo no permitido.

**Impacto:** Bypass de la protección `allow_negative_stock=False` bajo concurrencia.

**Recomendación:** Mover el cálculo de `qty_after` dentro de `_upsert_stock_bin` que ya tiene `FOR UPDATE`, derivándolo de `bin_row.actual_qty + qty_change`.

**Evidencia:**
- `cacao_accounting/contabilidad/posting.py:1227-1233, 1427-1455, 1681-1698`

**Caso de prueba:**
1. Crear ítem con `allow_negative_stock=False`
2. Enviar dos salidas de material concurrentes para la misma cantidad (stock actual = 10, cada salida = 10)
3. Solo una debe prosperar

---

### INV-07 [ALTO] — Sin capacidad de reconstruir `StockValuationLayer`

**Descripción:** `rebuild_stock_bins` reconstruye `StockBin` desde `StockLedgerEntry` pero NO reconstruye `StockValuationLayer`. Si los datos de capas FIFO se corrompen, no hay mecanismo de recuperación.

**Impacto:** El costeo FIFO se vuelve irrecuperable ante corrupción de datos. El sistema lanzaría errores o calcularía costos incorrectos.

**Recomendación:** Agregar método para reconstruir `StockValuationLayer` reproduciendo todos los `StockLedgerEntry` en orden cronológico.

**Evidencia:**
- `cacao_accounting/inventario/service.py:159-198`
- `cacao_accounting/contabilidad/posting.py:1258-1279`

---

### INV-10 [MEDIO] — `reserved_qty` puede desviarse por movimientos fuera del flujo O2C

**Evidencia:**
- `cacao_accounting/contabilidad/posting.py:1427-1455`
- `cacao_accounting/inventario/service.py:159-198`

---

### INV-11 — BAJO: Mensaje de error genérico cuando no hay capas de valoración

**Evidencia:**
- `cacao_accounting/contabilidad/posting.py:1181-1190`

---

### INV-21 [BAJO] — `valuation_rate` se resetea a 0 cuando qty=0

**Evidencia:**
- `cacao_accounting/contabilidad/posting.py:1452-1455`

---

### INV-22 [MEDIO] — Relaciones documentales creadas en draft, eliminadas en edición

**Evidencia:**
- `cacao_accounting/inventario/__init__.py:809-836, 839-865, 1194-1235`

---

### INV-25 [ALTO] — Reconciliación de inventario no consume capas FIFO

**Descripción:** `_create_stock_reconciliation_movement` no llama a `_consume_stock_valuation_layers` cuando la cantidad reconciliation es negativa. Actualiza `StockBin` directamente pero las capas FIFO no se consumen. Con ciclos múltiples de reconciliación, el FIFO diverge progresivamente del stock físico.

**Impacto:** Divergencia progresiva entre el rastreo FIFO y el stock físico real. Costeo incorrecto en futuras emisiones.

**Recomendación:** Al reducir stock por reconciliación, consumir desde las capas FIFO usando `_consume_stock_valuation_layers`. La tasa de valoración debe usar la tasa FIFO, y cualquier diferencia de valoración debe registrar un ajuste contable.

**Evidencia:**
- `cacao_accounting/contabilidad/posting.py:1729-1806`
- `cacao_accounting/contabilidad/posting.py:1258-1279`

**Caso de prueba:**
1. Recibir 10 unidades a $100 (capa: qty=10, rate=100)
2. Reconciliar a 8 unidades a $120 (aumenta valoración)
3. `StockValuationLayer` aún muestra qty=10, rate=100 (sin consumo registrado)
4. Emitir 8 unidades. FIFO consume 8 a $100 = $800
5. Capa restante: qty=2 a $100 = $200. Pero `StockBin` muestra stock_value = 8×$120 = $960
6. Diferencia: $960 - $200 = $760

---

## MATRIZ DE PRIORIDADES

| Prioridad | Hallazgos |
|-----------|-----------|
| **ALTA** | INV-06, INV-07, INV-25 |
| **MEDIA** | INV-01, INV-03, INV-04, INV-10, INV-22 |
| **BAJA** | INV-02, INV-05, INV-11, INV-21 |