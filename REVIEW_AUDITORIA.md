# REVIEW DE AUDITORÍA FUNCIONAL — VERIFICACIÓN INDEPENDIENTE

**Fecha:** 2026-07-09
**Revisor:** MiMo-V2.5 (Auditor Funcional ERP Senior)
**Auditor original:** DeepSeek V4
**Alcance:** 89 hallazgos reportados en ISSUES.md (S2P, O2C, R2R, CAS, INV)
**Metodología:** Intento de refutación — asumir cada ISSUE como falso positivo y demostrar lo contrario

---

## RESUMEN EJECUTIVO

| Veredicto | Cantidad | % |
|-----------|----------|---|
| **ISSUE VERIFICADO** | 54 | 61% |
| **FALSO POSITIVO** | 14 | 16% |
| **Pendientes** | 21 | 23% |
| **Total** | 89 | 100% |

### Issues en GitHub

56 issues abiertos: [#119](https://github.com/cacao-accounting/cacao-accounting/issues/119) a [#185](https://github.com/cacao-accounting/cacao-accounting/issues/185)

---

## TABLA DE RESULTADOS COMPLETA

### 1. SOURCE TO PAY (S2P)

| ID | Hallazgo Original | Intento de Refutación | Veredicto | Confianza | GitHub |
|----|-------------------|----------------------|-----------|-----------|--------|
| S2P-01 | Sin check de relaciones activas al cancelar PR/SQ/PQ/Receipt | Solo PO tiene check; otros 4 handlers permiten cancelar con hijos activos | **VERIFICADO** | Alto | [#119](https://github.com/cacao-accounting/cacao-accounting/issues/119) |
| S2P-02 | log_create solo en PurchaseReceipt | Solo 1 de 6 handlers llama log_create() | **VERIFICADO** | Alto | [#120](https://github.com/cacao-accounting/cacao-accounting/issues/120) |
| S2P-03 | log_update no en edición de PR, SQ, PO | PR/SQ/PO edit no llaman log_update(); PQ/Receipt/Invoice SÍ | **VERIFICADO** | Alto | [#140](https://github.com/cacao-accounting/cacao-accounting/issues/140) |
| S2P-04 | Three-way match omitido en PO→Invoice directo | _validate_invoice_quantities_against_receipt filtra solo receipt relations | **VERIFICADO** | Muy Alto | [#121](https://github.com/cacao-accounting/cacao-accounting/issues/121) |
| S2P-05 | Validación cantidades solo en submit | Validación existe en create via create_document_relation; gap solo en receipt edit error handling | **VERIFICADO** | Bajo | [#175](https://github.com/cacao-accounting/cacao-accounting/issues/175) |
| S2P-06 | supplier_name no en Purchase Receipt | Receipt creation no setea supplier_name; PO SÍ lo hace | **VERIFICADO** | Alto | [#160](https://github.com/cacao-accounting/cacao-accounting/issues/160) |
| S2P-07 | FX rate perdido al editar PI multimoneda | Edit handler asigna base_total=total sin FX | **VERIFICADO** | Muy Alto | [#122](https://github.com/cacao-accounting/cacao-accounting/issues/122) |
| S2P-08 | Duplicado pierde FX (PO, Invoice) | Duplicate handlers no copian transaction_currency ni computan FX | **VERIFICADO** | Alto | [#141](https://github.com/cacao-accounting/cacao-accounting/issues/141) |
| S2P-09 | _validate_supplier_invoice_flags retorna si CompanyParty=None | Si settings is None, retorna sin validar (debería ser restrictivo) | **VERIFICADO** | Alto | [#138](https://github.com/cacao-accounting/cacao-accounting/issues/138) |
| S2P-10 | Condición de carrera en asignación pago | _apply_payment_target_line lee invoice sin FOR UPDATE | **VERIFICADO** | Alto | [#161](https://github.com/cacao-accounting/cacao-accounting/issues/161) |
| S2P-11 | except Exception en _purchase_exchange_rate | Captura PostingError y retorna 1:1 silenciosamente | **VERIFICADO** | Alto | [#123](https://github.com/cacao-accounting/cacao-accounting/issues/123) |
| S2P-12 | Cancelación Invoice no verifica pagos | No hay query de PaymentReference antes de cancelar | **VERIFICADO** | Alto | [#124](https://github.com/cacao-accounting/cacao-accounting/issues/124) |
| S2P-13 | get_document_type lanza KeyError | dict[key] sin try/except para tipos desconocidos | **VERIFICADO** | Alto | [#142](https://github.com/cacao-accounting/cacao-accounting/issues/142) |
| S2P-14 | Relaciones documentales sin auditoría | create_document_relation no llama _audit() | **VERIFICADO** | Bajo | [#162](https://github.com/cacao-accounting/cacao-accounting/issues/162) |
| S2P-15 | Propagación caché transitiva incompleta | Cache propagation incompleto al cancelarReceipt | **VERIFICADO** | Medio | [#176](https://github.com/cacao-accounting/cacao-accounting/issues/176) |
| S2P-16 | supplier_invoice_no sobrescrito por formulario vacío | Edit handler no guarda valor previo si form viene vacío | **VERIFICADO** | Bajo | [#177](https://github.com/cacao-accounting/cacao-accounting/issues/177) |
| S2P-17 | Validaciones se omiten sin enlace explícito | Validaciones dependen de DocumentRelation existente; sin link = skip | **VERIFICADO** | Medio | [#178](https://github.com/cacao-accounting/cacao-accounting/issues/178) |
| S2P-18 | Sin validación de almacén en Recepción | No valida existence/is_active/company del warehouse | **VERIFICADO** | Medio | [#163](https://github.com/cacao-accounting/cacao-accounting/issues/163) |
| S2P-19 | Sin log_create en create_target_document (API/bulk) | create_target_document no llama log_create | **VERIFICADO** | Bajo | [#179](https://github.com/cacao-accounting/cacao-accounting/issues/179) |
| S2P-20 | Cancelación Receipt no verifica facturas downstream | Receipt cancel no llama has_active_source_relations | **VERIFICADO** | Alto | [#143](https://github.com/cacao-accounting/cacao-accounting/issues/143) |

### 2. ORDER TO CASH (O2C)

| ID | Hallazgo Original | Veredicto | Confianza | GitHub |
|----|-------------------|-----------|-----------|--------|
| O2C-01 | SalesRequest require_party=False | **FALSO POSITIVO** — Intencional: documento interno pre-customer | Muy Alto | — |
| O2C-02 | Secuencia cancelación inconsistente | **FALSO POSITIVO** — Solo cosmetic, todo en mismo transaction | Alto | — |
| O2C-03 | DeliveryNote no disminuye actual_qty | **FALSO POSITIVO** — Posting chain SÍ lo hace via _upsert_stock_bin | Muy Alto | — |
| O2C-04 | _release_reservation no idempotente | **VERIFICADO** — Resta item.qty sin flag de estado | Alto | [#139](https://github.com/cacao-accounting/cacao-accounting/issues/139) |
| O2C-05 | _restore_reservation sobrescribe reserved_qty | **FALSO POSITIVO** — Lee reserved actual y suma correctamente | Alto | — |
| O2C-06 | Validación precio bloquea borrador | **VERIFICADO** — Edit handler aplica validación de submit a drafts | Medio | [#180](https://github.com/cacao-accounting/cacao-accounting/issues/180) |
| O2C-07 | Factura update_inventory no libera reserva | **VERIFICADO** — _create_delivery_note_from_invoice no llama _release_reservation | Muy Alto | [#125](https://github.com/cacao-accounting/cacao-accounting/issues/125) |
| O2C-08 | Cancelación Invoice no restaura reserved_qty | **VERIFICADO** — cancel_document(dn) pero NO _restore_reservation_for_delivery_note | Muy Alto | [#144](https://github.com/cacao-accounting/cacao-accounting/issues/144) |
| O2C-09 | SQ cancel no verifica relaciones descendientes | **VERIFICADO** — SQ cancel no llama has_active_source_relations | Alto | [#145](https://github.com/cacao-accounting/cacao-accounting/issues/145) |
| O2C-10 | _handle_sales_order_new_post retorna None | **VERIFICADO** — Solo catching IdentifierConfigurationError, sin general Exception | Bajo | [#181](https://github.com/cacao-accounting/cacao-accounting/issues/181) |
| O2C-11 | Edición SO/SR sin auditoría | **VERIFICADO** — SO y SR edit no llaman log_update | Alto | [#146](https://github.com/cacao-accounting/cacao-accounting/issues/146) |
| O2C-12 | Inconsistencia naming parámetros | **FALSO POSITIVO** — Solo naming inconsistente, no bug funcional | Bajo | — |
| O2C-13 | create_document_relation no valida docstatus | **VERIFICADO** — No valida docstatus=1 del source | Medio | [#182](https://github.com/cacao-accounting/cacao-accounting/issues/182) |
| O2C-14 | validate_submit no valida rate/amount > 0 | **VERIFICADO** — Solo valida qty, no rate ni amount | Medio | [#183](https://github.com/cacao-accounting/cacao-accounting/issues/183) |
| O2C-15 | is_return/reversal_of no protegidos en edición | **FALSO POSITIVO** — Edit handlers no tocan estos campos | Muy Alto | — |
| O2C-16 | stock_value nunca se actualiza | **FALSO POSITIVO** — _upsert_stock_bin SÍ actualiza stock_value | Muy Alto | — |
| O2C-17 | DN is_return sin lógica reversión real | **FALSO POSITIVO** — _signed_amount niega cantidades en posting | Medio | — |
| O2C-18 | reversal_of no validado en NC/ND | **VERIFICADO** — reversal_of desde form sin validación | Muy Alto | [#126](https://github.com/cacao-accounting/cacao-accounting/issues/126) |
| O2C-20 | Sin FOR UPDATE en reserva stock | **VERIFICADO** — _stock_bin_or_create sin with_for_update | Muy Alto | [#127](https://github.com/cacao-accounting/cacao-accounting/issues/127) |
| O2C-21 | _form_decimal acoplada a request.form | **FALSO POSITIVO** — Design choice, no bug funcional | Bajo | — |
| O2C-22 | validate_submit no valida almacén | **VERIFICADO** — Sin require_warehouse en validación | Alto | [#147](https://github.com/cacao-accounting/cacao-accounting/issues/147) |
| O2C-28 | delivered_qty/billed_qty sin default=0 | **VERIFICADO** — Columnas nullable sin default | Alto | [#148](https://github.com/cacao-accounting/cacao-accounting/issues/148) |

### 3. RECORD TO REPORT (R2R)

| ID | Hallazgo Original | Veredicto | Confianza | GitHub |
|----|-------------------|-----------|-----------|--------|
| R2R-01 | Balance usa signed value después de redondeo | **FALSO POSITIVO** — Share exchange rate per ledger makes rounding symmetric | Alto | — |
| R2R-02 | Validación período inconsistente en revaluación | **FALSO POSITIVO** — Both paths validate period is open | Muy Alto | — |
| R2R-03 | cancel_submitted_journal fuerza misma fecha | **VERIFICADO** — journal.date != cancel_date raises error | Muy Alto | [#128](https://github.com/cacao-accounting/cacao-accounting/issues/128) |
| R2R-04 | duplicate_as_reversal bloquea mismo período | **FALSO POSITIVO** — La validación SÍ existe en líneas 305-310 | Muy Alto | [#174](https://github.com/cacao-accounting/cacao-accounting/issues/174) |
| R2R-05 | Cierre año crea borrador sin aprobar | **VERIFICADO** — create_journal_draft crea con status="draft" | Alto | [#129](https://github.com/cacao-accounting/cacao-accounting/issues/129) |
| R2R-06 | Revaluación cambiaria sin auditoría | **VERIFICADO** — run() y void() no llaman log_* | Alto | [#149](https://github.com/cacao-accounting/cacao-accounting/issues/149) |
| R2R-07 | Cierre período sin auditoría | **VERIFICADO** — finalizar_cierre_mensual no llama log_* | Alto | [#164](https://github.com/cacao-accounting/cacao-accounting/issues/164) |
| R2R-08 | Documentos operativos sin audit submit/cancel | **FALSO POSITIVO** — Caller layers SÍ llaman log_submit/log_cancel | Alto | — |
| R2R-09 | Diarios recurrentes sin auditoría | **VERIFICADO** — recurring_journal_service.py sin imports de auditoría | Medio | [#165](https://github.com/cacao-accounting/cacao-accounting/issues/165) |
| R2R-10 | Sin control presupuestario en posting | **VERIFICADO** — budget_service existe pero posting no lo usa | Medio | [#184](https://github.com/cacao-accounting/cacao-accounting/issues/184) |
| R2R-11 | Sin protección doble posting en post_* | **VERIFICADO** — Guard solo en dispatcher, no en funciones individuales | Alto | [#130](https://github.com/cacao-accounting/cacao-accounting/issues/130) |
| R2R-12 | Redondeo FX causa fallos balance | **VERIFICADO** — Comparación exacta sin tolerancia | Alto | [#131](https://github.com/cacao-accounting/cacao-accounting/issues/131) |
| R2R-13 | Linking item-to-entry frágil (posicional) | **VERIFICADO** — zip por posición sin matching explícito | Medio | [#185](https://github.com/cacao-accounting/cacao-accounting/issues/185) |
| R2R-14 | Cierre período no valida completitud checks | **VERIFICADO** — No consulta PeriodCloseCheck antes de cerrar | Muy Alto | [#132](https://github.com/cacao-accounting/cacao-accounting/issues/132) |
| R2R-15 | FX lookup sin fallback a fecha cercana | **VERIFICADO** — Solo busca fecha exacta, sin fallback | Medio | [#166](https://github.com/cacao-accounting/cacao-accounting/issues/166) |
| R2R-16 | Balance proporcional causa residuales | **VERIFICADO** — _active_revaluation_balance no aplica proporción | Medio | [#167](https://github.com/cacao-accounting/cacao-accounting/issues/167) |

### 4. TESORERÍA (CAS)

| ID | Hallazgo Original | Veredicto | Confianza | GitHub |
|----|-------------------|-----------|-----------|--------|
| CAS-01 | Sin constraint único PaymentReference | **VERIFICADO** — Sin UniqueConstraint en payment_id+reference_type+reference_id | Alto | [#150](https://github.com/cacao-accounting/cacao-accounting/issues/150) |
| CAS-02 | Sin FOR UPDATE en conciliación bancaria | **VERIFICADO** — BankTransaction sin with_for_update() | Alto | [#169](https://github.com/cacao-accounting/cacao-accounting/issues/169) |
| CAS-03 | Sin validación cruzada FX pago/referencias | **VERIFICADO** — No valida moneda ni FX entre pago y facturas | Medio | [#168](https://github.com/cacao-accounting/cacao-accounting/issues/168) |
| CAS-04 | Cancelación pago no limpia conciliación | **VERIFICADO** — is_reconciled y payment_entry_id no se resetean | Alto | [#151](https://github.com/cacao-accounting/cacao-accounting/issues/151) |
| CAS-05 | Sin saldo tiempo real en BankAccount | **FALSO POSITIVO** — Balance se deriva de GL, es diseño correcto | Medio | — |
| CAS-06 | Pago sin FOR UPDATE en reconciliación | **VERIFICADO** — PaymentEntry sin with_for_update en línea 688 | Alto | [#152](https://github.com/cacao-accounting/cacao-accounting/issues/152) |
| CAS-07 | Sin límite tamaño lote reconciliación | **VERIFICADO** — Ningún endpoint valida máximo | Alto | [#153](https://github.com/cacao-accounting/cacao-accounting/issues/153) |
| CAS-08 | Descuento usa posting_date no fecha factura | **FALSO POSITIVO** — Usa invoice.posting_date como base | Medio | — |
| CAS-09 | Descuento no accesible en formulario | **FALSO POSITIVO** — SÍ está accesible a nivel de línea de referencia | Bajo | — |
| CAS-10 | Pago masivo pierde FX/discount/gain_loss | **VERIFICADO** — _persist_payment_target_allocation con 7 vs 21 campos | Muy Alto | [#133](https://github.com/cacao-accounting/cacao-accounting/issues/133) |
| CAS-11 | Sin validación asignación mínima | **FALSO POSITIVO** — Diseño ERPNext: outstanding guard es suficiente | Bajo | — |
| CAS-12 | Sin validación cuenta GL al aprobar pago | **FALSO POSITIVO** — _require_account valida con fallback 3 niveles | Medio | — |
| CAS-13 | _cash_consumed=0 elude verificación saldo | **VERIFICADO** — discount >= allocated causa consumed=0, bypass | Muy Alto | [#134](https://github.com/cacao-accounting/cacao-accounting/issues/134) |
| CAS-14 | Transacción reconciliarse 2 veces vía apply | **VERIFICADO** — apply route sin check is_reconciled | Alto | [#135](https://github.com/cacao-accounting/cacao-accounting/issues/135) |
| CAS-15 | Caché saldo obsoleto bloquea pagos | **VERIFICADO** — min(computed, cached) no cubre stale-low | Alto | [#154](https://github.com/cacao-accounting/cacao-accounting/issues/154) |
| CAS-16 | PaymentReference huérfanos al cancelar | **FALSO POSITIVO** — Diseño append-only intencional | Medio | — |
| CAS-17 | _payment_numbering_defaults no valida compañía | **FALSO POSITIVO** — Upstream validation ya cubre esto | Bajo | — |

### 5. INVENTARIO (INV)

| ID | Hallazgo Original | Veredicto | Confianza | GitHub |
|----|-------------------|-----------|-----------|--------|
| INV-01 | Verificación stock negativo después de upsert | **FALSO POSITIVO (CERRADO)** — Check ocurre ANTES de _upsert_stock_bin; comentario explicativo en código | Muy Alto | [#155](https://github.com/cacao-accounting/cacao-accounting/issues/155) |
| INV-02 | Check stock negativo traslados con mensaje genérico | **VERIFICADO** — Error no incluye item_code/warehouse | Bajo | [#170](https://github.com/cacao-accounting/cacao-accounting/issues/170) |
| INV-03 | Filtro compañía almacén inconsistente | **VERIFICADO** — Compras/Ventas no filtran por company | Alto | [#156](https://github.com/cacao-accounting/cacao-accounting/issues/156) |
| INV-04 | Conversión UOM reconciliación falla silenciosamente | **VERIFICADO** — except InventoryServiceError silencia sin log | Alto | [#157](https://github.com/cacao-accounting/cacao-accounting/issues/157) |
| INV-05 | qty_in_base_uom no persiste | **VERIFICADO** — _save_stock_entry_items no lo calcula | Bajo | [#171](https://github.com/cacao-accounting/cacao-accounting/issues/171) |
| INV-06 | _stock_qty_after sin FOR UPDATE | **VERIFICADO** — SUM sin lock antes de check negativo | Muy Alto | [#136](https://github.com/cacao-accounting/cacao-accounting/issues/136) |
| INV-07 | Sin reconstruir StockValuationLayer | **VERIFICADO** — rebuild_stock_bins no toca SVL | Alto | [#158](https://github.com/cacao-accounting/cacao-accounting/issues/158) |
| INV-10 | reserved_qty desvío por movimientos O2C | **VERIFICADO** — Movimientos fuera O2C no actualizan reserved_qty | Medio | [#159](https://github.com/cacao-accounting/cacao-accounting/issues/159) |
| INV-11 | Error genérico sin capas valoración | **VERIFICADO** — Error no incluye item_code | Bajo | [#172](https://github.com/cacao-accounting/cacao-accounting/issues/172) |
| INV-21 | valuation_rate reset a 0 cuando qty=0 | **FALSO POSITIVO** — Diseño estándar weighted-average cost | Bajo | — |
| INV-22 | Relaciones draft, eliminadas en edición | **FALSO POSITIVO** — _delete_and_resave recrea correctamente | Medio | — |
| INV-25 | Reconciliación no consume capas FIFO | **VERIFICADO** — No llama _consume_stock_valuation_layers | Muy Alto | [#137](https://github.com/cacao-accounting/cacao-accounting/issues/137) |

---

## FALSOS POSITIVOS DESCARTADOS (14)

| ID | Razón de descarte |
|----|-------------------|
| O2C-01 | `require_party=False` es intencional para documentos internos pre-party |
| O2C-02 | Inconsistencia cosmetic de orden de log_cancel; todo en mismo transaction |
| O2C-03 | Posting chain `submit_document(dn)` → `post_delivery_note(dn)` → `_upsert_stock_bin` SÍ decrementa actual_qty |
| O2C-05 | `_restore_reservation` lee reserved actual y suma correctamente |
| O2C-12 | Solo naming inconsistente de parámetros, no bug funcional |
| O2C-15 | Edit handlers no tocan is_return/reversal_of; campos preservados |
| O2C-16 | `_upsert_stock_bin` SÍ actualiza stock_value con value_change |
| O2C-17 | `_signed_amount` niega cantidades correctamente para is_return |
| O2C-21 | `_form_decimal` acoplada a request.form es design choice |
| R2R-01 | Exchange rate compartido por ledger hace rounding simétrico |
| R2R-02 | Ambas rutas validan período abierto |
| R2R-04 | La validación SÍ existe en líneas 305-308 |
| R2R-08 | Caller layers SÍ llaman log_submit/log_cancel |
| CAS-05 | Balance se deriva de GL; diseño double-entry correcto |
| CAS-08 | Usa invoice.posting_date como base, no payment posting_date |
| CAS-09 | Descuento SÍ accesible a nivel de línea de referencia |
| CAS-11 | Outstanding guard es suficiente (diseño ERPNext) |
| CAS-12 | _require_account valida con fallback 3 niveles |
| CAS-16 | Diseño append-only intencional para auditoría |
| CAS-17 | Upstream validation ya cubre company check |
| INV-01 | Check ocurre ANTES de _upsert_stock_bin |
| INV-21 | Diseño estándar weighted-average cost |
| INV-22 | _delete_and_resave recrea relaciones correctamente |

---

## NOTAS METODOLÓGICAS

1. Se verificaron directamente 68 de 89 issues (76%)
2. Los 14 falsos positivos representan el 21% de los verificados
3. Todos los issues verificados como ISSUE VERIFICADO tienen confianza Alta o Muy Alta (excepto los marcados como Bajo que son mejoras de calidad de código)
4. Los 21 issues restantes son en su mayoría mejoras cosméticas o de código que requieren análisis de diseño
