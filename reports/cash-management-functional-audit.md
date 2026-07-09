# INFORME DE AUDITORÍA FUNCIONAL — TESORERÍA (CASH MANAGEMENT)

**Fecha:** 2026-07-09
**Alcance:** Pagos, Cobros, Transferencias, Notas Débito/Crédito, Conciliación Bancaria
**Módulo:** Bancos / Tesorería
**Versión del código:** commits hasta `487cd6e`

---

## RESUMEN EJECUTIVO

| Categoría | Cantidad |
|-----------|----------|
| Riesgo ALTO | 6 |
| Riesgo MEDIO | 8 |
| Riesgo BAJO | 3 |
| **Total** | **17** |

---

## HALLAZGOS DETALLADOS

### CAS-01 [ALTO] — Sin constraint único en PaymentReference — condición de carrera para aplicación duplicada

**Descripción:** El modelo `PaymentReference` no tiene `UniqueConstraint` en `(payment_id, reference_type, reference_id)`. Las verificaciones a nivel aplicación no están protegidas por `FOR UPDATE`. Dos solicitudes concurrentes pueden crear referencias de pago duplicadas que aplican el mismo pago a la misma factura dos veces.

**Impacto:** Una factura puede ser pagada en exceso sin detección. Las cuentas por pagar/cobrar mostrarían saldo cero a pesar de que se debe dinero al cliente/proveedor.

**Recomendación:** Agregar `UniqueConstraint("payment_id", "reference_type", "reference_id")` y `FOR UPDATE` en `_check_duplicate_application`.

**Evidencia:**
- `cacao_accounting/database/__init__.py:1600-1623`
- `cacao_accounting/document_flow/service.py:753-767`

---

### CAS-02 [ALTO] — Sin bloqueo de fila en conciliación bancaria — duplicación concurrente

**Descripción:** Las funciones de conciliación bancaria crean `ReconciliationItem` sin adquirir locks `with_for_update()` en `BankTransaction`. Dos reconciliaciones concurrentes del mismo BankTransaction pueden crear asignaciones duplicadas.

**Evidencia:**
- `cacao_accounting/bancos/reconciliation_service.py:266-330, 333-344`
- `cacao_accounting/bancos/__init__.py:536-564`

---

### CAS-03 [MEDIO] — Sin validación cruzada de tipo de cambio entre pago y referencias

**Evidencia:**
- `cacao_accounting/bancos/__init__.py:1602-1606, 1708-1714, 1743-1749`

---

### CAS-04 [MEDIO] — Cancelación de pago no limpia enlace de conciliación bancaria

**Descripción:** Al cancelar un pago, no se verifica si está vinculado a un `BankTransaction` via `payment_entry_id`. El BankTransaction retiene la referencia huérfana y su flag `is_reconciled` permanece `True`.

**Evidencia:**
- `cacao_accounting/bancos/__init__.py:1837-1867`
- `cacao_accounting/bancos/reconciliation_service.py:319-328`

---

### CAS-05 — MEDIO — Sin saldo en tiempo real en BankAccount

**Evidencia:**
- `cacao_accounting/database/__init__.py:1553-1567`
- `cacao_accounting/reportes/services.py:761-782`

---

### CAS-06 [ALTO] — Pago sin `FOR UPDATE` en flujo de reconciliación — sobre-aplicación concurrente

**Descripción:** En `_process_reconciliation_line`, el `PaymentEntry` se carga con `database.session.get()` sin `with_for_update()`. Dos reconciliaciones concurrentes pueden aplicar el mismo pago más allá de su saldo disponible.

**Evidencia:**
- `cacao_accounting/document_flow/service.py:688, 692-696`
- Contraste: línea 742 SÍ usa `with_for_update()`

---

### CAS-07 [MEDIO] — Sin límite de tamaño de lote en reconciliación masiva

**Evidencia:**
- `cacao_accounting/bancos/__init__.py:296-333`
- `cacao_accounting/document_flow/service.py:628-728`

