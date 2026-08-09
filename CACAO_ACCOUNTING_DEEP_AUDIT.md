# CACAO ACCOUNTING — DEEP ACCOUNTING AUDIT

Fecha: 2026-08-09  
Alcance: revisión de código, pruebas focales, suite completa y esquema MariaDB 11.4 en Docker.  
Conclusión: **PARTIAL — no debe declararse listo para producción financiera sin cerrar los riesgos residuales**.

## 1. Executive Summary

El sistema tiene una base contable significativa: el posting genera `GLEntry`, existen libros paralelos, subledger de inventario, pagos/aplicaciones, revaluación FX, reportes y pruebas de regresión. La suite completa posterior a los cambios terminó con **1591 passed, 10 skipped y 174 warnings**; el esquema MariaDB pasó **214 pruebas**.

La evidencia sí confirma cinco defectos corregidos durante esta auditoría: dos incompatibilidades del esquema con MariaDB, una agregación bancaria entre libros, el signo FX incorrecto de notas de crédito abiertas y cifras/signos incorrectos en datasets semánticos y forecast de caja. La suite verde demuestra regresión de software, pero no prueba por sí sola que todos los subledgers reconcilien con GL en todos los libros, compañías, monedas y períodos. Por eso la evaluación final es PARTIAL en todos los procesos auditados.

## 2. Architecture Map

El flujo observado es, en términos funcionales:

`HTTP/CLI → servicios de dominio → repositorios/SQLAlchemy → documento fuente → posting.py → GLEntry por Book activo → reportes/analytics/reconciliación`.

- R2R: `contabilidad/posting.py`, `journal_service.py`, cierre fiscal y reportes GL/trial balance.
- O2C/S2P: documentos de ventas/compras y `document_flow/payment.py`, con aplicaciones y saldos pendientes.
- Inventario: movimientos SLE, `StockBin` como proyección y valoración/capas en el motor de posting.
- Bancos: `BankAccount`, `BankTransaction`, pagos y `bancos/reconciliation_service.py`.
- FX: `contabilidad/exchange_revaluation_service.py`; reportes semánticos normalizan valores de transacción y base.
- Multi-ledger: `Book`/`ledger_id`; los journals y consultas relevantes deben aislarse por compañía, libro, período y moneda.

### Cobertura de flujos verificada

| Flujo | Cadena comprobada | Pruebas/evidencia | Estado de cifras |
|---|---|---|---|
| R2R | journal/documento → posting → GLEntry → trial balance/BS/P&L | `test_07posting_engine.py`, `test_e2e_journalentry.py`, `test_fiscal_year_closing.py`, `test_r2r11_double_posting.py`, `test_record_to_reports_multicurrency_multiledger.py` | Doble partida y aislamiento probados; cierre/reapertura dimensional aún parcial |
| O2C | SalesInvoice → AR → PaymentEntry/Reference → banco → GL → reportes | `test_payment_entry_improved.py`, `test_o2c_sales_fixes.py`, `test_08_reconciliation_reports.py`, escenario multimoneda | Cálculos base, pagos, devoluciones y FX focales probados; refunds/write-offs completos pendientes |
| S2P/P2P | PurchaseReceipt → 3-way → PurchaseInvoice → AP → pago → GL | `test_s2p15_downstream_revert.py`, `test_08_reconciliation_reports.py`, `test_07posting_engine.py` | Matching parcial/completo y posting probados; créditos/prepagos completos pendientes |
| Inventory | recepción/entrada → SLE → capas/StockBin → salida/COGS → GL → kardex | `test_update_inventory.py`, `test_07posting_engine.py`, escenarios `INVENTORY_REBUILD_SCENARIOS`, `test_08_reconciliation_reports.py` | cantidades, capas, transferencias, reversals y reconstrucción probados; matriz GL por dimensión pendiente |
| Caja/bancos | PaymentEntry/BankTransaction → GL → candidate/reconciliation → balance/forecast | `test_cash_forecast.py`, `test_08_reconciliation_reports.py`, `test_exchange_revaluation.py` | banco contra GL y cancelaciones probados; statement/reconciling-items completo pendiente |
| FX/multi-ledger | moneda transacción → rate → valor libro → realized/unrealized → reportes | `test_record_to_reports_multicurrency_multiledger.py`, `test_exchange_revaluation.py` | NIO/EUR, rate, ganancias y exposición bancaria probados; cobertura exhaustiva de cierre pendiente |

