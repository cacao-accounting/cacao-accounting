# Requerimiento técnico: motores de cálculo para impuestos, costos y liquidaciones

## 1. Objetivo general

Implementar una arquitectura centralizada de cálculo para manejar impuestos, cargos, costos accesorios, retenciones, prorrateos, pagos y cobros en compras y ventas.

El sistema no debe calcular impuestos directamente dentro de facturas, pagos, compras, ventas o inventario. En su lugar, los documentos y eventos del sistema deben invocar motores especializados.

Los motores deben ser:

* configurables
* determinísticos
* auditables
* reutilizables
* independientes del ORM
* independientes de la interfaz
* aptos para simulación, borrador y confirmación

---

# 2. Motores requeridos

## 2.1 Fiscal Engine

Responsabilidad:

Calcular impuestos, retenciones, cargos fiscales y obligaciones tributarias.

Debe manejar:

* IVA
* ISC
* DAI
* impuestos municipales
* retenciones
* percepciones
* impuestos incluidos en precio
* impuestos en cascada
* impuestos diferidos al pago/cobro
* impuestos capitalizables
* impuestos no capitalizables
* impuestos por ítem
* impuestos por tercero
* impuestos por transacción

No debe generar asientos directamente. Solo debe devolver el resultado fiscal calculado.

---

## 2.2 Landed Cost Engine

Responsabilidad:

Calcular costos capitalizables asociados a inventario.

Debe manejar:

* flete
* seguro
* DAI
* ISC capitalizable
* manejo de carga
* gastos portuarios
* almacenamiento
* comisiones de importación
* otros cargos capitalizables
* prorrateo entre ítems
* ajustes de costo
* diferencias entre costo estimado y costo final

No debe registrar inventario directamente. Solo debe devolver el costo asignado por ítem.

---

## 2.3 Settlement Engine

Responsabilidad:

Calcular efectos financieros al momento de pagar o cobrar.

Debe manejar:

* pagos
* cobros
* pagos parciales
* cobros parciales
* retenciones al pago
* retenciones al cobro
* anticipos
* compensaciones
* diferencias cambiarias
* impuestos que se causan al momento del pago/cobro
* saldos pendientes

No debe mover bancos directamente. Solo debe devolver el desglose financiero.

---

# 3. Principio arquitectónico obligatorio

Los tres motores deben ser funciones puras.

Ejemplo conceptual:

```python
result = fiscal_engine.calculate(context)
result = landed_cost_engine.calculate(context)
result = settlement_engine.calculate(context)
```

No deben:

* hacer consultas a la base de datos
* escribir registros
* crear asientos
* modificar inventario
* modificar saldos
* depender de sesiones ORM
* depender de formularios o vistas

Deben recibir un contexto completo y devolver un resultado completo.

---

# 4. Eventos de negocio soportados

El sistema debe trabajar sobre eventos de negocio, no únicamente sobre documentos.

## 4.1 Eventos de compra

```text
purchase_order_created
purchase_receipt_created
purchase_invoice_created
purchase_invoice_confirmed
purchase_debit_note_created
purchase_credit_note_created
purchase_return_created
purchase_payment_created
purchase_payment_confirmed
```

## 4.2 Eventos de venta

```text
sales_order_created
sales_delivery_created
sales_invoice_created
sales_invoice_confirmed
sales_debit_note_created
sales_credit_note_created
sales_return_created
sales_collection_created
sales_collection_confirmed
```

## 4.3 Eventos de inventario

```text
inventory_receipt_created
inventory_receipt_confirmed
inventory_cost_adjustment_created
inventory_cost_adjustment_confirmed
inventory_return_created
```

## 4.4 Eventos de liquidación internacional

```text
import_landed_cost_draft_created
import_landed_cost_confirmed
import_customs_clearance_created
import_customs_clearance_confirmed
```

## 4.5 Eventos financieros

```text
payment_created
payment_confirmed
collection_created
collection_confirmed
payment_reversed
collection_reversed
```

---

# 5. Orquestador de eventos

Debe existir un componente central:

```text
Business Event Orchestrator
```

Responsabilidad:

* recibir el evento
* construir el contexto de cálculo
* invocar los motores necesarios
* consolidar resultados
* enviar resultados al generador contable
* enviar resultados al módulo de inventario
* guardar snapshot del cálculo
* manejar reversión si aplica

