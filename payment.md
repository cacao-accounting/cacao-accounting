Sí. Esto es **crítico** y debe tratarse como cierre funcional de **Payment Entry**, no solo como mejora visual.

La pantalla actual de Cacao Accounting está incompleta para AP/AR porque solo captura encabezado del pago, tercero, cuenta, impuestos/cargos y comentario, pero **no tiene una tabla explícita de referencias aplicadas**. Sin esa tabla no se puede controlar correctamente:

```text
Factura A -> saldo pendiente individual
Factura B -> saldo pendiente individual
Nota débito -> saldo pendiente individual
Nota crédito -> saldo a favor individual
Pago X -> aplicado parcialmente a N documentos
Documento Y -> afectado por N pagos
```

El modelo correcto es el de la primera imagen: un pago tiene encabezado, monto, tercero, cuenta bancaria y una sección central de **Referencias del Pago** donde se ve exactamente qué documentos fueron afectados y por cuánto.

---

# Requerimiento funcional: cierre de Payment Entry con referencias aplicadas

## 1. Objetivo

Rediseñar y completar la funcionalidad de **Entrada de Pago / Payment Entry** para que soporte correctamente:

* pagos a proveedores;
* cobros de clientes;
* anticipos;
* reembolsos;
* pagos no aplicados;
* aplicación parcial o total a N documentos;
* conciliación futura de pagos abiertos contra facturas/notas;
* control individual de saldos AP/AR por transacción.

El pago debe poder existir en dos modalidades:

```text
Pago aplicado
Pago no aplicado / abierto
```

Un pago aplicado afecta una o varias facturas, notas débito, notas crédito u otros documentos permitidos.

Un pago no aplicado no afecta ningún documento fuente todavía, pero queda disponible para conciliación/aplicación futura.

---

# 2. Principio funcional obligatorio

La relación entre pagos y documentos es **muchos a muchos**:

```text
Un PaymentEntry puede aplicar a N documentos.
Un documento puede recibir N pagos.
```

Por tanto, el saldo de AP/AR **no puede vivir solo en el encabezado del pago**. Debe calcularse por documento fuente usando sus referencias aplicadas.

Ejemplo:

```text
Factura Venta FV-001 total 1,000
Pago P-001 aplica 300
Pago P-002 aplica 500
Saldo FV-001 = 200
```

Ejemplo inverso:

```text
Pago P-003 total 1,500
Aplica 700 a FV-010
Aplica 500 a FV-011
Queda 300 sin aplicar
```

---

# 3. UX requerida para Payment Entry

La pantalla debe aproximarse al patrón de la primera imagen.

## 3.1 Encabezado

El formulario debe organizarse en secciones claras:

```text
Tipo de Pago
Pago de / a
Cuentas
Importe
Referencia
Deducciones o Pérdida
ID de transacción
Dimensiones contables
Más información
```

No es necesario copiar exactamente el layout, pero sí la estructura funcional.

---

## 3.2 Sección: Tipo de Pago

Campos requeridos:

| Campo                    | Requerido | Descripción                                       |
| ------------------------ | --------: | ------------------------------------------------- |
| Tipo de pago             |        Sí | Pago saliente, pago entrante, reembolso, anticipo |
| Fecha de contabilización |        Sí | Fecha contable del pago                           |
| Modo de pago             |        Sí | Transferencia, cheque, efectivo, tarjeta, etc.    |
| Compañía                 |        Sí | Empresa dueña del pago                            |
| Secuencia                |        Sí | Serie/secuencia documental                        |

El campo actual `Tipo de transacción` puede mantenerse, pero debe ser semánticamente claro:

```text
Pago saliente / Pago a proveedor
Pago entrante / Cobro de cliente
Reembolso recibido de proveedor
Reembolso pagado a cliente
Anticipo a proveedor
Anticipo de cliente
```

---

## 3.3 Sección: Pago de / a

Campos requeridos:

| Campo           | Requerido | Descripción                                  |
| --------------- | --------: | -------------------------------------------- |
| Tipo tercero    |        Sí | Cliente / Proveedor                          |
| Tercero         |        Sí | Cliente o proveedor                          |
| Nombre de parte |        No | Nombre legible congelado al momento del pago |

Reglas:

* Si viene desde factura de compra: tercero = proveedor.
* Si viene desde factura de venta: tercero = cliente.
* Si viene desde nota crédito compra: tercero = proveedor.
* Si viene desde nota crédito venta: tercero = cliente.
* Si el pago es manual no aplicado, el usuario debe seleccionar tercero.