La corrida consolidada de estos flujos produjo **161 passed, 110 warnings** en
216.61 segundos. La suite completa posterior a las correcciones produjo
**1591 passed, 10 skipped, 242 warnings**. Los nombres de pruebas anteriores
son evidencia ejecutada, no una inferencia basada únicamente en la existencia
del código.

## 3. Accounting Data Model

`Entity` representa la compañía/legal entity; `Book` representa libros paralelos; `Account` y cuentas de control alimentan `GLEntry`; los documentos de ventas/compras y pagos forman los subledgers; `BankAccount`/`BankTransaction` representan caja; SLE/StockBin/valoración representan inventario. La fuente auditable primaria del GL es el conjunto de líneas `GLEntry`; los campos derivados (`outstanding_amount`, saldos de forecast, bins y totales de reportes) deben reconstruirse desde transacciones fuente.

Se verificó que los asientos válidos mantengan débito = crédito en las pruebas existentes. La auditoría no encontró, en la suite ejecutada, un asiento publicado desequilibrado; esto es evidencia de tests, no una garantía universal de producción.

## 4. R2R Findings

La cobertura existente incluye posting, trial balance, estados financieros, journals recurrentes, cierres y reversiones. La suite completa pasa. Falta una corrida independiente consolidada que publique aquí los totales de apertura, débitos, créditos y cierre por cuenta/libro/período, por lo que R2R queda PARTIAL.

## 5. O2C Findings

Se cubren facturación, pagos parciales, anticipos, aplicaciones, saldos y multimoneda en pruebas focales y previas de la bitácora. No se demostró en esta corrida una matriz completa con overpayment, refund, write-off, payment reversal y conciliación AR-control GL por cada libro. Estado PARTIAL.

## 6. S2P Findings

Se cubren recepción, facturación parcial, pagos/aplicaciones y conciliación 3-way en pruebas previas. No quedó ejecutada una matriz completa de prepagos, créditos de proveedor, devoluciones, descuentos, duplicados y AP-control GL por compañía/libro/período. Estado PARTIAL.

## 7. Inventory Findings

El repositorio contiene SLE, reconstrucción de `StockBin`, valoración por capas y COGS, con pruebas de reconstrucción documentadas en `SESSIONS.md`. No se publicó una reconciliación independiente completa de cantidad, valoración, inventario GL y COGS por almacén, moneda y período para esta sesión. Estado PARTIAL.

## 8. Banking Findings

Existe flujo de banco, pagos, movimientos y reconciliación. Se corrigió la exposición bancaria multi-ledger en FX. Sigue pendiente una matriz publicada de book balance, partidas conciliatorias, estado bancario, fees, intereses, transferencias, devoluciones y huérfanos. Estado PARTIAL.

## 9. Multi-Currency Findings

Se conserva importe de transacción, moneda, rate y valor base en los flujos cubiertos. Se corrigieron los signos de notas de crédito y la exposición bancaria. La suite no constituye evidencia suficiente de remeasurement/reversal de todas las partidas AR/AP abiertas, realized FX tras liquidación parcial y precisión por moneda. Estado PARTIAL.

## 10. Multi-Ledger Findings

Las pruebas focales verifican dos libros y aislamientos relevantes; el defecto bancario confirmado demuestra que el aislamiento no era completo antes de la corrección. Debe completarse una revisión/query audit por `company_id`, `ledger_id`, `book_id`, `currency` y `period` en todos los reportes y servicios. Estado PARTIAL.

## 11. Reconciliation Results

