# ISSUES.md — REGISTRO DE AUDITORÍA FUNCIONAL ERP

**Última actualización:** 2026-07-09
**Versión del código auditado:** commits hasta `487cd6e`

---

## TABLA RESUMEN

| ID | Descripción | Status | GitHub | Commits |
|---|---|---|---|---|
| **S2P-01** | Sin verificación de relaciones activas al cancelar documentos no financieros | VERIFICADO | [#119](https://github.com/cacao-accounting/cacao-accounting/issues/119) | *(sesión 2026-07-09)* |
| **S2P-02** | `log_create` no se llama en creación de la mayoría de documentos | VERIFICADO | [#120](https://github.com/cacao-accounting/cacao-accounting/issues/120) | `bc1e0e0` |
| **S2P-03** | `log_update` no se llama en edición de PR, SQ, PO | VERIFICADO | [#140](https://github.com/cacao-accounting/cacao-accounting/issues/140) | `5bc4d13` |
| **S2P-04** | Three-way match omitido cuando Factura salta Recepción (PO → Invoice directo) | VERIFICADO | [#121](https://github.com/cacao-accounting/cacao-accounting/issues/121) | `bc1e0e0` |
| **S2P-05** | Validación de cantidades solo en submit, no en draft/edit | VERIFICADO | [#175](https://github.com/cacao-accounting/cacao-accounting/issues/175) | — |
| **S2P-06** | `supplier_name` no establecido en Purchase Receipt | VERIFICADO | [#160](https://github.com/cacao-accounting/cacao-accounting/issues/160) | `effccba` |
| **S2P-07** | Tipo de cambio perdido al editar Purchase Invoice multimoneda | VERIFICADO | [#122](https://github.com/cacao-accounting/cacao-accounting/issues/122) | — |
| **S2P-08** | Handlers de duplicado pierden tipo de cambio (PO, Invoice) | VERIFICADO | [#141](https://github.com/cacao-accounting/cacao-accounting/issues/141) | `d93b09e` |
| **S2P-09** | `_validate_supplier_invoice_flags` omite validación cuando `CompanyParty` es None | VERIFICADO | [#138](https://github.com/cacao-accounting/cacao-accounting/issues/138) | `13f77a4` |
| **S2P-10** | Condición de carrera en asignación directa de pago (sin `with_for_update`) | VERIFICADO | [#161](https://github.com/cacao-accounting/cacao-accounting/issues/161) | `cbd9a98` |
| **S2P-11** | `except Exception` genérico en `_purchase_exchange_rate` silencia errores | VERIFICADO | [#123](https://github.com/cacao-accounting/cacao-accounting/issues/123) | — |
| **S2P-12** | Cancelación de Invoice no verifica referencias de pago activas | VERIFICADO | [#124](https://github.com/cacao-accounting/cacao-accounting/issues/124) | `2db83f0` |
| **S2P-13** | `get_document_type` lanza KeyError para tipos desconocidos | VERIFICADO | [#142](https://github.com/cacao-accounting/cacao-accounting/issues/142) | — |
| **S2P-14** | Creación de relaciones documentales sin auditoría | VERIFICADO | [#162](https://github.com/cacao-accounting/cacao-accounting/issues/162) | — |
| **S2P-15** | Propagación de caché transitiva incompleta al cancelar Recepción | VERIFICADO | [#176](https://github.com/cacao-accounting/cacao-accounting/issues/176) | — |
| **S2P-16** | `supplier_invoice_no` sobrescrito por formulario vacío | VERIFICADO | [#177](https://github.com/cacao-accounting/cacao-accounting/issues/177) | — |
| **S2P-17** | Validaciones de Recepción/Factura se omiten sin enlace explícito | VERIFICADO | [#178](https://github.com/cacao-accounting/cacao-accounting/issues/178) | — |
| **S2P-18** | Sin validación de existencia/actividad de almacén en Recepción | VERIFICADO | [#163](https://github.com/cacao-accounting/cacao-accounting/issues/163) | — |
| **S2P-19** | Sin `log_create` en `create_target_document` (API/bulk) | VERIFICADO | [#179](https://github.com/cacao-accounting/cacao-accounting/issues/179) | — |
| **S2P-20** | Cancelación de Recepción no verifica facturas downstream | VERIFICADO | [#143](https://github.com/cacao-accounting/cacao-accounting/issues/143) | — |
| **O2C-01** | SalesRequest submit usa `require_party=False` | FALSO POSITIVO | — | — |
| **O2C-02** | Secuencia de cancelación inconsistente en SalesInvoice | FALSO POSITIVO | — | — |
| **O2C-04** | `_release_reservation_for_delivery_note` no es idempotente | VERIFICADO | [#139](https://github.com/cacao-accounting/cacao-accounting/issues/139) | `9a70e55` |
| **O2C-06** | Validación de precio en edición bloquea guardar borrador | VERIFICADO | [#180](https://github.com/cacao-accounting/cacao-accounting/issues/180) | — |
| **O2C-07** | Factura con `update_inventory=True` no disminuye `actual_qty` ni `reserved_qty` | VERIFICADO | [#125](https://github.com/cacao-accounting/cacao-accounting/issues/125) | `744c419` |
| **O2C-08** | Cancelación de Invoice no restaura inventario cuando `update_inventory=True` | VERIFICADO | [#144](https://github.com/cacao-accounting/cacao-accounting/issues/144) | `991894b` |
| **O2C-09** | SalesQuotation cancel no verifica relaciones descendientes activas | VERIFICADO | [#145](https://github.com/cacao-accounting/cacao-accounting/issues/145) | *(sesión 2026-07-09)* |
| **O2C-10** | `_handle_sales_order_new_post` retorna None en error | VERIFICADO | [#181](https://github.com/cacao-accounting/cacao-accounting/issues/181) | — |
| **O2C-11** | Edición de SalesOrder/SalesRequest sin auditoría | VERIFICADO | [#146](https://github.com/cacao-accounting/cacao-accounting/issues/146) | `ca51871` |
| **O2C-12** | Inconsistencia de naming en parámetros | FALSO POSITIVO | — | — |
| **O2C-13** | `create_document_relation` no valida docstatus de origen | VERIFICADO | [#182](https://github.com/cacao-accounting/cacao-accounting/issues/182) | — |
| **O2C-14** | `validate_submit_prerequisites` no valida rate > 0, amount > 0 | VERIFICADO | [#183](https://github.com/cacao-accounting/cacao-accounting/issues/183) | — |
| **O2C-17** | DeliveryNote `is_return` sin lógica de reversión real | FALSO POSITIVO | — | — |
| **O2C-18** | Nota de Crédito/Débito: `reversal_of` no validado | VERIFICADO | [#126](https://github.com/cacao-accounting/cacao-accounting/issues/126) | `744c419` |
| **O2C-20** | Sin `SELECT...FOR UPDATE` en reserva de stock (concurrencia) | VERIFICADO | [#127](https://github.com/cacao-accounting/cacao-accounting/issues/127) | `744c419` |
| **O2C-21** | `_form_decimal` acoplada a `request.form` | FALSO POSITIVO | — | — |
| **O2C-22** | `validate_submit_prerequisites` no valida almacén para ítems de stock | VERIFICADO | [#147](https://github.com/cacao-accounting/cacao-accounting/issues/147) | `e30c173` |
| **O2C-28** | `delivered_qty`/`billed_qty` no inicializados en 0 | VERIFICADO | [#148](https://github.com/cacao-accounting/cacao-accounting/issues/148) | `abc2853` |
| **R2R-01** | Validación de balance usa signed `line.value` después de redondeo por línea | FALSO POSITIVO | — | — |
| **R2R-02** | Validación de período inconsistente en revaluación cambiaria | FALSO POSITIVO | — | — |
| **R2R-03** | `cancel_submitted_journal` fuerza cancelación en la misma fecha | VERIFICADO | [#128](https://github.com/cacao-accounting/cacao-accounting/issues/128) | `4ba8263` |
| **R2R-04** | `duplicate_journal_as_reversal_draft` bloquea reversiones mismo período | FALSO POSITIVO | [#174](https://github.com/cacao-accounting/cacao-accounting/issues/174) | — |
| **R2R-05** | Cierre de año fiscal crea borrador sin aprobar | VERIFICADO | [#129](https://github.com/cacao-accounting/cacao-accounting/issues/129) | `deb241f` |
| **R2R-06** | Revaluación cambiaria sin auditoría | VERIFICADO | [#149](https://github.com/cacao-accounting/cacao-accounting/issues/149) | — |
| **R2R-07** | Cierre de período sin auditoría | VERIFICADO | [#164](https://github.com/cacao-accounting/cacao-accounting/issues/164) | — |
| **R2R-08** | Documentos operativos sin auditoría de submit/cancel | FALSO POSITIVO | — | — |
| **R2R-09** | Diarios recurrentes sin auditoría | VERIFICADO | [#165](https://github.com/cacao-accounting/cacao-accounting/issues/165) | `e173e25` |
| **R2R-10** | Sin control presupuestario en posting | VERIFICADO | [#184](https://github.com/cacao-accounting/cacao-accounting/issues/184) | — |
| **R2R-11** | Sin protección contra doble posting en funciones `post_*` individuales | VERIFICADO | [#130](https://github.com/cacao-accounting/cacao-accounting/issues/130) | — |
| **R2R-12** | Redondeo de tipo de cambio causa fallos de balance | VERIFICADO | [#131](https://github.com/cacao-accounting/cacao-accounting/issues/131) | `66826cd` |
| **R2R-13** | Linking item-to-entry en revaluación frágil (orden posicional) | VERIFICADO | [#185](https://github.com/cacao-accounting/cacao-accounting/issues/185) | — |
| **R2R-14** | Cierre de período no exige completitud de pasos requeridos | VERIFICADO | [#132](https://github.com/cacao-accounting/cacao-accounting/issues/132) | `cca22e0` |
| **R2R-15** | Búsqueda de tipo de cambio sin fallback a fecha más cercana | VERIFICADO | [#166](https://github.com/cacao-accounting/cacao-accounting/issues/166) | `4bc9fa7` |
| **R2R-16** | Balance proporcional en revaluación puede causar residuales | VERIFICADO | [#167](https://github.com/cacao-accounting/cacao-accounting/issues/167) | `ba9188f` |
| **CAS-01** | Sin constraint único en PaymentReference — aplicación duplicada concurrente | VERIFICADO | [#150](https://github.com/cacao-accounting/cacao-accounting/issues/150) | `725c609` |
| **CAS-02** | Sin bloqueo de fila en conciliación bancaria — duplicación concurrente | VERIFICADO | [#169](https://github.com/cacao-accounting/cacao-accounting/issues/169) | `108e1a5` |
| **CAS-03** | Sin validación cruzada de tipo de cambio entre pago y referencias | VERIFICADO | [#168](https://github.com/cacao-accounting/cacao-accounting/issues/168) | — |
| **CAS-04** | Cancelación de pago no limpia enlace de conciliación bancaria | VERIFICADO | [#151](https://github.com/cacao-accounting/cacao-accounting/issues/151) | `166fcdd` |
| **CAS-05** | Sin saldo en tiempo real en BankAccount | FALSO POSITIVO | — | — |
| **CAS-06** | Pago sin `FOR UPDATE` en flujo de reconciliación — sobre-aplicación concurrente | VERIFICADO | [#152](https://github.com/cacao-accounting/cacao-accounting/issues/152) | `7f9dd0c` |
| **CAS-07** | Sin límite de tamaño de lote en reconciliación masiva | VERIFICADO | [#153](https://github.com/cacao-accounting/cacao-accounting/issues/153) | `b52172e` |
| **CAS-08** | Descuento por pronto pago usa `posting_date` no fecha de factura | FALSO POSITIVO | — | — |
| **CAS-09** | Descuento por pronto pago no accesible en formulario de pago | FALSO POSITIVO | — | — |
| **CAS-10** | Creación de pago masivo pierde tipo de cambio, descuento, ganancia/pérdida | VERIFICADO | [#133](https://github.com/cacao-accounting/cacao-accounting/issues/133) | `fdc4a57` |
| **CAS-11** | Sin validación de asignación mínima | FALSO POSITIVO | — | — |
| **CAS-12** | Sin validación de cuenta GL al aprobar pago | FALSO POSITIVO | — | — |
| **CAS-13** | `_cash_consumed` cero permite eludir verificación de saldo restante | VERIFICADO | [#134](https://github.com/cacao-accounting/cacao-accounting/issues/134) | `f18c66e` |
| **CAS-14** | Transacción bancaria puede reconciliarse dos veces vía ruta "apply" | VERIFICADO | [#135](https://github.com/cacao-accounting/cacao-accounting/issues/135) | `628c579` |
| **CAS-15** | Caché de saldo pendiente obsoleto puede bloquear pagos legítimos | VERIFICADO | [#154](https://github.com/cacao-accounting/cacao-accounting/issues/154) | `8d2213e` |
| **CAS-16** | PaymentReference rows huérfanos al cancelar pago | FALSO POSITIVO | — | — |
| **CAS-17** | `_payment_numbering_defaults` no valida compañía del banco | FALSO POSITIVO | — | — |
| **INV-01** | Verificación de stock negativo ocurre después de upsert de StockBin | FALSO POSITIVO (CERRADO) | [#155](https://github.com/cacao-accounting/cacao-accounting/issues/155) | — |
| **INV-02** | Check de stock negativo en traslados funciona pero mensaje no específico | VERIFICADO | [#171](https://github.com/cacao-accounting/cacao-accounting/issues/171) | `fa8411e` |
| **INV-03** | Filtro de compañía en almacén inconsistente con `WarehouseCompanyAccount` | VERIFICADO | [#156](https://github.com/cacao-accounting/cacao-accounting/issues/156) | `bfcdf73` |
| **INV-04** | Conversión de UOM en reconciliación falla silenciosamente | VERIFICADO | [#157](https://github.com/cacao-accounting/cacao-accounting/issues/157) | `1414765` |
| **INV-05** | `qty_in_base_uom` no persiste al guardar entrada de stock | VERIFICADO | [#172](https://github.com/cacao-accounting/cacao-accounting/issues/172) | `2c4bfd5` |
| **INV-06** | `_stock_qty_after` sin `FOR UPDATE` — riesgo de condición de carrera | VERIFICADO | [#136](https://github.com/cacao-accounting/cacao-accounting/issues/136) | `2b5db7d` |
| **INV-07** | Sin capacidad de reconstruir `StockValuationLayer` | VERIFICADO | [#158](https://github.com/cacao-accounting/cacao-accounting/issues/158) | `4f2680d` |
| **INV-10** | `reserved_qty` puede desviarse por movimientos fuera del flujo O2C | VERIFICADO | [#159](https://github.com/cacao-accounting/cacao-accounting/issues/159) | — |
| **INV-11** | Mensaje de error genérico cuando no hay capas de valoración | VERIFICADO | [#172](https://github.com/cacao-accounting/cacao-accounting/issues/172) | `678bc02` |
| **INV-21** | `valuation_rate` se resetea a 0 cuando qty=0 | FALSO POSITIVO | — | — |
| **INV-22** | Relaciones documentales creadas en draft, eliminadas en edición | FALSO POSITIVO | — | — |
| **INV-25** | Reconciliación de inventario no consume capas FIFO | VERIFICADO | [#137](https://github.com/cacao-accounting/cacao-accounting/issues/137) | `2087e10` |

**Totales:** 54 VERIFICADO · 14 FALSO POSITIVO · 1 FALSO POSITIVO (CERRADO) · 31 commits de fix

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
[cacao_accounting/<modulo>/<archivo>.py:<líneas>]

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