---

## 3.4 Sección: Cuentas

Campos requeridos:

| Campo              |             Requerido | Descripción                              |
| ------------------ | --------------------: | ---------------------------------------- |
| Cuenta bancaria    |                    Sí | Cuenta desde/hacia donde se mueve dinero |
| Moneda             |                    Sí | Moneda de la cuenta bancaria o del pago  |
| Cuenta AP/AR       |      Sí cuando aplica | Cuenta por pagar/cobrar asociada         |
| Cuenta de anticipo |     Sí para anticipos | Cuenta puente de anticipos               |
| Tipo de cambio     | Sí si hay multimoneda | Tasa usada para contabilizar             |

La moneda debe venir preferiblemente de la cuenta bancaria. Si el documento origen tiene moneda diferente, el backend debe manejar conversión.

---

# 4. Sección crítica: Referencias del Pago

Debe agregarse una tabla obligatoria llamada:

```text
Referencias del Pago
```

Esta tabla es el núcleo funcional.

## 4.1 Columnas mínimas

| Columna                       | Descripción                                                               |
| ----------------------------- | ------------------------------------------------------------------------- |
| Seleccionar                   | Checkbox para eliminar/aplicar acciones                                   |
| No.                           | Número de línea                                                           |
| Tipo                          | Factura compra, factura venta, nota débito, nota crédito, orden, anticipo |
| Documento                     | Número del documento referenciado                                         |
| Fecha                         | Fecha del documento                                                       |
| Total                         | Total del documento                                                       |
| Saldo pendiente               | Saldo antes de este pago                                                  |
| Monto aplicado                | Monto aplicado en este pago                                               |
| Descuento                     | Descuento aplicado, si aplica                                             |
| Diferencia / Ganancia-Pérdida | Diferencia cambiaria o ajuste                                             |
| Moneda                        | Moneda del documento                                                      |
| Ver / Editar                  | Link al documento origen                                                  |

## 4.2 Comportamiento requerido

La tabla debe permitir:

* cargar líneas automáticamente cuando el pago se crea desde una factura/nota/orden;
* agregar documentos manualmente del mismo tercero;
* eliminar líneas;
* editar `monto_aplicado`;
* aplicar parcialmente;
* aplicar totalmente;
* dejar parte del pago sin aplicar;
* impedir aplicar más que el saldo pendiente;
* impedir mezclar clientes/proveedores distintos;
* impedir mezclar compañías distintas;
* permitir N documentos en un solo pago;
* permitir que un documento reciba N pagos en diferentes momentos.

---

# 5. Totales del pago

Debajo de la tabla de referencias debe existir una sección de resumen.

Campos calculados:

| Campo                      | Fórmula                                       |
| -------------------------- | --------------------------------------------- |
| Monto total pagado/cobrado | Valor del encabezado del pago                 |
| Total aplicado             | Suma de `monto_aplicado` en referencias       |
| Monto sin asignar          | `monto_total - total_aplicado`                |
| Diferencia de monto        | Diferencia por redondeo, multimoneda o ajuste |
| Total impuestos/cargos     | Suma de cargos/deducciones si aplica          |

Regla crítica:

```text
Monto sin asignar >= 0
```

Debe permitirse guardar/aprobar un pago con monto sin asignar mayor que cero. Ese monto queda como **pago abierto**.

Ejemplo:

```text
Pago recibido: 1,000
Aplicado a facturas: 700
Monto sin asignar: 300
```

Ese saldo debe quedar disponible para reconciliación futura.

---

# 6. Pago no aplicado / pago abierto

El sistema debe permitir crear un pago sin referencias.

## 6.1 Casos válidos

* Cliente paga por adelantado sin factura.
* Proveedor devuelve dinero sin documento aplicado todavía.
* Banco registra depósito no identificado.
* Se recibe transferencia y luego se conciliará con facturas.
* Se paga a proveedor y luego se aplicará contra facturas futuras.
* Migración de saldos iniciales.

## 6.2 Reglas

Un pago sin referencias:

* debe tener compañía;
* debe tener tercero, salvo depósitos no identificados si se decide soportarlos;
* debe tener cuenta bancaria;
* debe tener monto;
* debe generar movimiento bancario;
* debe generar contabilidad contra cuenta puente;
* no debe reducir saldo de ninguna factura/nota;
* debe quedar con `unallocated_amount > 0`;
* debe aparecer en una futura pantalla de conciliación/aplicación.

---

# 7. Conciliación futura