| Área | Subledger | GL control | Diferencia | Evidencia actual |
|---|---:|---:|---:|---|
| AR | Cubierto por pruebas de documentos/aplicaciones | Cubierto por posting | No publicado como matriz completa | Parcial |
| AP | Cubierto por pruebas de documentos/aplicaciones | Cubierto por posting | No publicado como matriz completa | Parcial |
| Inventory | SLE/StockBin/valoración probados | Posting de inventario probado | No publicado por dimensión | Parcial |
| Bank | Forecast/reconciliation y FX probados | GLEntry probado | No publicado por partidas conciliatorias | Parcial |
| Tax | Cálculos y posting existentes | No matriz consolidada publicada | No determinada | Parcial |

No se inventan importes ni se etiqueta cero una diferencia que no fue calculada explícitamente.

## 12. End-to-End Test Results

- Suite requerida en `.venv`: **1591 passed, 10 skipped, 174 warnings**, log `test_results_audit_authoritative_20260809.log`.
- Suite completa autoritativa sobre el árbol final: **1591 passed, 10 skipped, 174 warnings**, log `test_results_audit_authoritative_20260809.log`.
- Esquema MariaDB 11.4 en Docker (`mysql+pymysql`, puerto 3307): **214 passed**, log `test_results_mariadb_schema_current.log`.
- Flujo de migraciones MySQL 8, PostgreSQL 16 y MariaDB 11.4: **PASS**; cada motor registró `20260809_0001` después de `db init`, en `test_results_migration_mysql_20260809.log`, `test_results_migration_postgresql_20260809.log` y `test_results_migration_mariadb_20260809.log`.
- Pruebas focales FX/multi-ledger/reportes: **12 passed**.
- Fixture afectado por hacer obligatorio `Entity.code`: **24 passed** de `test_line_import_api.py` tras completar el dato requerido.
- Regresión final de pagos/conciliaciones tras el último reemplazo de bloqueo ORM: **131 passed, 41 warnings**, log `test_results_payment_last_orm_20260809.log`.

Los escenarios base, multimoneda, multilibro, inventario y 3-way están documentados en `SESSIONS.md` y en los tests correspondientes. No se declara PASS para escenarios no ejecutados con una matriz de conciliación independiente.

## 13. Critical Bugs

### [FX-001] Revaluación bancaria agregaba todos los libros

**Severidad:** CRITICAL  
**Proceso:** FX / Multi-ledger / Bank  
**Archivo(s):** `cacao_accounting/contabilidad/exchange_revaluation_service.py:400-672`  
**Código involucrado:** `_open_bank_accounts`, `_bank_original_balance`  
**Problema:** el saldo original bancario no aislaba el `ledger_id` fuente.  
**Escenario de reproducción:** dos books activos contienen la misma exposición bancaria de 10 USD; antes de la corrección la suma podía ser 20 USD.  
**Resultado actual:** corregido; el query filtra `ledger_id`.  
**Resultado esperado:** una exposición de 10 USD por ledger fuente, sin contaminación.  
**Impacto contable:** sobrestimación de banco y de ganancia/pérdida FX no realizada.  
**Causa raíz:** agregación global de `GLEntry` por cuenta bancaria.  
**Corrección recomendada:** mantener filtro obligatorio de ledger y parametrizarlo desde el resumen de revaluación.  
**Test requerido:** `test_service_revalues_foreign_currency_bank_balance` con copia en segundo book; implementado y pasado.

## 14. High-Risk Bugs

### [DB-001] Foreign keys apuntaban a columnas nullable en MariaDB

**Severidad:** HIGH  
**Proceso:** Cross-cutting / Integridad de datos  
**Archivo(s):** `cacao_accounting/database/__init__.py:393`, `:517`  
**Código involucrado:** `Entity.code`, `Book.code`  
**Problema:** MariaDB 11.4 rechazaba la creación de FKs hacia códigos únicos nullable.  
**Escenario de reproducción:** `cacaoctl db reset --force` contra `cacao-audit-mariadb` antes del cambio.  
**Resultado actual:** corregido; schema MariaDB pasa 214 pruebas.  
**Resultado esperado:** creación determinista del esquema.  
**Impacto contable:** instalación bloqueada y posibilidad de despliegues sin integridad relacional.  
**Causa raíz:** nulabilidad incompatible con el contrato de FK.  
**Corrección recomendada:** mantener `nullable=False` y crear migración para bases existentes.  
**Test requerido:** prueba de esquema MariaDB y constraint de `Entity.code`; implementado.

