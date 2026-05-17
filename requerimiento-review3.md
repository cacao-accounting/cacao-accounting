
Después de analizar el diff, veo que has implementado una arquitectura sólida y bien documentada para los motores de cálculo fiscal, landed cost y settlement. Los motores son determinísticos, incluyen snapshots con huella SHA256, rounding manager, y una suite de pruebas unitarias y de integración bastante completa (incluyendo el golden test de importación).

Sin embargo, aún faltan varias piezas clave para dar por culminada la implementación según lo reflejado en PENDIENTE.md y lo que se puede inferir del código actual:

---

1. Posting Builder definitivo (pendiente explícito)

· Estado actual: AccountingMapper genera un JournalEntryProforma (solo una estructura en memoria). No persiste asientos contables reales en la base de datos.
· Lo que falta:
  · Un servicio que tome el JournalEntryProforma y lo convierta en instancias concretas de GLEntry, GLEntryLine, etc., respetando las ULIDs y las reglas contables de la empresa.
  · Integración con el ledger real (tablas existentes como gl_entry, gl_entry_line).
  · Manejo de reversiones (ya hay un esqueleto en reverse_from_snapshot, pero no escribe en la BD ni valida contra el esquema actual).
  · Resolución de cuentas contables dinámicas (no solo default_tax_accounts, sino también centro de costo, proyecto, etc.).

---

2. Motor de reglas basado en DAG (pendiente explícito)

· Estado actual: FiscalEngine ordena reglas por order y calcula linealmente. La detección de dependencias circulares es básica (grafo simple).
· Lo que falta:
  · Implementar un grafo de dependencias (DAG) que permita ejecutar reglas en paralelo cuando no haya dependencias, y manejar cálculos complejos no secuenciales (ej. impuestos que dependen de totales acumulados pero no necesariamente en orden fijo).
  · Soporte para condiciones dinámicas más avanzadas (ej. “si el monto base supera X, aplicar tasa Y” o reglas con umbrales).
  · Mejor manejo de merge_strategy cuando hay múltiples reglas del mismo concepto en diferentes niveles (hoy el RuleResolver funciona pero es secuencial).

---

3. Extensión del Settlement Engine (pendiente explícito)

· Estado actual: Solo maneja retenciones proporcionales sobre pagos parciales. No contempla descuentos por pronto pago ni diferencias de cambio.
· Lo que falta:
  · Descuentos por pronto pago: Calcular el monto líquido a pagar si se aplica un early_payment_discount (ej. 2% si se paga en 10 días).
  · Revaluación de moneda: Cuando la moneda del documento difiere de la moneda funcional, calcular la diferencia de cambio en el momento del settlement (usando exchange_rate vs fiscal_exchange_rate).
  · Ajustar la lógica de remaining_balance para reflejar correctamente el saldo después de aplicar descuentos y diferencias cambiarias.

---

4. Integración con el flujo transaccional existente

· Estado actual: Los motores son puros (no tocan BD). El BusinessEventOrchestrator se puede llamar, pero no está conectado a los endpoints ni a los modelos de transacciones (PurchaseInvoice, SalesInvoice, Payment, etc.).
· Lo que falta:
  · Modificar los controladores/views que confirman facturas de compra/venta, recibos de importación, pagos, etc., para que invoquen al Orchestrator con el CalculationContext construido a partir de los datos reales.
  · Almacenar el snapshot generado (JSON + fingerprint) en la transacción (ej. un campo calculation_snapshot en la tabla de factura).
  · Llamar al Posting Builder para crear los asientos contables automáticos al confirmar.
  · Manejar los errores de cálculo y mostrarlos en la UI.

---

5. Configuración dinámica de reglas desde la UI

· Estado actual: Las reglas (TaxRuleContext) se construyen manualmente en los tests. No hay modelos en la BD para almacenar impuestos, cargos, retenciones, etc.
· Lo que falta:
  · Modelos Django/SQLAlchemy para TaxRule, ChargeRule, WithholdingRule, LandedCostAllocationMethod, etc.
  · CRUD en el panel de administración para que los usuarios definan sus propias reglas (tasas, bases, fechas de vigencia, monedas, etc.).
  · Un RuleLoader que convierta las reglas de la BD a los objetos TaxRuleContext en tiempo de ejecución.

---

6. Manejo de redondeo a nivel de documento

· Estado actual: RoundingManager funciona bien, pero la política de redondeo se pasa como parte del CalculationContext.
· Lo que falta:
  · Almacenar la política de redondeo por empresa (configuración global) y permitir excepciones por transacción.
  · Garantizar que el total del documento (después de sumar impuestos) redondee exactamente igual que los cálculos individuales, y que si hay discrepancia de un centavo se ajuste automáticamente en la última línea (ya está en LandedCostEngine, pero no en FiscalEngine para la suma de impuestos).

---

7. Pruebas de integración con la base de datos

· Estado actual: Las pruebas son unitarias y no tocan la BD real.
· Lo que falta:
  · Tests que creen una factura de compra en la BD, llamen al orchestrator, verifiquen que se genera el snapshot, se crean los asientos contables y se actualizan los saldos de inventario.
  · Pruebas de reversión (notas de crédito) que comprueben que los asientos se anulan correctamente usando el snapshot almacenado.

---

Resumen de entregables pendientes (para culminar)

Pendiente Dificultad estimada
Posting Builder (persistencia de asientos) Alta
DAG para reglas fiscales Media-Alta
Descuentos y revaluación en SettlementEngine Media
Integración con endpoints y modelos existentes Alta
UI/configuración de reglas Alta
Pruebas de integración con BD Media

Conclusión: El diseño de los motores está casi listo (fase 1 completada), pero falta toda la capa de integración con la aplicación real, la persistencia y las funcionalidades avanzadas que menciona el PENDIENTE.md. Sin esos elementos, la implementación no puede considerarse culminada desde el punto de vista funcional.
