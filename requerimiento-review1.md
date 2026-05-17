Sí. Para culminar esta implementación y poder acoplarla a transacciones, falta cerrar estas piezas. El estado actual ya declara motores, snapshots, tests y un mapper contable inicial, pero el propio diff muestra que todavía son componentes preliminares: CalculationContext ya incluye moneda/tipo de cambio y referencias contables, y existe un AccountingMapper, pero aún no hay integración transaccional completa ni garantías contables fuertes.  

Requerimiento final de implementación

1. Completar el Mapping Contable

Implementar un Accounting Mapping Layer definitivo que convierta los resultados de los motores en asientos proforma balanceados por evento.

Debe cubrir como mínimo:

purchase_receipt_confirmed
purchase_invoice_confirmed
import_landed_cost_confirmed
sales_invoice_confirmed
payment_confirmed
collection_confirmed
purchase_credit_note_confirmed
sales_credit_note_confirmed

Debe producir:

JournalEntryProforma
JournalEntryLineProforma[]

con:

cuenta contable
débito
crédito
moneda documento
moneda compañía
tipo de cambio
tercero
centro de costo
referencia documental
descripción auditable

Debe garantizar:

total débitos = total créditos

Si no puede balancear, debe devolver error bloqueante.


---

2. Definir cuentas obligatorias por tratamiento contable

Cada accounting_treatment debe tener una cuenta resoluble.

Requerir mapeos para:

capitalizable_inventory_cost
separate_tax_account
separate_expense_account
withholding_payable
withholding_receivable
revenue
inventory
grni
accounts_payable
accounts_receivable
bank
exchange_gain
exchange_loss
rounding_difference

Si falta una cuenta, la transacción no debe confirmarse.


---

3. Implementar Mapping para compras

Compra con recepción

Evento:

purchase_receipt_confirmed

Debe generar:

Dr Inventario
Cr Mercadería recibida no facturada / GRNI

Por el costo inventariable calculado por Landed Cost Engine.

Factura de compra

Evento:

purchase_invoice_confirmed

Debe generar:

Dr GRNI
Dr IVA crédito fiscal / impuestos separados
Dr Gastos no capitalizables
Cr Proveedor

Si no existe recepción previa:

Dr Inventario / Gasto
Dr Impuestos separados
Cr Proveedor


---

4. Implementar Mapping para importaciones

Evento:

import_landed_cost_confirmed

Debe mapear:

mercadería
flete internacional
seguro
gastos aduana
DAI
ISC
IVA
transporte local

Según tratamiento:

capitalizable -> inventario
cuenta separada -> impuesto recuperable / impuesto por pagar
gasto separado -> gasto

Debe soportar varios proveedores/acreedores:

proveedor mercancía
naviera
aseguradora
aduana
transportista local


---

5. Implementar Mapping para ventas

Evento:

sales_invoice_confirmed

Debe generar:

Dr Cliente
Cr Ingresos
Cr IVA débito fiscal / impuestos por pagar
Cr Cargos facturados al cliente

Si hay descuentos:

Dr Descuentos sobre ventas
Cr Cliente / reduce ingresos

según política contable.


---

6. Implementar Mapping para pagos y cobros

Pago a proveedor

Evento:

payment_confirmed

Debe generar:

Dr Proveedor
Cr Banco
Cr Retención por pagar
Dr/Cr Diferencia cambiaria

Cobro de cliente

Evento:

collection_confirmed

Debe generar:

Dr Banco
Dr Retención sufrida / anticipo impuesto
Dr/Cr Diferencia cambiaria
Cr Cliente

Debe soportar pagos/cobros parciales.


---

7. Implementar Multimoneda real

Ahora existen currency, company_currency, exchange_rate y fiscal_exchange_rate, pero falta que afecten todos los resultados contables. 

Debe agregarse a cada monto:

amount_transaction_currency
amount_company_currency
exchange_rate_used
exchange_rate_source

Mínimo requerido:

moneda documento
moneda compañía
moneda fiscal
moneda de pago/cobro
tipo de cambio contable
tipo de cambio fiscal
tipo de cambio de liquidación


---

8. Diferencias cambiarias

Settlement Engine debe calcular:

ganancia cambiaria realizada
pérdida cambiaria realizada

Casos mínimos:

factura USD, pago NIO
factura USD, pago USD, compañía NIO
factura a TC 36.50, pago a TC 36.80

Debe generar líneas contables contra:

exchange_gain
exchange_loss


---

