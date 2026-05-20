# Estado Actual del Proyecto - 2026-05-19

- **Politica de numeracion documental:** `document_no` es irreversible una vez emitido. Los borradores conservan su numero aunque cambien fecha, compania o serie; si se genero una numeracion incorrecta, el registro debe anularse y crearse uno nuevo para preservar consecutivos rigurosos y trazabilidad sin huecos por eliminacion fisica.
- **MVP Fiscal (preview unificado):** Implementada matriz de comportamiento fiscal/gastos por tipo documental en `fiscal_preview_service.py`, con resolución por doctype y evento de reconocimiento.
- **API Fiscal Unificada:** Disponible `POST /api/fiscal/preview` para cálculo/preview común consumible por formularios transaccionales.
- **Preview fiscal canónico:** Los recálculos de preview priorizan reglas persistidas de `TaxRule` para conservar cascadas, dependencias y orden; las líneas reenviadas por el cliente ya no sustituyen reglas configuradas.
- **Impuestos/cargos manuales:** El bloque transaccional permite añadir líneas fiscales manuales desde la UI; el backend las adjunta a las reglas canónicas sin duplicar líneas automáticas reenviadas por el cliente.
- **Cobros bancarios:** `payment_entry` de tipo `receive` usa perfil de cobro (`sales` / `collection_confirmed`) para alinear preview, snapshot persistido y posting.
- **Guard UI fiscal:** El framework transaccional omite auto-preview para doctypes fuera de matriz fiscal, evitando errores visuales en flujos como cotizaciones.
- **UX Común “Impuestos y Cargos”:** Integrado en el framework transaccional compartido (Compras, Ventas, Inventario) con resumen de totales y modal de detalle por línea fiscal.
- **Bancos (alcance ajustado por requerimiento):** El bloque fiscal quedó activo solo en **Entrada de Pagos**; Nota de Crédito, Nota de Débito y Transferencia no requieren estos campos en esta fase.
- **Seguridad y calidad:** Corregida exposición de errores internos en API de preview; `codeql_checker` sin alertas, checks de calidad en verde para los cambios.
- **Persistencia fiscal real:** Implementada para `purchase_invoice`, `sales_invoice` y `payment_entry` mediante `document_tax_summary` y `document_tax_line`, incluyendo snapshot inmutable por línea.
- **Persistencia fiscal robusta:** Las cuentas fiscales vacías se guardan como `NULL` en `DocumentTaxLine.account_id`, evitando violaciones de FK cuando el usuario no selecciona cuenta.
- **Contabilización fiscal histórica:** `submit_document` para `purchase_invoice`, `sales_invoice` y `payment_entry` consume primero el snapshot fiscal persistido antes de cualquier fallback dinámico.

- **AR/AP y Terceros:** Implementado `PartyGroup` como catalogo global de tipos de cliente/proveedor y `Party.party_group_id` con sincronizacion hacia `classification` para compatibilidad.
- **Clientes y Proveedores:** Los maestros permiten crear/editar/ver tipo de tercero, estado global y configuracion por compania (`CompanyParty`, `PartyAccount`, plantilla fiscal y flags de compra).
- **Contactos y Direcciones:** Detalles de Cliente y Proveedor permiten gestionar multiples contactos y direcciones con alta, edicion inline y desactivacion, usando `Contact`, `Address`, `PartyContact` y `PartyAddress`.
- **Search Select:** Agregados doctypes `party_group`, `customer_group` y `supplier_group` para seleccionar Tipo de Cliente / Tipo de Proveedor desde formularios.
- **Validacion terceros:** Pruebas focales de esquema, search-select, rutas de terceros y render general de vistas en verde; Black, Ruff, Flake8, Mypy y pydocstyle focal pasan.

- **Revalorizacion cambiaria NIIF:** Implementado `ExchangeRevaluationService` para runs auditables multiledger, calculo incremental por documento/cuenta bancaria, omision de moneda origen, ejecuciones sin diferencias y anulacion con reversos GL.
- **Trazabilidad de revalorizacion:** `ExchangeRevaluation`, `ExchangeRevaluationItem` y `GLEntry.exchange_revaluation_run_id` guardan snapshot de tasas, saldos, documento fuente, tercero, cuenta, ledger y linea GL.
- **UI y cierre mensual:** Contabilidad cuenta con listado, formulario, detalle solo lectura y anulacion de revalorizaciones; el asistente de cierre mensual ejecuta la revalorizacion despues de comprobantes recurrentes.
- **Validacion revalorizacion:** Suite completa `pytest --slow=True` en verde (`681 passed`); Black, Ruff, Flake8, Mypy focal y pydocstyle focal tambien pasan.