Debe diseñarse desde ahora para soportar una función futura:

```text
Conciliar / Aplicar Pago
```

Esta función permitirá tomar pagos abiertos y aplicarlos contra facturas/notas.

## 7.1 Flujo futuro esperado

```text
Pago abierto
→ Conciliar con documentos pendientes
→ Seleccionar facturas/notas
→ Definir montos aplicados
→ Guardar aplicación
→ Reducir saldo de documentos
→ Reducir monto sin asignar del pago
```

## 7.2 Requerimiento técnico de preparación

Aunque la UI de reconciliación se implemente después, el modelo debe quedar listo.

Debe existir capacidad para:

* crear `PaymentEntry` sin `PaymentReference`;
* agregar referencias después de aprobado;
* preservar auditoría de cuándo se aplicó cada referencia;
* no recalcular incorrectamente asientos bancarios;
* generar asiento adicional solo si la aplicación mueve saldo entre cuentas puente y AP/AR.

---

# 8. Modelo de datos requerido

## 8.1 PaymentEntry

Debe tener o validar funcionalmente estos campos:

| Campo                | Uso                                     |
| -------------------- | --------------------------------------- |
| `id`                 | Identificador interno                   |
| `document_no`        | Número visible                          |
| `company`            | Compañía                                |
| `posting_date`       | Fecha contable                          |
| `payment_type`       | `pay` / `receive`                       |
| `party_type`         | `supplier` / `customer`                 |
| `party_id`           | Tercero                                 |
| `bank_account_id`    | Cuenta bancaria                         |
| `currency`           | Moneda del pago                         |
| `exchange_rate`      | Tipo de cambio                          |
| `paid_amount`        | Monto total del pago                    |
| `allocated_amount`   | Total aplicado                          |
| `unallocated_amount` | Monto abierto                           |
| `difference_amount`  | Diferencia / ajuste                     |
| `reference_no`       | Cheque / transferencia / número externo |
| `reference_date`     | Fecha de referencia                     |
| `mode_of_payment`    | Modo de pago                            |
| `docstatus`          | Borrador/aprobado/anulado               |
| `remarks`            | Comentarios                             |

Si `allocated_amount` y `unallocated_amount` no se guardan físicamente, deben calcularse consistentemente desde referencias.

---

## 8.2 PaymentReference

Debe existir una tabla de detalle para referencias.

Campos requeridos:

| Campo                                    | Uso                           |
| ---------------------------------------- | ----------------------------- |
| `id`                                     | ID línea                      |
| `payment_entry_id`                       | Pago padre                    |
| `reference_type`                         | Tipo físico del documento     |
| `reference_doctype` / `flow_source_type` | Tipo lógico real              |
| `reference_id`                           | ID documento                  |
| `reference_document_no`                  | Número visible congelado      |
| `reference_date`                         | Fecha del documento           |
| `party_type`                             | Cliente/proveedor             |
| `party_id`                               | Tercero                       |
| `company`                                | Compañía                      |
| `currency`                               | Moneda del documento          |
| `total_amount`                           | Total del documento           |
| `outstanding_amount_before`              | Saldo antes de aplicar        |
| `allocated_amount`                       | Monto aplicado por esta línea |
| `outstanding_amount_after`               | Saldo posterior               |
| `exchange_rate`                          | Tasa si aplica                |
| `difference_amount`                      | Diferencia cambiaria/redondeo |
| `discount_amount`                        | Descuento aplicado            |
| `created_at`                             | Auditoría                     |
| `created_by`                             | Usuario                       |
| `cancelled_at`                           | Si se anula                   |
| `cancelled_by`                           | Usuario que anuló             |

---

# 9. Cálculo de saldos AP/AR

Debe existir una función centralizada:

```python
compute_outstanding_amount(document)
```

o equivalente, que use:

```text
Total del documento
- suma de PaymentReference aprobadas/no anuladas
- aplicaciones de notas crédito si aplica
+ ajustes según tipo documental
```

## 9.1 Reglas por documento

| Documento           | Saldo representa                                       |
| ------------------- | ------------------------------------------------------ |
| Factura compra      | Monto pendiente de pagar al proveedor                  |
| Nota débito compra  | Monto pendiente de pagar al proveedor                  |
| Nota crédito compra | Monto a favor de la empresa / reembolsable o aplicable |
| Factura venta       | Monto pendiente de cobrar al cliente                   |
| Nota débito venta   | Monto pendiente de cobrar al cliente                   |
| Nota crédito venta  | Monto a favor del cliente / reembolsable o aplicable   |