### [FX-002] Notas de crédito abiertas usaban naturaleza de factura

**Severidad:** HIGH  
**Proceso:** FX / O2C / S2P  
**Archivo(s):** `cacao_accounting/contabilidad/exchange_revaluation_service.py:332-399`  
**Código involucrado:** `_open_sales_invoices`, `_open_purchase_invoices`  
**Problema:** una nota de crédito abierta se revaluaba como factura normal.  
**Escenario de reproducción:** nota de crédito AR o AP de 10 USD abierta al cierre.  
**Resultado actual:** corregido: AR usa naturaleza credit y AP debit.  
**Resultado esperado:** el signo de la exposición y del FX corresponde al saldo acreedor/deudor.  
**Impacto contable:** unrealized FX invertido en AR/AP.  
**Causa raíz:** naturaleza basada solo en tipo de documento normal.  
**Corrección recomendada:** derivar naturaleza del indicador de devolución y cubrir créditos, reversos y liquidaciones parciales.  
**Test requerido:** `test_revaluation_uses_credit_note_nature_for_open_ar_and_ap`; implementado.

### [REPORT-001] Datasets semánticos no neteaban devoluciones ni exponían base

**Severidad:** HIGH  
**Proceso:** O2C / S2P / Reporting / FX  
**Archivo(s):** `cacao_accounting/reportes/semantic.py:43-181`  
**Código involucrado:** `_signed`, `_base_amount`, análisis de ventas/compras/AR/AP  
**Problema:** devoluciones aparecían positivas y faltaba valor base por línea.  
**Escenario de reproducción:** venta 10 USD y devolución 2 USD a rate 36.  
**Resultado actual:** corregido: neto 8 USD y base 288; compras y saldos también normalizan signo.  
**Resultado esperado:** datasets reconciliables con documentos y GL.  
**Impacto contable:** ventas, compras, AR/AP y BI sobrestimados o mezclados entre monedas.  
**Causa raíz:** dataset trataba documentos por magnitud, no por naturaleza económica.  
**Corrección recomendada:** conservar transacción/base, moneda y signo; no convertir Decimal a float en la capa financiera.  
**Test requerido:** `test_semantic_reports_net_returns_and_expose_base_amount`; implementado.

### [CASH-001] Forecast omitía saldos base legacy y signaba mal devoluciones

**Severidad:** HIGH  
**Proceso:** Bank / O2C / S2P / FX  
**Archivo(s):** `cacao_accounting/bancos/cash_forecast_service.py:184-308`  
**Código involucrado:** `_sum_invoice_amount` y filtros de facturas abiertas  
**Problema:** un saldo existente solo en base podía omitirse o convertirse mal; una devolución podía aumentar forecast.  
**Escenario de reproducción:** saldo normal 10 USD y devolución 2 USD base a rate 36.  
**Resultado actual:** corregido; neto base esperado 288.  
**Resultado esperado:** forecast usa `base_outstanding_amount` y signo económico.  
**Impacto contable:** previsión de cobros/pagos y liquidez incorrecta.  
**Causa raíz:** fallback y predicado de saldo no contemplaban representación legacy ni devoluciones.  
**Corrección recomendada:** conservar fallback acotado, normalizar signos y cubrir null/zero.  
**Test requerido:** `test_cash_forecast_uses_base_legacy_balance_and_nets_returns`; implementado.

## 15. Medium/Low Findings