Ejemplo:

```text
purchase_invoice_confirmed
 ├── Fiscal Engine
 ├── Landed Cost Engine
 ├── Settlement Engine, si hay pago inmediato
 ├── Accounting Mapper
 ├── Inventory Mapper
 └── Snapshot Writer
```

---

# 6. Contexto común de cálculo

Todos los motores deben recibir un objeto común llamado:

```text
CalculationContext
```

## 6.1 Campos principales

```json
{
  "company_id": 1,
  "document_type": "purchase_invoice",
  "event_type": "purchase_invoice_confirmed",
  "transaction_direction": "purchase",
  "transaction_date": "2026-05-16",
  "posting_date": "2026-05-16",
  "party_type": "supplier",
  "party_id": 25,
  "currency": "USD",
  "company_currency": "NIO",
  "exchange_rate": 36.75,
  "fiscal_exchange_rate": 36.75,
  "price_includes_tax": false,
  "items": [],
  "charges": [],
  "tax_rules": [],
  "settlement": null,
  "rounding_policy": {},
  "accounting_policy": {},
  "references": {}
}
```

---

# 7. Modelo de ítems

Cada línea de producto o servicio debe entregarse al motor con información suficiente.

```json
{
  "line_id": "ITEM-001",
  "item_id": 100,
  "description": "Mercadería importada",
  "quantity": 10,
  "unit_price": 100,
  "gross_amount": 1000,
  "discount_amount": 0,
  "net_amount": 1000,
  "item_type": "inventory",
  "uom": "unit",
  "weight": 25,
  "volume": 0.5,
  "tax_profile_id": 3,
  "cost_center_id": 1,
  "warehouse_id": 2
}
```

---

# 8. Modelo de reglas fiscales

Debe existir una tabla o estructura equivalente:

```text
tax_rule
```

## 8.1 Campos requeridos

* compañía
* nombre
* ámbito: compra, venta, ambos
* nivel: ítem, tercero, transacción
* concepto fiscal
* tipo: impuesto, retención, percepción, cargo, descuento
* cálculo: porcentaje, monto fijo, monto manual, por cantidad
* tasa
* monto
* base de cálculo
* orden
* dependencias
* tratamiento contable
* momento de reconocimiento
* cuenta contable sugerida
* afecta inventario
* afecta costo
* afecta total documento
* afecta pago/cobro
* participa en base de cálculo posterior
* método de prorrateo
* fecha inicio
* fecha fin
* activo

---

# 9. Jerarquía de resolución de reglas

Las reglas deben resolverse en este orden de especificidad:

```text
1. Ítem
2. Tercero: cliente/proveedor
3. Transacción
4. Plantilla predeterminada de compañía
```

La regla más específica prevalece sobre la más general, salvo cuando una regla indique explícitamente que es acumulativa.

## 9.1 Modos de combinación

Cada regla debe tener un campo:

```text
merge_strategy
```

Valores:

* `override`
* `append`
* `exclude`
* `replace_group`

Ejemplo:

```text
Ítem exento     -> excluye IVA
Cliente retenedor -> agrega retención
Transacción importación -> agrega DAI, ISC, flete, seguro
```

---

# 10. Momentos de reconocimiento

Cada impuesto, cargo o retención debe definir cuándo se reconoce.

Valores mínimos:

```text
receipt
invoice
payment
collection
customs_clearance
landed_cost_confirmation
reversal
```

Ejemplos:

* DAI capitalizable: `customs_clearance` o `invoice`
* IVA crédito fiscal: `invoice`
* Retención al proveedor: `payment`
* Retención sufrida por cliente: `collection`
* Flete estimado: `receipt`
* Ajuste de flete real: `landed_cost_confirmation`

---

# 11. Tratamientos contables

Cada línea calculada debe tener un tratamiento contable.

Valores mínimos:

```text
capitalizable_inventory_cost
separate_tax_account
separate_expense_account
withholding_payable
withholding_receivable
revenue_adjustment
payable_adjustment
receivable_adjustment
```

Ejemplos:

DAI:

```text
capitalizable_inventory_cost
```

IVA compra:

```text
separate_tax_account
```

Retención al proveedor:

```text
withholding_payable
```

Retención sufrida en venta:

```text
withholding_receivable
```

---

# 12. Fiscal Engine

## 12.1 Entrada

Recibe:

```text
CalculationContext
```

## 12.2 Salida

Devuelve:

```json
{
  "engine": "fiscal",
  "document_tax_total": 162.23,
  "capitalizable_tax_total": 81.50,
  "separate_tax_total": 162.23,
  "withholding_total": 0,
  "tax_lines": [],
  "audit_trail": [],
  "warnings": [],
  "errors": []
}
```

## 12.3 Línea fiscal calculada

```json
{
  "line_id": "TAX-001",
  "concept": "DAI",
  "type": "tax",
  "rate": 5,
  "calculation_method": "percentage",
  "base_amount": 1000,
  "amount": 50,
  "recognition_event": "customs_clearance",
  "accounting_treatment": "capitalizable_inventory_cost",
  "affects_inventory": true,
  "affects_document_total": true,
  "included_in_price": false,
  "source_rule_id": 10,
  "applies_to_items": ["ITEM-001"],
  "depends_on": [],
  "participates_in_next_base": true
}
```

---

# 13. Cálculo en cascada

El motor debe soportar bases acumuladas.

Ejemplo:

```text
Mercadería: 1000
DAI 5% sobre mercadería = 50
Base acumulada = 1050
ISC 3% sobre mercadería + DAI = 31.50
Base acumulada = 1081.50
IVA 15% sobre mercadería + DAI + ISC = 162.23
```

Cada regla debe poder declarar:

```json
{
  "base_mode": "accumulated",
  "include_concepts": ["goods", "DAI", "ISC"],
  "exclude_concepts": [],
  "participates_in_next_base": true
}
```

---

# 14. Landed Cost Engine

## 14.1 Entrada

Recibe:

* ítems
* cargos capitalizables
* impuestos capitalizables calculados por Fiscal Engine
* reglas de prorrateo
* valores estimados o reales
* moneda y tipo de cambio

## 14.2 Salida

```json
{
  "engine": "landed_cost",
  "base_goods_total": 1000,
  "capitalizable_charges_total": 81.50,
  "inventory_value_total": 1081.50,
  "allocations": [],
  "audit_trail": [],
  "warnings": [],
  "errors": []
}
```

## 14.3 Asignación por ítem

```json
{
  "item_line_id": "ITEM-001",
  "base_amount": 1000,
  "allocated_costs": [
    {
      "concept": "DAI",
      "amount": 50
    },
    {
      "concept": "ISC",
      "amount": 31.50
    }
  ],
  "final_inventory_cost": 1081.50,
  "unit_inventory_cost": 108.15
}
```

---

# 15. Métodos de prorrateo

El Landed Cost Engine debe soportar:

```text
by_value
by_quantity
by_weight
by_volume
equal
manual
```

## 15.1 Prorrateo por valor

```text
proporción = valor del ítem / valor total de ítems
costo asignado = cargo global × proporción
```

Ejemplo:

```text
Ítem A: 600
Ítem B: 400
Total: 1000

Cargo capitalizable: 81.50

A: 48.90
B: 32.60
```

---

# 16. Settlement Engine

## 16.1 Entrada

Recibe:

* documento por pagar o cobrar
* saldo pendiente
* monto del pago/cobro
* moneda
* tipo de cambio
* reglas fiscales al pago/cobro
* retenciones aplicables
* anticipos
* compensaciones

## 16.2 Salida

```json
{
  "engine": "settlement",
  "gross_settlement_amount": 1000,
  "cash_amount": 900,
  "withholding_amount": 100,
  "exchange_difference": 0,
  "remaining_balance": 0,
  "settlement_lines": [],
  "audit_trail": [],
  "warnings": [],
  "errors": []
}
```

## 16.3 Línea de liquidación

```json
{
  "line_id": "SETTLE-001",
  "concept": "Retención IR",
  "type": "withholding",
  "base_amount": 1000,
  "rate": 10,
  "amount": 100,
  "recognition_event": "payment",
  "accounting_treatment": "withholding_payable",
  "account_id": 2105
}
```

---

# 17. Pagos y cobros parciales

El Settlement Engine debe calcular retenciones proporcionalmente.

Ejemplo:

```text
Factura: 1000
Retención total aplicable: 100
Pago parcial: 500

Retención proporcional:
50
```

Resultado:

```text
Dr Proveedor 500
Cr Banco 450
Cr Retención por pagar 50
```

---