Todas las notas deben manejar `grand_total` positivo. La semántica se determina por `document_type`.

---

# 10. Reglas de aprobación

Al aprobar un pago:

## 10.1 Validar encabezado

* compañía obligatoria;
* tercero obligatorio, salvo caso explícito de depósito no identificado;
* cuenta bancaria obligatoria;
* moneda obligatoria;
* monto mayor que cero;
* fecha obligatoria;
* secuencia obligatoria;
* cuenta bancaria pertenece a la compañía;
* modo de pago obligatorio si el sistema lo requiere.

## 10.2 Validar referencias

Para cada referencia:

* documento existe;
* documento está aprobado;
* documento no está anulado;
* documento pertenece a la misma compañía;
* documento pertenece al mismo tercero;
* documento tiene saldo abierto;
* monto aplicado > 0;
* monto aplicado <= saldo abierto;
* moneda compatible o con tipo de cambio;
* no duplicar la misma referencia en el mismo pago.

## 10.3 Permitir sin referencias

Debe permitirse aprobar sin referencias si:

```text
paid_amount > 0
allocated_amount = 0
unallocated_amount = paid_amount
```

Esto debe tratarse como pago abierto.

---

# 11. Contabilidad requerida

## 11.1 Pago aplicado a factura compra / nota débito compra

```text
Dr Cuentas por Pagar
Cr Banco
```

## 11.2 Cobro aplicado a factura venta / nota débito venta

```text
Dr Banco
Cr Cuentas por Cobrar
```

## 11.3 Reembolso recibido por nota crédito compra

```text
Dr Banco
Cr Saldo a favor proveedor / AP clearing
```

## 11.4 Reembolso pagado por nota crédito venta

```text
Dr Saldo a favor cliente / AR clearing
Cr Banco
```

## 11.5 Anticipo a proveedor no aplicado

```text
Dr Anticipos a Proveedores
Cr Banco
```

## 11.6 Anticipo de cliente no aplicado

```text
Dr Banco
Cr Anticipos de Clientes
```

## 11.7 Pago recibido no aplicado de cliente

```text
Dr Banco
Cr Anticipos de Clientes / Pagos no aplicados clientes
```

## 11.8 Pago no aplicado a proveedor

```text
Dr Anticipos a Proveedores / Pagos no aplicados proveedores
Cr Banco
```

Las cuentas puente deben venir de configuración contable de compañía, no hardcodeadas.

---

# 12. Trazabilidad documental

Al aprobar un pago con referencias, debe crear relaciones:

```text
documento_origen -> payment_entry
```

Ejemplos:

```text
purchase_invoice -> payment_entry
sales_invoice -> payment_entry
purchase_debit_note -> payment_entry
sales_debit_note -> payment_entry
purchase_credit_note -> payment_entry
sales_credit_note -> payment_entry
```

Para anticipos desde orden:

```text
purchase_order -> payment_entry
sales_order -> payment_entry
```

Para pago abierto sin referencia:

```text
No hay relación documental a factura/nota.
Sí puede existir relación si nació desde una orden.
```

Cuando luego se concilie, deberá crearse la relación en ese momento.

---

# 13. UI propuesta para Cacao Accounting

## Encabezado

```text
Tipo de transacción: Pago entrante / Pago saliente
Compañía
Secuencia
Cuenta bancaria
Moneda
Fecha
Monto total
```

## Tercero

```text
Tipo tercero
Tercero
Nombre del tercero
```

## Referencias del Pago

Tabla:

```text
[+] Agregar documento
[ ] No. | Tipo | Documento | Fecha | Total | Saldo pendiente | Monto aplicado | Moneda | Ver
```

Acciones:

```text
Agregar factura
Agregar nota débito
Agregar nota crédito
Aplicar saldo automáticamente
Limpiar referencias
```

## Resumen

```text
Monto total
Total aplicado
Monto sin asignar
Diferencia
Impuestos/cargos
```

## Deducciones y cargos

```text
Cuenta
Centro de costo
Monto
Descripción
```

## Referencia bancaria

```text
Número externo / cheque / transferencia
Fecha de referencia
Contador externo
```

---

# 14. Comportamiento desde “Crear”

## Desde factura compra

Debe abrir pago con:

```text
payment_type = pay
party_type = supplier
party = proveedor
references = [factura]
allocated_amount = saldo factura
paid_amount = saldo factura
unallocated_amount = 0
```

## Desde factura venta