- **CONFIRMED BUG — HIGH (corregido):** `db migrate` declaraba éxito sin aplicar revisiones: una SQLite limpia terminaba con `alembic_version` vacío porque no existían scripts versionados. Se añadió `cacao_accounting/migrations/20260809_0001_baseline.py`, la CLI rechaza bases sin tabla `user` y `tests/test_database_migrations.py` cubre ambos casos. Sigue pendiente una migración posterior para constraints históricas de `Entity.code`/`Book.code` con preflight de nulos.
- **CONTROL GAP — HIGH:** el baseline no sustituye la migración de datos/constraints para bases históricas que pudieran contener `NULL` en `Entity.code` o `Book.code`; debe ejecutarse con preflight y no inventar códigos.
- **POTENTIAL RISK — MEDIUM:** existen superficies de presentación que convierten Decimal a `float`/`parseFloat`/`toFixed`; no se confirmó pérdida material en posting, pero falta una prueba de contrato de precisión UI/API.
- **DESIGN QUESTION — LOW:** `Book.code` es globalmente único además de único por entidad; puede limitar códigos iguales entre compañías. No se confirmó impacto contable.
- **CONTROL GAP — LOW:** la corrida focal emitió 110 warnings; después de reemplazar
  `Query.get()` por `Session.get(..., with_for_update=True)` en conciliación bancaria,
  pagos, referencias e importación, la regresión afectada pasó 146 pruebas y la
  superficie focal quedó en 56 warnings. Los restantes corresponden principalmente
  a claves JWT cortas de fixtures, `PytestCollectionWarning` y APIs legacy externas;
  deben limpiarse para que una advertencia transaccional no quede oculta.

## 16. Missing Controls

1. Migraciones versionadas y verificadas para cambios de constraints, incluyendo preflight de datos existentes.
2. Job/consulta de reconciliación formal por company, book, currency y fiscal period para AR, AP, inventory, bank y tax.
3. Alertas ante GLEntry huérfanos, subledger sin GL, journals duplicados y diferencias no cero.
4. Pruebas de concurrencia/retry/event replay con idempotency keys persistentes.
5. Política documentada de escala, redondeo y fuente/fecha del FX por moneda.

## 17. Missing Tests

Faltan o deben consolidarse pruebas independientes de: realized FX parcial y posterior remeasurement, reversal de remeasurement, cierre/reapertura por período, tax inclusive/multiple-tax, refund/write-off/overpayment, transferencias bancarias, backdated inventory, negative stock, y matriz de reconciliación materializada.

## 18. Recommended Fix Order

- **P0:** crear y probar la migración de constraints para `Entity.code`/`Book.code`; bloquear posting si faltan company/book/period/currency; ejecutar reconciliación de saldos antes de producción.
- **P1:** implementar matriz AR/AP/inventory/bank/tax ↔ GL por dimensiones y alertas de diferencia; completar FX realized/unrealized y cierres.
- **P2:** reforzar idempotencia, locks, retries y reversals; añadir escenarios de concurrencia y replay.
- **P3:** eliminar floats de fronteras financieras, documentar precisión y resolver la política de unicidad de códigos.

## 19. Residual Risks

La auditoría ejecutó flujos de migración en MySQL 8, PostgreSQL 16 y MariaDB 11.4; MariaDB se probó mediante `mysql+pymysql`, no mediante el controlador nativo `mariadb+mariadbconnector` porque no está instalado en el entorno. No se certifica comportamiento bajo carga/concurrencia real, migración de datos existentes, autorización multi-entidad ni todas las combinaciones de cierre, impuestos y reversals. Los 174 warnings deben revisarse aunque no hayan producido fallos.

## 20. Final Assessment

| Proceso | Estado |
|---|---|
| R2R | PARTIAL |
| O2C | PARTIAL |
| S2P | PARTIAL |
| Inventory | PARTIAL |
| Banking | PARTIAL |
| Multi-currency | PARTIAL |
| Multi-ledger | PARTIAL |
| Financial reporting | PARTIAL |

Respuesta a la pregunta de confiabilidad: **todavía no podemos demostrar confiabilidad financiera completa**. Sí podemos demostrar que la suite de regresión está verde y que los cinco defectos encontrados fueron corregidos con evidencia reproducible; falta cerrar las reconciliaciones dimensionales, migraciones y controles residuales antes de declarar PASS.