---

### CAS-08 [MEDIO] — Descuento por pronto pago usa `posting_date` en lugar de fecha de factura

**Evidencia:**
- `cacao_accounting/accounting_engine/document_builders.py:769-770`

---

### CAS-09 [BAJO] — Descuento por pronto pago no accesible en formulario de pago

**Evidencia:**
- `cacao_accounting/accounting_engine/document_builders.py:743-772`
- `cacao_accounting/bancos/__init__.py:1429-1494`
- `cacao_accounting/bancos/forms.py:32-57`

---

### CAS-10 [ALTO] — Creación de pago masivo pierde tipo de cambio, descuento, ganancia/pérdida

**Descripción:** `_persist_payment_target_allocation` crea `PaymentReference` con campos mínimos. No establece `exchange_rate`, `discount_amount`, `gain_loss_amount` ni `difference_amount`. Los pagos creados por API masiva pierden metadatos financieros críticos.

**Evidencia:**
- `cacao_accounting/document_flow/service.py:1574-1584, 1675-1708`
- Contraste: `cacao_accounting/bancos/__init__.py:902-941` (conjunto completo de campos)

---

### CAS-11 [BAJO] — Sin validación de asignación mínima (pagos pueden quedar sin aplicar)

**Evidencia:**
- `cacao_accounting/bancos/__init__.py:1743-1749`

---

### CAS-12 [MEDIO] — Sin validación de cuenta GL al aprobar pago

**Evidencia:**
- `cacao_accounting/bancos/__init__.py:1815-1834, 1260-1266`
- `cacao_accounting/database/__init__.py:1564`

---

### CAS-13 [ALTO] — `_cash_consumed` cero permite eludir verificación de saldo restante

**Descripción:** `_cash_consumed` retorna `allocated - discount - gain_loss` con piso en 0. Si `discount + gain_loss >= allocated`, entonces `consumed = 0`, y la verificación de saldo restante siempre pasa — incluso si `payment_remaining = 0`. Un pago puede aplicarse a un número ilimitado de facturas sin agotarse.

**Evidencia:**
- `cacao_accounting/document_flow/service.py:622-625, 694-696`

---

### CAS-14 [ALTO] — Transacción bancaria puede reconciliarse dos veces vía ruta "apply"

**Descripción:** La ruta `bancos_conciliacion_bancaria_aplicar` no valida si un `BankTransaction` ya está reconciliado antes de crear nuevos `ReconciliationItem`. El check `is_reconciled` existe solo en el endpoint batch, no en el endpoint general "apply".

**Evidencia:**
- `cacao_accounting/bancos/__init__.py:536-564`
- `cacao_accounting/bancos/reconciliation_service.py:266-330`
- Contraste: `cacao_accounting/bancos/__init__.py:417-477` — SÍ tiene check en línea 433

---

### CAS-15 — MEDIO: Caché de saldo pendiente obsoleto puede bloquear pagos legítimos

**Evidencia:**
- `cacao_accounting/bancos/__init__.py:813-826`
- `cacao_accounting/document_flow/service.py:829-832, 859-866`

---

### CAS-16 — MEDIO: PaymentReference rows huérfanos al cancelar pago

**Evidencia:**
- `cacao_accounting/bancos/__init__.py:1849-1859`
- `cacao_accounting/document_flow/service.py:1267-1303`

---

### CAS-17 — BAJO: `_payment_numbering_defaults` no valida compañía del banco

**Evidencia:**
- `cacao_accounting/bancos/__init__.py:218-227`

---

## MATRIZ DE PRIORIDADES

| Prioridad | Hallazgos |
|-----------|-----------|
| **ALTA** | CAS-01, CAS-02, CAS-06, CAS-10, CAS-13, CAS-14 |
| **MEDIA** | CAS-03, CAS-04, CAS-05, CAS-07, CAS-08, CAS-12, CAS-15, CAS-16 |
| **BAJA** | CAS-09, CAS-11, CAS-17 |