```text
payment_type = receive
party_type = customer
party = cliente
references = [factura]
allocated_amount = saldo factura
paid_amount = saldo factura
unallocated_amount = 0
```

## Desde orden compra

```text
payment_type = pay
party_type = supplier
party = proveedor
references = []
paid_amount = total orden o 0 editable
unallocated_amount = paid_amount
is_advance = true
source_order = orden
```

## Desde orden venta

```text
payment_type = receive
party_type = customer
party = cliente
references = []
paid_amount = total orden o 0 editable
unallocated_amount = paid_amount
is_advance = true
source_order = orden
```

## Desde nota crédito compra

```text
payment_type = receive
party_type = supplier
references = [nota_credito_compra]
```

## Desde nota crédito venta

```text
payment_type = pay
party_type = customer
references = [nota_credito_venta]
```

## Desde nota débito compra

```text
payment_type = pay
party_type = supplier
references = [nota_debito_compra]
```

## Desde nota débito venta

```text
payment_type = receive
party_type = customer
references = [nota_debito_venta]
```

---

# 15. Casos de prueba obligatorios

## 15.1 Pago aplicado a una factura

* Crear factura venta por 1,000.
* Crear cobro por 600.
* Validar saldo factura = 400.
* Crear segundo cobro por 400.
* Validar saldo factura = 0.

## 15.2 Pago aplicado a múltiples facturas

* Crear facturas por 300, 400, 500.
* Crear pago por 1,000.
* Aplicar 300, 400, 300.
* Validar saldos: 0, 0, 200.
* Validar pago sin asignar = 0.

## 15.3 Pago parcialmente no aplicado

* Crear pago recibido por 1,000.
* Aplicar 700 a factura.
* Validar pago sin asignar = 300.
* Validar factura reducida en 700.
* Validar los 300 quedan disponibles.

## 15.4 Pago sin referencias

* Crear pago recibido por 500 sin referencias.
* Aprobar.
* Validar que no cambia saldo de facturas.
* Validar `unallocated_amount = 500`.
* Validar asiento contra cuenta puente.

## 15.5 Documento con múltiples pagos

* Factura compra por 1,000.
* Pago 1 por 250.
* Pago 2 por 300.
* Pago 3 por 450.
* Validar saldo = 0.
* Validar downstream de factura muestra tres pagos.

## 15.6 No permitir sobreaplicación

* Factura con saldo 100.
* Intentar aplicar 150.
* Debe fallar.

## 15.7 Nota crédito de venta reembolsada

* Crear nota crédito venta por 200.
* Crear reembolso por 200.
* Validar saldo nota = 0.
* Validar `payment_type = pay`.

## 15.8 Nota crédito de compra reembolsada

* Crear nota crédito compra por 200.
* Crear reembolso recibido por 200.
* Validar saldo nota = 0.
* Validar `payment_type = receive`.

## 15.9 Anulación

* Crear pago aplicado.
* Aprobar.
* Validar saldo reducido.
* Anular pago.
* Validar saldo restaurado.
* Validar asiento reversado o anulado.
* Validar relación documental conserva auditoría.

---

# 16. Criterios de aceptación

La implementación se considera cerrada cuando:

* [ ] El formulario de pago incluye tabla **Referencias del Pago**.
* [ ] Un pago puede aplicar a N documentos.
* [ ] Un documento puede recibir N pagos.
* [ ] El pago puede guardarse/aprobarse sin referencias.
* [ ] El pago sin referencias queda con monto abierto.
* [ ] El pago parcialmente aplicado deja saldo sin asignar.
* [ ] Facturas y notas calculan saldo por referencias aplicadas.
* [ ] No se permite aplicar más que el saldo pendiente.
* [ ] No se permite mezclar terceros/compañías incompatibles.
* [ ] Se generan relaciones documentales por cada referencia aplicada.
* [ ] Se genera asiento contable correcto.
* [ ] La anulación restaura saldos.
* [ ] El diseño queda listo para conciliación futura de pagos abiertos.
* [ ] Existen pruebas para pagos múltiples, documentos con múltiples pagos y pagos no aplicados.

---

# Conclusión

Este cambio es obligatorio antes de considerar cerrada la implementación de bancos/AP/AR.

La pantalla actual sirve para capturar un movimiento bancario simple, pero no para un ERP contable con saldos por documento. La nueva implementación debe girar alrededor de:

```text
PaymentEntry
PaymentReference
allocated_amount
unallocated_amount
outstanding_amount por documento
```

Sin esa tabla de referencias, AP y AR no pueden ser confiables.
