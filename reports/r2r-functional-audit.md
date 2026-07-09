# INFORME DE AUDITORÍA FUNCIONAL — RECORD TO REPORT (R2R)

**Fecha:** 2026-07-09
**Alcance:** Contabilidad General, Posting GL, Asientos Contables, Cierre Contable, Revaluación Cambiaria, Diarios Recurrentes
**Módulo:** Contabilidad
**Versión del código:** commits hasta `487cd6e`

---

## RESUMEN EJECUTIVO

| Categoría | Cantidad |
|-----------|----------|
| Riesgo ALTO | 8 |
| Riesgo MEDIO | 8 |
| Riesgo BAJO | 0 |
| **Total** | **16** |

---

## HALLAZGOS DETALLADOS

### R2R-01 [ALTO] — Validación de balance usa signed `line.value` después de redondeo por línea

**Descripción:** `post_comprobante_contable` verifica balance sumando `line.value` (débito positivo, crédito negativo). Cada línea se convierte vía `_to_company_currency` que redondea a 4 decimales. La suma de valores convertidos individualmente puede producir un desbalance falso de 0.0001.

**Impacto:** Asientos contables manuales multimoneda con múltiples líneas fallan frecuentemente con falso "El comprobante contable no está balanceado."

**Recomendación:** Usar tolerancia `abs(total_value) > Decimal("0.01")` o verificar balance con débitos/créditos absolutos.

**Evidencia:**
- `cacao_accounting/contabilidad/posting.py:2285-2301, 2354-2369, 418-421`

---

### R2R-02 [MEDIO] — Validación de período inconsistente en revaluación cambiaria

**Evidencia:**
- `cacao_accounting/contabilidad/exchange_revaluation_service.py:96-97, 100-103, 247-261, 263-275`

---

### R2R-03 [ALTO] — `cancel_submitted_journal` fuerza cancelación en la misma fecha

**Descripción:** La cancelación de un asiento contable requiere que la fecha de reversión sea exactamente igual a la fecha del asiento original. IAS/IFRS 8 permite correcciones en el período de descubrimiento.

**Impacto:** Los usuarios no pueden corregir errores descubiertos en períodos posteriores sin workarounds.

**Recomendación:** Eliminar el requisito de misma fecha. Validar solo que la fecha de cancelación caiga en un período abierto.

**Evidencia:**
- `cacao_accounting/contabilidad/journal_service.py:204-206`

---

### R2R-04 [MEDIO] — `duplicate_journal_as_reversal_draft` bloquea reversiones en el mismo período

**Evidencia:**
- `cacao_accounting/contabilidad/journal_service.py:305-308`

---

### R2R-05 [ALTO] — Cierre de año fiscal crea borrador sin aprobar automáticamente

**Descripción:** `create_fiscal_year_closing_voucher` crea el voucher en estado "draft". Debe ser aprobado manualmente. Si el usuario olvida, el año fiscal queda abierto.

**Recomendación:** Auto-aprobar el voucher de cierre después de crearlo, o proporcionar indicador prominente en dashboard.

**Evidencia:**
- `cacao_accounting/contabilidad/fiscal_year_closing.py:168-203`
- `cacao_accounting/contabilidad/journal_service.py:156-162`

---

### R2R-06 [ALTO] — Revaluación cambiaria sin auditoría

**Descripción:** `ExchangeRevaluationService.run()` y `void()` no llaman a ninguna función de auditoría. No hay `log_create`, `log_submit` ni `log_cancel` para los runs de revaluación.

**Recomendación:** Agregar `log_create(run)` después de la creación, `log_submit(run)` después del posting exitoso, y `log_cancel(run)` después del void.

**Evidencia:**
- `cacao_accounting/contabilidad/exchange_revaluation_service.py:80-219`

---

### R2R-07 — ALTO — Cierre de período sin auditoría

**Descripción:** `finalizar_cierre_mensual` marca `period.is_closed = True` sin registrar en la pista de auditoría quién cerró el período, cuándo, o desde qué IP.

**Evidencia:**
- `cacao_accounting/contabilidad/__init__.py:2717-2746`

---

### R2R-08 — ALTO — Documentos operativos sin auditoría de submit/cancel en posting.py

**Descripción:** `submit_document` y `cancel_document` en posting.py realizan posting y cancelación pero no llaman a `log_submit` ni `log_cancel`.

**Evidencia:**
- `cacao_accounting/contabilidad/posting.py:2605-2639`

---

### R2R-09 — MEDIO — Diarios recurrentes sin auditoría

**Evidencia:**
- `cacao_accounting/contabilidad/recurring_journal_service.py:134-232`

---

### R2R-10 — MEDIO — Sin control presupuestario en posting

**Evidencia:**
- `cacao_accounting/contabilidad/posting.py` (todas las funciones post_*)
- `cacao_accounting/contabilidad/budget_service.py`

---

### R2R-11 [ALTO] — Sin protección contra doble posting en funciones `post_*` individuales

**Descripción:** `post_document_to_gl` verifica `_has_active_gl_entries`. Las funciones individuales `post_sales_invoice`, `post_purchase_invoice`, `post_payment_entry`, `post_bank_transaction` no realizan esta verificación al inicio.

**Evidencia:**
- `cacao_accounting/contabilidad/posting.py:757, 846, 971, 1389, 2582-2602`

---

### R2R-12 — ALTO — Redondeo de tipo de cambio causa fallos de balance

**Descripción:** `_to_company_currency` redondea cada línea a 4 decimales. La suma de débitos redondeados puede no igualar la suma de créditos redondeados. `_assert_entries_balance` usa comparación exacta `Decimal`.

**Recomendación:** Aplicar tolerancia `abs(debit_total - credit_total) > Decimal("0.01")`.

**Evidencia:**
- `cacao_accounting/contabilidad/posting.py:408-416, 418-421`

---

### R2R-13 — MEDIO — Linking item-to-entry en revaluación frágil (asume orden posicional)

**Evidencia:**
- `cacao_accounting/contabilidad/exchange_revaluation_service.py:544-546`

---

### R2R-14 — ALTO: Cierre de período no exige completitud de pasos requeridos

**Descripción:** Un período puede cerrarse aunque los pasos requeridos (revaluación, diarios recurrentes, depreciación) no estén completados. Solo verifica que existan registros `PeriodCloseCheck`, no que tengan estado "passed".

**Recomendación:** Antes de marcar `period.is_closed = True`, verificar que todos los `PeriodCloseCheck` tengan `check_status == "passed"`.

**Evidencia:**
- `cacao_accounting/contabilidad/__init__.py:2717-2746`

---

### R2R-15 — MEDIO: Búsqueda de tipo de cambio sin fallback a fecha más cercana

**Evidencia:**
- `cacao_accounting/contabilidad/exchange_revaluation_service.py:655-675`
- `cacao_accounting/contabilidad/posting.py:424-446`

---

### R2R-16 — MEDIO: Balance proporcional en revaluación puede causar residuales

**Evidencia:**
- `cacao_accounting/contabilidad/exchange_revaluation_service.py:598-601, 565-568`

---

## MATRIZ DE PRIORIDADES

| Prioridad | Hallazgos |
|-----------|-----------|
| **ALTA** | R2R-01, R2R-03, R2R-05, R2R-06, R2R-07, R2R-08, R2R-11, R2R-12, R2R-14 |
| **MEDIA** | R2R-02, R2R-04, R2R-09, R2R-10, R2R-13, R2R-15, R2R-16 |
| **BAJA** | — |