Necesito implementar el módulo de impuestos, costos accesorios, landed cost y liquidaciones financieras del sistema.

Antes de escribir código, debes leer y tomar como fuente principal estos archivos del repositorio:

- requerimiento.md
- requerimiento-analisis.md
- requerimiento-docs.md
- requerimiento-test.md

Objetivo general:
Implementar una arquitectura basada en tres motores de cálculo integrados pero separados:

1. Fiscal Engine
2. Landed Cost Engine
3. Settlement Engine

La implementación debe ser auditable, predecible, testeable y configurable. No debe hardcodear impuestos específicos como IVA, DAI, ISC, retenciones, flete o seguro. Todos los impuestos, cargos, gastos, costos accesorios, retenciones y tratamientos contables deben provenir de reglas configurables.

Principios obligatorios:

- Los motores deben ser determinísticos.
- Los motores deben ser funciones puras siempre que sea posible.
- Los motores no deben depender directamente de vistas, formularios ni plantillas HTML.
- Los motores no deben mezclar responsabilidades.
- El Fiscal Engine calcula obligaciones fiscales.
- El Landed Cost Engine calcula costos inventariables y prorrateos.
- El Settlement Engine calcula pagos, cobros, retenciones al pago/cobro, saldos y diferencias financieras.
- Los documentos de compra, venta, inventario y bancos no deben implementar cálculos fiscales propios.
- La sincronización entre motores debe realizarse mediante eventos de negocio y/o un orquestador.
- Todo cálculo confirmado debe guardar un snapshot auditable.
- El sistema debe permitir explicar cómo se calculó cada impuesto, cargo, costo o retención.
- El implementador debe poder predecir el efecto de cada regla configurada y validarlo fácilmente contra el resultado del sistema.

Eventos mínimos a soportar o preparar:

- purchase_receipt_confirmed
- purchase_invoice_confirmed
- import_landed_cost_confirmed
- sales_invoice_confirmed
- payment_confirmed
- collection_confirmed
- purchase_credit_note_confirmed
- sales_credit_note_confirmed

Implementar o preparar las estructuras necesarias para:

- reglas fiscales por ítem
- reglas fiscales por tercero, cliente o proveedor
- reglas fiscales por transacción
- plantillas de impuestos y cargos
- reglas con prioridad: ítem > tercero > transacción > compañía
- reglas acumulativas y reglas que sustituyen otras reglas
- impuestos en cascada
- impuestos incluidos en precio
- impuestos o cargos capitalizables al inventario
- impuestos registrados en cuenta separada
- gastos separados
- retenciones al pago
- retenciones al cobro
- pagos y cobros parciales
- prorrateo de costos por valor, cantidad, peso, volumen, igualitario y manual
- redondeo fiscal y contable
- moneda del documento, moneda de compañía y tipo de cambio
- snapshot histórico de cálculos
- reversión basada en snapshot para notas de crédito/débito

Caso obligatorio de referencia:

Mercadería: 1000.00
DAI 5% sobre mercadería = 50.00
Subtotal acumulado = 1050.00
ISC 3% sobre mercadería + DAI = 31.50
Subtotal acumulado = 1081.50
IVA 15% sobre mercadería + DAI + ISC = 162.23

Resultado esperado:
Costo inventariable = 1081.50
IVA separado = 162.23
Total factura = 1243.73

DAI e ISC forman parte del costo.
IVA se registra en cuenta separada.
La recepción de inventario debe ingresar por 1081.50.
La factura debe cancelar inventario no facturado por 1081.50 y reconocer IVA por 162.23.

Pruebas:
Implementar pruebas unitarias robustas para cada motor y pruebas de integración por evento.

Como mínimo deben existir pruebas para:

- cálculo fiscal simple
- cálculo fiscal en cascada
- prioridad de reglas ítem > tercero > transacción
- impuestos incluidos en precio
- cargos capitalizables
- cargos no capitalizables
- landed cost con un ítem
- landed cost con varios ítems
- prorrateo por valor
- prorrateo por cantidad
- prorrateo por peso
- pagos completos
- pagos parciales
- retenciones al pago
- retenciones al cobro
- recepción de compra
- factura de compra
- liquidación de importación
- factura de venta
- cobro de venta
- pago a proveedor
- nota de crédito usando snapshot
- reproducibilidad histórica del cálculo
- generación de audit trail
- validación de reglas inválidas
- detección de dependencias circulares

Debe existir un golden test que valide el caso de importación:

Mercadería 1000
DAI 5%
ISC 3%
IVA 15%

Y confirme:
DAI = 50.00
ISC = 31.50
IVA = 162.23
Costo inventario = 1081.50
Total factura = 1243.73

Documentación:
Crear dentro del repositorio un directorio:

docs/

Y dentro de docs/ crear un subdirectorio completo para esta implementación, por ejemplo:

docs/tax-cost-engines/

La documentación debe explicar claramente cómo configurar y validar reglas de:

- impuestos
- cargos
- gastos
- costos capitalizables
- retenciones
- fletes
- seguros
- DAI
- ISC
- IVA
- descuentos
- impuestos al pago
- impuestos al cobro
- liquidaciones de importación
- reglas por producto
- reglas por cliente/proveedor
- reglas por transacción
- plantillas de impuestos y cargos
- prorrateos
- snapshots
- reversión de documentos
- auditoría de cálculo

La documentación debe incluir ejemplos numéricos completos y verificables.

Debe incluir al menos estos archivos:

- docs/tax-cost-engines/index.md
- docs/tax-cost-engines/concepts.md
- docs/tax-cost-engines/fiscal-engine.md
- docs/tax-cost-engines/landed-cost-engine.md
- docs/tax-cost-engines/settlement-engine.md
- docs/tax-cost-engines/rule-priority.md
- docs/tax-cost-engines/rule-examples.md
- docs/tax-cost-engines/import-purchase-example.md
- docs/tax-cost-engines/sales-example.md
- docs/tax-cost-engines/payment-withholding-example.md
- docs/tax-cost-engines/auditability.md
- docs/tax-cost-engines/testing.md

La documentación debe permitir que un usuario técnico configure una regla y pueda predecir:

- cuándo se aplica
- sobre qué base se calcula
- si aumenta inventario
- si afecta total
- si afecta pago/cobro
- qué cuenta contable impacta
- cómo se prorratea
- cómo se redondea
- cómo aparece en el audit trail

Criterios de aceptación:

1. Los tres motores existen separados.
2. El cálculo fiscal no está duplicado en compras ni ventas.
3. Las reglas son configurables.
4. El caso de importación obligatorio pasa con los valores esperados.
5. Los motores devuelven resultados auditables.
6. Los documentos confirmados guardan snapshot.
7. Las notas de crédito/débito pueden revertir usando snapshot.
8. Los pagos/cobros parciales calculan retenciones proporcionalmente.
9. Existen pruebas unitarias e integración suficientes.
10. Existe documentación completa en docs/tax-cost-engines/.
11. El comportamiento del sistema puede ser validado manualmente contra los ejemplos de documentación.
12. La implementación debe mantener el diseño simple, sin sobreingeniería innecesaria.

Antes de modificar código, revisa la estructura actual del proyecto y propón brevemente dónde ubicarás:

- los motores
- los modelos o estructuras de reglas
- el orquestador de eventos
- los snapshots
- las pruebas
- la documentación

Luego implementa de forma incremental, priorizando primero el golden test de importación.
