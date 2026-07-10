# ISSUES.md — REGISTRO DE AUDITORÍA FUNCIONAL ERP

**Última actualización:** 2026-07-10
**Versión del código auditado:** HEAD `5a1374d`

| ID | Descripción | Status | GitHub | Commits |
|---|---|---|---|---|
| **S2P-02** | Sin `log_create` en rutas de duplicado y `create_target_document` | CORREGIDO | [#120](https://github.com/cacao-accounting/cacao-accounting/issues/120) | `0381b76` |
| **S2P-04** | Three-way match omitido cuando Factura salta Recepción (PO → Invoice directo) | FALSO POSITIVO | [#121](https://github.com/cacao-accounting/cacao-accounting/issues/121) | `5a1374d` |
| **S2P-05** | Validación de cantidades solo en submit, no en draft/edit | CORREGIDO | [#178](https://github.com/cacao-accounting/cacao-accounting/issues/178) | `d6e2200` |
| **S2P-06** | `supplier_name` no establecido en edición de Purchase Receipt | CORREGIDO | [#160](https://github.com/cacao-accounting/cacao-accounting/issues/160) | `fff2f81` |
| **S2P-08** | Handlers de duplicado pierden tipo de cambio (PO, Invoice) | FALSO POSITIVO | [#141](https://github.com/cacao-accounting/cacao-accounting/issues/141) | `d93b09e` |
| **S2P-11** | `except Exception` genérico en `_purchase_exchange_rate` silencia errores | FALSO POSITIVO | [#123](https://github.com/cacao-accounting/cacao-accounting/issues/123) | `5a1374d` |
| **S2P-15** | Propagación de caché transitiva incompleta al cancelar Recepción | CORREGIDO | [#179](https://github.com/cacao-accounting/cacao-accounting/issues/179) | `fix-S2P-15` |
| **S2P-16** | `supplier_invoice_no` sobrescrito por formulario vacío en edición | CORREGIDO | [#177](https://github.com/cacao-accounting/cacao-accounting/issues/177) | `fff2f81` |
| **S2P-17** | Validaciones de Recepción/Factura se omiten sin enlace explícito | CORREGIDO | [#180](https://github.com/cacao-accounting/cacao-accounting/issues/180) | `fff2f81` |
| **S2P-18** | Sin validación de existencia/actividad de almacén en Recepción | FALSO POSITIVO | [#163](https://github.com/cacao-accounting/cacao-accounting/issues/163) | `5a1374d` |
| **S2P-19** | Sin `log_create` en `create_target_document` (API/bulk) | CORREGIDO | [#181](https://github.com/cacao-accounting/cacao-accounting/issues/181) | `0381b76` |
| **S2P-20** | Cancelación de Recepción no verifica facturas downstream con pago asociado | FALSO POSITIVO | [#143](https://github.com/cacao-accounting/cacao-accounting/issues/143) | `5a1374d` |
| **S2P-21** | Control presupuestario configurable (global) en aprobación PR/PO | PENDIENTE | [#188](https://github.com/cacao-accounting/cacao-accounting/issues/188) | — |
| **S2P-22** | Sin automatización de punto de reorden | PENDIENTE | [#189](https://github.com/cacao-accounting/cacao-accounting/issues/189) | — |
| **O2C-01** | SalesRequest submit usa `require_party=False` | FALSO POSITIVO | — | — |
| **O2C-02** | Secuencia de cancelación inconsistente en SalesInvoice | FALSO POSITIVO | — | — |
| **O2C-04** | `_release_reservation_for_delivery_note` no es idempotente | CORREGIDO | [#139](https://github.com/cacao-accounting/cacao-accounting/issues/139) | `d794cfa` |
| **O2C-06** | Validación de precio en edición bloquea guardar borrador | CORREGIDO | [#182](https://github.com/cacao-accounting/cacao-accounting/issues/182) | `d794cfa` |
| **O2C-09** | SalesQuotation cancel no verifica relaciones descendientes activas | FALSO POSITIVO | [#145](https://github.com/cacao-accounting/cacao-accounting/issues/145) | `5a1374d` |
| **O2C-10** | `_handle_sales_order_new_post` retorna None en error | CORREGIDO | [#183](https://github.com/cacao-accounting/cacao-accounting/issues/183) | `d794cfa` |
| **O2C-11** | Edición de SalesOrder/SalesRequest sin auditoría | FALSO POSITIVO | [#146](https://github.com/cacao-accounting/cacao-accounting/issues/146) | `5a1374d` |
| **O2C-12** | Inconsistencia de naming en parámetros | FALSO POSITIVO | — | — |
| **O2C-13** | `create_document_relation` no valida docstatus de origen | CORREGIDO | [#184](https://github.com/cacao-accounting/cacao-accounting/issues/184) | `45611d0` |
| **O2C-14** | `validate_submit_prerequisites` no valida rate > 0, amount > 0 | CORREGIDO | [#185](https://github.com/cacao-accounting/cacao-accounting/issues/185) | `d88a578` |
| **O2C-17** | DeliveryNote `is_return` sin lógica de reversión real | FALSO POSITIVO | — | — |
| **O2C-18** | Nota de Crédito/Débito: `reversal_of` no validado en edición | CORREGIDO | [#126](https://github.com/cacao-accounting/cacao-accounting/issues/126) | `d794cfa` |
| **O2C-21** | `_form_decimal` acoplada a `request.form` | FALSO POSITIVO | — | — |
| **O2C-22** | `validate_submit_prerequisites` exige almacén para ítems de servicio | CORREGIDO | [#147](https://github.com/cacao-accounting/cacao-accounting/issues/147) | `d88a578` |
| **O2C-23** | Sin validación de límite de crédito en documentos de venta | PENDIENTE | [#190](https://github.com/cacao-accounting/cacao-accounting/issues/190) | — |
| **O2C-24** | Precios negativos permitidos en documentos de venta | CORREGIDO | [#191](https://github.com/cacao-accounting/cacao-accounting/issues/191) | `93cdadb` |
| **R2R-01** | Validación de balance usa signed `line.value` después de redondeo por línea | FALSO POSITIVO | — | — |
| **R2R-02** | Validación de período inconsistente en revaluación cambiaria | FALSO POSITIVO | — | — |
| **R2R-04** | `duplicate_journal_as_reversal_draft` bloquea reversiones mismo período | FALSO POSITIVO | [#174](https://github.com/cacao-accounting/cacao-accounting/issues/174) | — |
| **R2R-06** | Revaluación cambiaria sin auditoría | FALSO POSITIVO | [#149](https://github.com/cacao-accounting/cacao-accounting/issues/149) | `5a1374d` |
| **R2R-07** | Cierre de período sin auditoría | FALSO POSITIVO | [#164](https://github.com/cacao-accounting/cacao-accounting/issues/164) | `5a1374d` |
| **R2R-08** | Documentos operativos sin auditoría de submit/cancel | FALSO POSITIVO | — | — |
| **R2R-10** | Sin control presupuestario en posting | PENDIENTE | [#186](https://github.com/cacao-accounting/cacao-accounting/issues/186) | — |
| **R2R-11** | Sin protección contra doble posting en funciones `post_*` individuales | CORREGIDO | [#130](https://github.com/cacao-accounting/cacao-accounting/issues/130) | `ab45e31` |
| **R2R-13** | Linking item-to-entry en revaluación frágil (orden posicional) | CORREGIDO | [#187](https://github.com/cacao-accounting/cacao-accounting/issues/187) | `ab45e31` |
| **R2R-17** | Sin validación de balance en moneda de transacción | CORREGIDO | [#192](https://github.com/cacao-accounting/cacao-accounting/issues/192) | `4003b55` |
| **R2R-18** | Sin consolidación multi-empresa | PENDIENTE | [#193](https://github.com/cacao-accounting/cacao-accounting/issues/193) | — |
| **CAS-05** | Sin saldo en tiempo real en BankAccount | FALSO POSITIVO | — | — |
| **CAS-08** | Descuento por pronto pago usa `posting_date` no fecha de factura | FALSO POSITIVO | — | — |
| **CAS-09** | Descuento por pronto pago no accesible en formulario de pago | FALSO POSITIVO | — | — |
| **CAS-11** | Sin validación de asignación mínima | FALSO POSITIVO | — | — |
| **CAS-12** | Sin validación de cuenta GL al aprobar pago | FALSO POSITIVO | — | — |
| **CAS-13** | `_cash_consumed` cero permite eludir verificación de saldo restante | CORREGIDO | [#134](https://github.com/cacao-accounting/cacao-accounting/issues/134) | `189da6e` |
| **CAS-16** | PaymentReference rows huérfanos al cancelar pago | FALSO POSITIVO | — | — |
| **CAS-17** | `_payment_numbering_defaults` no valida compañía del banco | FALSO POSITIVO | — | — |
| **CAS-18** | Conciliación bancaria no valida docstatus del pago destino | CORREGIDO | [#194](https://github.com/cacao-accounting/cacao-accounting/issues/194) | `a0d3845` |
| **CAS-19** | Sin pronóstico de flujo de caja | PENDIENTE | [#195](https://github.com/cacao-accounting/cacao-accounting/issues/195) | — |
| **CAS-20** | Sin alerta de pagos duplicados por monto y proveedor cercano | CORREGIDO | [#196](https://github.com/cacao-accounting/cacao-accounting/issues/196) | `de7c43d` |
| **INV-01** | Verificación de stock negativo ocurre después de upsert de StockBin | FALSO POSITIVO (CERRADO) | [#155](https://github.com/cacao-accounting/cacao-accounting/issues/155) | — |
| **INV-10** | `reserved_qty` puede desviarse por movimientos fuera del flujo O2C | CORREGIDO | [#159](https://github.com/cacao-accounting/cacao-accounting/issues/159) | clamp en `_upsert_stock_bin` |
| **INV-21** | `valuation_rate` se resetea a 0 cuando qty=0 | FALSO POSITIVO | — | — |
| **INV-22** | Relaciones documentales creadas en draft, eliminadas en edición | FALSO POSITIVO | — | — |
| **INV-26** | Sin alerta de punto de reorden en movimientos de salida | PENDIENTE | [#197](https://github.com/cacao-accounting/cacao-accounting/issues/197) | — |
| **SEC-01** | Ausencia de validación de propiedad (created_by) en submit/cancel | FALSO POSITIVO | [#198](https://github.com/cacao-accounting/cacao-accounting/issues/198) | — |
| **SEC-02** | Eliminación física de líneas de documento al editar (sin trazabilidad) | PENDIENTE | [#199](https://github.com/cacao-accounting/cacao-accounting/issues/199) | — |

---

## TEMPLATE DE ISSUE PARA FUTURAS REVISIONES

```markdown
### ID-[XXX] [SEVERIDAD] — Título descriptivo

**Descripción:**
[Comportamiento actual vs esperado]

**Impacto:**
[Consecuencia funcional, financiera o de integridad]

**Recomendación:**
[Qué debe corregirse y cómo]

**Módulo/Archivo:**
[cacao_accounting/<modulo>/<archivo>.py:<línas>]

**Caso de prueba:**
[Pasos para reproducir / test name]

**Veredicto:** [PENDIENTE | VERIFICADO | FALSO POSITIVO]
**Confianza:** [Muy Alto | Alto | Medio | Bajo]
**GitHub Issue:** [#NNN](https://github.com/cacao-accounting/cacao-accounting/issues/NNN)
**Commit(s):** `abc1234`, `def5678`
```

### Guía rápida de severidad

| Severidad | Criterio |
|-----------|----------|
| ALTO | Pérdida financiera directa, violación de integridad de datos, riesgo de fraude |
| MEDIO | Impacto operativo, UX deficiente, pérdida de trazabilidad |
| BAJO | Calidad de código, mejoras cosméticas, casos límite |

### Estados de veredicto

- **PENDIENTE** — Hallazgo inicial, no revisado aún
- **VERIFICADO** — Confirmado como error real tras revisión independiente
- **FALSO POSITIVO** — Descartado tras análisis (código correcto)
- **FALSO POSITIVO (CERRADO)** — Cerrado formalmente con comentario en el issue