# 18. Asociación de motores con eventos

## 18.1 Recepción de compra

Evento:

```text
purchase_receipt_confirmed
```

Motores:

```text
Fiscal Engine, solo impuestos/cargos reconocibles en recepción
Landed Cost Engine
```

Resultado:

```text
Dr Inventario
Cr Mercadería recibida no facturada
```

Incluye solamente:

* costo base
* costos capitalizables estimados
* impuestos capitalizables reconocibles en recepción

No incluye:

* IVA crédito fiscal, salvo que la política indique reconocimiento en recepción

---

## 18.2 Factura de compra

Evento:

```text
purchase_invoice_confirmed
```

Motores:

```text
Fiscal Engine
Landed Cost Engine, si hay costos reales o ajustes
```

Resultado:

```text
Dr Mercadería recibida no facturada
Dr IVA crédito fiscal
Dr Gastos no capitalizables
Cr Proveedor
```

Si existe diferencia entre recepción y factura:

```text
Dr/Cr Ajuste de costo inventario
Dr/Cr Variación de precio/costo
```

---

## 18.3 Liquidación de importación

Evento:

```text
import_landed_cost_confirmed
```

Motores:

```text
Fiscal Engine
Landed Cost Engine
```

Debe calcular:

* FOB
* flete
* seguro
* CIF
* DAI
* ISC
* IVA
* gastos aduaneros
* gastos capitalizables
* gastos no capitalizables
* costo final por ítem

---

## 18.4 Factura de venta

Evento:

```text
sales_invoice_confirmed
```

Motores:

```text
Fiscal Engine
```

Resultado:

```text
Dr Cliente
Cr Ingresos
Cr IVA por pagar
Cr Otros impuestos por pagar
```

Si hay cargos de envío cobrados al cliente:

```text
Dr Cliente
Cr Ingreso por envío / recuperación de gastos
```

---

## 18.5 Cobro de venta

Evento:

```text
collection_confirmed
```

Motores:

```text
Settlement Engine
Fiscal Engine, si hay impuestos o retenciones al cobro
```

Ejemplo con retención sufrida:

```text
Dr Banco
Dr Retención sufrida / anticipo impuesto
Cr Cliente
```

---

## 18.6 Pago a proveedor

Evento:

```text
payment_confirmed
```

Motores:

```text
Settlement Engine
Fiscal Engine, si hay retenciones al pago
```

Ejemplo:

```text
Dr Proveedor
Cr Banco
Cr Retención por pagar
```

---

## 18.7 Nota de crédito

Evento:

```text
purchase_credit_note_confirmed
sales_credit_note_confirmed
```

Motores:

```text
Fiscal Engine en modo reversión
Landed Cost Engine, si afecta inventario
Settlement Engine, si afecta saldos pagados/cobrados
```

Debe poder usar:

```text
reverse(reference_document)
```

No debe recalcular libremente si la nota referencia una factura existente.

---

# 19. Snapshot obligatorio

Al confirmar cualquier documento, el sistema debe guardar un snapshot del cálculo.

Debe guardar:

* reglas aplicadas
* tasas
* bases
* montos
* orden de cálculo
* dependencias
* cuentas sugeridas
* prorrateos
* redondeos
* tipo de cambio
* moneda
* versión de reglas
* resultado de cada motor

Esto permite auditoría y reversión histórica.

---

# 20. Auditoría de cálculo

Cada motor debe devolver un `audit_trail`.

Ejemplo:

```json
{
  "step": 3,
  "concept": "ISC",
  "formula": "1050 * 0.03",
  "base_amount": 1050,
  "rate": 3,
  "result": 31.50,
  "reason": "ISC calculado sobre subtotal acumulado que incluye mercadería + DAI"
}
```

La UI debe poder mostrar:

```text
¿Por qué este impuesto dio este monto?
```

---

# 21. Redondeo

Debe existir una política central de redondeo.

```text
rounding_policy
```

Campos:

* precisión fiscal
* precisión contable
* precisión por moneda
* redondeo por línea
* redondeo por documento
* método:

  * half_up
  * half_even
  * truncate
* manejo de diferencia residual

El sistema debe asignar diferencias mínimas de redondeo a la última línea elegible o a una cuenta de ajuste.

---

# 22. Moneda y tipo de cambio

Debe soportar:

* moneda del documento
* moneda de compañía
* moneda fiscal
* moneda de pago
* tipo de cambio contable
* tipo de cambio fiscal
* tipo de cambio de pago

En importaciones, el tipo de cambio fiscal puede diferir del contable.

---

# 23. Generador contable

Debe existir un componente separado:

```text
Accounting Mapper
```

Responsabilidad:

Convertir resultados de los motores en propuestas de asiento.

Los motores no generan asientos directamente.

Ejemplo:

```text
Motor Result -> Accounting Mapper -> Journal Entry Draft
```

---

# 24. Generador de inventario

Debe existir un componente separado:

```text
Inventory Mapper
```

Responsabilidad:

Convertir resultado del Landed Cost Engine en movimientos de inventario.

Ejemplo:

```text
Landed Cost Result -> Inventory Mapper -> Stock Ledger Entry
```

---

# 25. Estados de ejecución

Los motores deben soportar tres modos:

```text
simulation
draft
confirmed
```

## simulation

* no guarda nada
* usado para previsualización

## draft

* calcula y permite editar documento

## confirmed

* calcula
* congela snapshot
* permite contabilización
* permite inventario
* permite cuentas por cobrar/pagar

---

# 26. Validaciones mínimas

El sistema debe validar:

* regla sin cuenta contable
* impuesto sin base
* regla circular
* regla vencida
* tasa inválida
* moneda sin tipo de cambio
* cargo capitalizable sin método de prorrateo
* retención al pago sin cuenta de retención
* impuesto incluido en precio sin método de extracción
* nota de crédito sin documento referencia, si requiere reversión exacta
* diferencias entre recepción y factura sin política de ajuste

---

# 27. Errores bloqueantes y advertencias

Los motores deben devolver:

```json
{
  "errors": [],
  "warnings": []
}
```

Errores bloquean confirmación.

Advertencias permiten continuar con autorización.

Ejemplo error:

```text
El cargo "Flete internacional" es capitalizable pero no tiene método de prorrateo.
```

Ejemplo advertencia:

```text
El tipo de cambio fiscal difiere del tipo de cambio contable.
```

---

# 28. Diseño de módulos sugerido

```text
accounting_engine/
├── common/
│   ├── money.py
│   ├── rounding.py
│   ├── currency.py
│   ├── context.py
│   └── result.py
│
├── fiscal/
│   ├── engine.py
│   ├── rules.py
│   ├── resolver.py
│   ├── calculator.py
│   └── audit.py
│
├── landed_cost/
│   ├── engine.py
│   ├── allocator.py
│   ├── adjustment.py
│   └── audit.py
│
├── settlement/
│   ├── engine.py
│   ├── withholding.py
│   ├── payment.py
│   ├── exchange_difference.py
│   └── audit.py
│
├── orchestration/
│   ├── event_orchestrator.py
│   ├── event_registry.py
│   └── pipeline.py
│
├── mapping/
│   ├── accounting_mapper.py
│   └── inventory_mapper.py
│
└── snapshots/
    ├── serializer.py
    └── reverser.py
```

---

# 29. Ejemplo completo: compra internacional

Entrada:

```text
Mercadería: 1000
DAI: 5%
ISC: 3%
IVA: 15%
```

Cálculo:

```text
Mercadería: 1000.00
DAI: 50.00
Subtotal: 1050.00
ISC: 31.50
Subtotal: 1081.50
IVA: 162.23
Total factura: 1243.73
Costo inventario: 1081.50
```

Recepción:

```text
Dr Inventario                         1081.50
Cr Mercadería recibida no facturada   1081.50
```

Factura:

```text
Dr Mercadería recibida no facturada   1081.50
Dr IVA crédito fiscal                  162.23
Cr Proveedor                          1243.73
```

---

# 30. Criterio de aceptación principal

La implementación será aceptada cuando:

* compras y ventas usen el mismo Fiscal Engine
* costos de importación usen Landed Cost Engine
* pagos y cobros usen Settlement Engine
* ningún documento calcule impuestos directamente
* los impuestos se puedan configurar por ítem, tercero y transacción
* los cargos capitalizables aumenten inventario
* los impuestos no capitalizables vayan a cuenta separada
* los pagos parciales calculen retenciones proporcionalmente
* exista snapshot auditable
* las notas de crédito puedan revertir cálculos históricos
* el sistema soporte simulación antes de confirmar documentos