- **Calidad Python (docstrings):** `pydocstyle` queda integrado al flujo de desarrollo y CI (`development.txt`, `run_test.sh` y workflow `python-package.yml`) con convención `pep257`.
- **Regla de documentación:** `AGENTS.md` ahora exige documentación adecuada mediante docstrings en módulos, clases y funciones.
- **Estado de `cacao_accounting`:** No se detectan docstrings faltantes (pydocstyle y validación AST sin hallazgos).

- **Merge Bancos remoto:** Integrada la rama `feat/banking-module-registers-16721791397278534001` con resolucion manual de conflictos, conservando funcionalidad existente en modulos no bancarios.
- **Bancos UX/Flujo:** Pagos, notas de debito/credito y transferencias internas ahora comparten formularios unificados con smart-select y payload JSON para captura rapida.
- **Compatibilidad de posting bancario:** Transferencias internas convierten cuentas bancarias origen/destino a cuentas GL (`paid_from_account_id`/`paid_to_account_id`) antes del posteo.
- **Documentos Operativos:** Detalles de Compras, Ventas e Inventario muestran moneda del registro, totales y lineas con codigo de moneda (`NIO 1,000.00`) y cantidades con 4 decimales (`10.0000`).
- **Comprobante Contable:** La moneda se muestra como codigo (`NIO`) y los importes `Debe`/`Haber` usan separador de miles con codigo de moneda (`NIO 1,000.00`) en tabla, panel y modal de detalle.
- **Comprobante Manual:** La leyenda `Comprobante manual` queda alineada bajo el numero del comprobante, igualando la cabecera de documentos operativos.
- **Validacion CI y Cobertura:** Workflow local equivalente en `venv` queda verde: build/twine, flake8, ruff, mypy, black, pytest completo con cobertura (`623 passed`, 83% total Python), `npm ci && npm test` (`21 passing`) y cobertura JavaScript con c8 (77% total).
- **Datos Demo de Terceros:** `Cliente Demo SA` y `Proveedor Demo SA` ahora se activan en `CompanyParty` para `cacao`, habilitando `smart-select` de clientes/proveedores filtrado por compania en Compras y Ventas.