9. Builder de contexto por transacción

Para que sea fácil de implementar en transacciones, crear builders:

PurchaseReceiptCalculationBuilder
PurchaseInvoiceCalculationBuilder
ImportLandedCostCalculationBuilder
SalesInvoiceCalculationBuilder
PaymentCalculationBuilder
CollectionCalculationBuilder
CreditNoteCalculationBuilder

Cada builder debe convertir modelos actuales del sistema en CalculationContext.

Las vistas/formularios no deben armar el contexto manualmente.


---

10. API interna simple para transacciones

Crear una interfaz única:

preview = calculation_service.preview(document)
result = calculation_service.confirm(document)
reversal = calculation_service.reverse(document)

Debe devolver:

fiscal_result
landed_cost_result
settlement_result
journal_proforma
inventory_proforma
snapshot
errors
warnings


---

11. Inventory Mapper

Falta un mapper equivalente al contable.

Debe convertir LandedCostResult en:

Stock Ledger Proforma
Inventory Valuation Proforma
Unit Cost Update Proforma

Debe cubrir:

entrada a bodega
ajuste de costo
reversión de entrada
devolución


---

12. Validadores bloqueantes

Antes de confirmar cualquier transacción, validar:

cuenta contable faltante
tipo de cambio faltante
moneda inválida
regla vencida
dependencia circular
dependencia inexistente
cargo capitalizable sin método de prorrateo
ítem inventariable sin bodega
ítem con cantidad cero
retención sin evento de reconocimiento
proforma contable desbalanceada
snapshot no serializable


---

13. Errores estructurados

Reemplazar strings simples por objetos:

EngineError(
    code="MISSING_ACCOUNT",
    message="Falta cuenta contable para IVA crédito fiscal",
    severity="blocking",
    source="accounting_mapper"
)

Niveles:

blocking
warning
info

Esto es necesario para UI y para impedir confirmaciones incorrectas.


---

14. Snapshots completos

El snapshot actual ya existe, pero debe incluir también:

journal_proforma
inventory_proforma
exchange rates usados
cuentas contables resueltas
versión de reglas
versión de motores
fingerprint
usuario que confirmó
documento origen
documentos relacionados

El diff ya incluye fingerprint de snapshot, lo cual va en buena dirección, pero debe cubrir también efectos contables e inventario. 


---

15. Reversión completa

La reversión no debe limitarse a Fiscal y Landed Cost.

Debe revertir:

fiscal_result
landed_cost_result
settlement_result
journal_proforma
inventory_proforma
diferencias cambiarias
retenciones

Actualmente la reversión del snapshot cubre fiscal y landed cost, pero no completa todo el ciclo contable/financiero. 


---

16. Tests que faltan

Agregar pruebas obligatorias para:

asiento balanceado de compra
asiento balanceado de venta
asiento balanceado de importación
asiento balanceado de pago con retención
asiento balanceado de cobro con retención
factura USD con compañía NIO
pago con tipo de cambio distinto
diferencia cambiaria realizada
error por cuenta faltante
error por tipo de cambio faltante
builder de purchase invoice
builder de sales invoice
builder de payment
snapshot incluye journal proforma
reversión revierte journal proforma


---

Orden recomendado de implementación

Fase 1 — Cerrar contratos

EngineError
MoneyAmount / CurrencyAmount
AccountingMappingContext
InventoryMappingContext
JournalEntryProforma definitivo
InventoryProforma

Fase 2 — Mapping contable

compras
ventas
importaciones
pagos
cobros
retenciones
diferencias cambiarias

Fase 3 — Multimoneda

montos duales
tipo de cambio fiscal
tipo de cambio contable
tipo de cambio settlement
ganancia/pérdida cambiaria

Fase 4 — Builders de transacción

PurchaseReceiptBuilder
PurchaseInvoiceBuilder
ImportLandedCostBuilder
SalesInvoiceBuilder
PaymentBuilder
CollectionBuilder

Fase 5 — Acoplamiento progresivo

1. Importación
2. Recepción de compra
3. Factura de compra
4. Factura de venta
5. Pago
6. Cobro
7. Notas crédito/débito

Criterio final para avanzar

No acoples todavía hasta que puedas afirmar esto:

Dado un documento,
el sistema puede previsualizar cálculo fiscal,
costo inventariable,
settlement,
asiento contable,
movimiento de inventario,
snapshot y errores bloqueantes
sin guardar nada.

Cuando eso esté listo, el acoplamiento a transacciones será limpio.