- **Correccion UI Transaccional:** El modal compartido de detalle de linea inicializa sus `smart-select` solo cuando existe `modalLine`, conserva valores existentes y la secuencia se recarga automaticamente al cambiar compania.
- **Smart Select en Grids:** Los formularios transaccionales usan hidden inputs escalares como fuente de verdad; items filtran por compania y cargan descripcion, UOM predeterminada y UOMs permitidas.
- **Cabecera de Detalle:** Solicitud de Compra usa la misma estructura visual del comprobante manual: documento como titulo, tipo bajo el titulo, estado junto al numero, acciones a la derecha y datos dentro de la misma tarjeta.
- **Comprobante Manual:** El comprobante contable muestra `Comprobante manual` debajo del numero para mantener paridad visual con los documentos operativos.
- **Acciones en Borrador:** Solicitud de Compra en borrador muestra `Editar`, `Duplicar`, `Aprobar`, `Listado` y `Nuevo`; `Crear` permanece reservado para documentos aprobados.
- **Paridad Funcional Transaccional:** Compras, Ventas e Inventario incorporan rutas y acciones de `Editar` y `Duplicar` en documentos transaccionales, con edición restringida a borrador y duplicado disponible en borrador/aprobado.
- **Compras RFQ/SQ:** Se habilitaron rutas faltantes de `submit` y `cancel` para Solicitud de Cotización y Cotización de Proveedor; los botones del detalle ya no apuntan a endpoints inexistentes.
- **Actualizar Elementos:** Orden de Compra y Solicitud de Cotizacion pueden entrar desde Solicitud de Compra con origen precargado para traer lineas pendientes.
- **Framework Transaccional:** Estandarizado con soporte para `smart-select` en todos los niveles y layout uniforme.
- **Flujo Documental:** Soporta fusion de multiples fuentes con filtrado por Tercero y Compania.
- **Modulos Operativos:** Compras, Ventas e Inventario usan macros compartidas y ya tienen paridad de acciones en transaccionales; pendiente de consolidar cobertura y revisar casos limite en documentos maestros/no transaccionales.
- **Rutas de Inventario:** Renombradas a `inventory-issue` para mayor claridad semantica.
- **Pruebas:** Cobertura de mas de 600 tests unitarios/integracion y suite E2E Playwright basica para UI transaccional.
- **Verificación patch E2E/ULID:** Confirmado ajuste en `posting.py` para crear `StockBin` faltante y proteger `valuation_rate` con divisor `actual_qty > 0`. Se alinearon FKs de GL (`reversal_of`, `gl_entry_id`) a ULID de 26 caracteres y la suite de pruebas quedó en verde (`618 passed, 5 skipped`).
- **Motores de Cálculo Centralizados:** Implementada la nueva arquitectura de motores Fiscal, Landed Cost y Settlement. Los cálculos son determinísticos, auditables y configurables vía reglas sin código hardcodeado para impuestos específicos.
- **Golden Test de Importación:** Validado exitosamente el caso de referencia (DAI 5%, ISC 3%, IVA 15%) con costos de inventario y totales de factura exactos.
- **Audit Trail y Snapshots:** El sistema genera una explicación detallada de cada cálculo y persiste snapshots JSON con integridad SHA256 para trazabilidad histórica y reversiones precisas.
- **Infraestructura Contable Desacoplada:** Los motores Fiscal, Landed Cost y Settlement son ahora ciudadanos de primera clase, con soporte para redondeo avanzado, mapeo contable pro-forma y resolución dinámica de reglas.
- **Reglas Fiscales Persistidas:** Existe el modelo `TaxRule`, con servicio `tax_rule_service.py` para CRUD y conversión a `TaxRuleContext`, además de una pantalla administrativa en `/settings/tax-rules`.
- **Mapping Contable de Liquidaciones:** `AccountingMapper` ya distingue `payment_confirmed` y `collection_confirmed`, generando líneas pro-forma para tercero, banco/caja, retenciones y diferencia cambiaria.
- **Multimoneda en Proforma:** `JournalEntryLineProforma` ahora transporta moneda de transacción, moneda compañía, monto dual y tipo de cambio usado; `SettlementEngine` calcula diferencia cambiaria realizada para pagos/cobros.
- **Motor listo para transacciones:** `contabilidad/posting.py` ya puede usar el motor fiscal/gastos para `PurchaseReceipt`, `PurchaseInvoice`, `SalesInvoice` y `PaymentEntry` mediante builders de contexto y un posting builder que persiste `JournalEntryProforma` como `GLEntry`.
- **TaxRule en flujo real:** El acoplamiento transaccional carga `TaxRule` desde BD por evento (`purchase_invoice_confirmed`, `sales_invoice_confirmed`, `payment_confirmed`, `collection_confirmed`, notas de crédito, etc.) y mantiene fallback a `TaxTemplate` para no romper documentos existentes.
- **DAG + settlement ampliado:** `FiscalEngine` resuelve dependencias entre reglas vía ordenamiento topológico; `SettlementEngine` soporta descuentos por pronto pago y revaluación no realizada; `AccountingMapper` genera el offset del control AR/AP para la revaluación no realizada.
- **Landed Cost transaccional:** `LandedCostEngine` calcula prorrateo de cargos capitalizables y el flujo real de recepción de compra materializa el costo aterrizado en la capa inicial de `StockValuationLayer` cuando los cargos ya son conocidos al ingreso. Para costos posteriores, la factura de compra puede persistir una capa de ajuste por valor sin cambiar cantidad.
- **Trazabilidad de importación:** Se agregó `LandedCostAllocation` como tabla dedicada de prorrateo para no sobrecargar `StockValuationLayer`; cada asignación guarda línea documental, ítem, almacén, base, monto asignado, costo final y referencia opcional a la capa de valuación.
- **Cobertura de eventos revisados:** El flujo real quedó cubierto para recepciones de compra, facturas de compra/venta, pagos/cobros y notas de crédito; el evento `import_landed_cost_confirmed` sigue disponible en motores/orquestador para casos de importación calculada.
- **Validación actual:** En `.venv`, `black --check cacao_accounting/`, `ruff`, `flake8`, `mypy`, `pydocstyle` focal y `pytest -v -s --exitfirst --slow=True` completo están en verde (`672 passed`).
