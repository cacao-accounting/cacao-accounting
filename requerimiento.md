Sí. La implementación de **pagos/cobros/reembolsos** es el siguiente cierre natural, porque el patch ya dejó habilitada la navegación documental hacia `payment_entry` desde facturas, órdenes y notas débito/crédito, pero falta asegurar que el pago sea **contablemente correcto**, trazable y usable en escenarios reales. El patch actual ya soporta `from_purchase_order`, `from_sales_order`, `from_purchase_credit_note`, `from_purchase_debit_note`, `from_sales_credit_note` y `from_sales_debit_note`, y define el perfil de pago/cobro según el tipo documental origen. 

# Requerimiento técnico para cerrar la implementación de pagos

## 1. Objetivo

Completar la funcionalidad de **Pagos / Cobros / Reembolsos / Anticipos** en Bancos para que `payment_entry` pueda operar correctamente como documento puente entre:

```text
Compras → Cuentas por Pagar → Bancos → Contabilidad
Ventas → Cuentas por Cobrar → Bancos → Contabilidad
Notas Crédito/Débito → Bancos → Contabilidad
Órdenes → Anticipos → Aplicación futura
```

La implementación debe cubrir:

* pago a proveedor;
* cobro de cliente;
* anticipo a proveedor;
* anticipo de cliente;
* reembolso recibido de proveedor;
* reembolso pagado a cliente;
* pago de nota débito de compra;
* cobro de nota débito de venta;
* aplicación parcial o total contra documentos fuente;
* trazabilidad documental;
* afectación contable;
* saldos abiertos.

---

# 2. Tipos funcionales de pago

El sistema debe diferenciar explícitamente estos escenarios.

| Origen              |          Acción | `party_type` | `payment_type` | Semántica                         |
| ------------------- | --------------: | ------------ | -------------- | --------------------------------- |
| Factura de Compra   |      Crear Pago | supplier     | pay            | Pago a proveedor                  |
| Factura de Venta    |     Crear Cobro | customer     | receive        | Cobro de cliente                  |
| Orden de Compra     |  Crear Anticipo | supplier     | pay            | Anticipo a proveedor              |
| Orden de Venta      |  Crear Anticipo | customer     | receive        | Anticipo de cliente               |
| Nota Débito Compra  |      Crear Pago | supplier     | pay            | Pago de cargo adicional           |
| Nota Crédito Compra | Crear Reembolso | supplier     | receive        | Entrada de dinero desde proveedor |
| Nota Débito Venta   |     Crear Cobro | customer     | receive        | Cobro de cargo adicional          |
| Nota Crédito Venta  | Crear Reembolso | customer     | pay            | Salida de dinero hacia cliente    |

El mapping que ya existe en el patch es correcto como base funcional:

```python
"purchase_invoice": ("supplier", "pay")
"sales_invoice": ("customer", "receive")
"purchase_order": ("supplier", "pay")
"sales_order": ("customer", "receive")
"purchase_credit_note": ("supplier", "receive")
"purchase_debit_note": ("supplier", "pay")
"sales_credit_note": ("customer", "pay")
"sales_debit_note": ("customer", "receive")
```

Debe mantenerse, pero ahora debe conectarse con saldos, referencias, asientos y validaciones.

---

# 3. Modelo funcional esperado

## 3.1 Payment Entry

`PaymentEntry` debe representar cualquier movimiento bancario asociado a un tercero.

Debe soportar como mínimo:

| Campo                           | Requerimiento                                     |
| ------------------------------- | ------------------------------------------------- |
| `company`                       | Obligatorio                                       |
| `bank_account_id`               | Obligatorio                                       |
| `posting_date`                  | Obligatorio                                       |
| `party_type`                    | `supplier` o `customer`                           |
| `party_id`                      | Proveedor o cliente                               |
| `payment_type`                  | `pay` o `receive`                                 |
| `currency`                      | Moneda del pago                                   |
| `exchange_rate`                 | Obligatorio si moneda distinta a moneda funcional |
| `paid_amount`                   | Monto pagado/cobrado en moneda del pago           |
| `received_amount` / equivalente | Si existe separación contable                     |
| `reference_no`                  | Número de cheque, transferencia, recibo, etc.     |
| `reference_date`                | Fecha de referencia bancaria                      |
| `docstatus`                     | Borrador, aprobado, anulado                       |
| `document_no`                   | Secuencia/serie                                   |
| `remarks`                       | Observaciones                                     |

---

## 3.2 Payment Reference

Cada pago puede tener una o varias referencias.

Debe soportar:

| Campo                            | Requerimiento                                                                           |
| -------------------------------- | --------------------------------------------------------------------------------------- |
| `payment_entry_id`               | Pago padre                                                                              |
| `reference_type`                 | Tipo físico: `purchase_invoice`, `sales_invoice`, `purchase_order`, `sales_order`, etc. |
| `reference_id`                   | ID del documento origen                                                                 |
| `flow_source_type` / equivalente | Tipo lógico: `purchase_credit_note`, `sales_debit_note`, etc.                           |
| `total_amount`                   | Total del documento                                                                     |
| `outstanding_amount`             | Saldo abierto antes del pago                                                            |
| `allocated_amount`               | Monto aplicado en este pago                                                             |
| `exchange_rate`                  | Si aplica                                                                               |
| `gain_loss_amount`               | Diferencia cambiaria si aplica                                                          |

Importante: si el modelo físico de notas usa `PurchaseInvoice` / `SalesInvoice`, está bien que `reference_type` sea `purchase_invoice` o `sales_invoice`, pero la trazabilidad debe conservar el `document_type` real.

---

# 4. Casos de uso obligatorios

## 4.1 Pago de Factura de Compra

Desde una factura de compra aprobada:

```text
Factura de Compra → Crear Pago
```

El formulario debe prellenar:

* compañía;
* proveedor;
* moneda;
* saldo abierto;
* monto sugerido igual al saldo abierto;
* referencia a la factura;
* tipo de pago: `pay`;
* party type: `supplier`.

Al aprobar el pago:

* reduce saldo abierto de la factura;
* crea movimiento bancario de salida;
* crea asiento contable;
* crea `DocumentRelation`;
* la factura debe mostrar el pago en downstream;
* el pago debe mostrar la factura en upstream.

---

## 4.2 Cobro de Factura de Venta

Desde una factura de venta aprobada:

```text
Factura de Venta → Crear Cobro
```

Debe prellenar:

* compañía;
* cliente;
* moneda;
* saldo abierto;
* monto sugerido igual al saldo abierto;
* referencia a la factura;
* tipo de pago: `receive`;
* party type: `customer`.

Al aprobar el cobro:

* reduce saldo abierto de la factura;
* crea movimiento bancario de entrada;
* crea asiento contable;
* crea `DocumentRelation`.

---

## 4.3 Anticipo a Proveedor desde Orden de Compra

Desde orden de compra aprobada:

```text
Orden de Compra → Crear Pago / Anticipo
```

Debe comportarse como **anticipo**, no como pago aplicado a factura.

El formulario debe prellenar:

* compañía;
* proveedor;
* monto sugerido desde total de la orden, editable;
* tipo: `pay`;
* party type: `supplier`;
* referencia a orden de compra;
* línea sin factura asociada.

Al aprobar:

* crea salida bancaria;
* crea activo o cuenta puente de anticipo a proveedor;
* no reduce cuentas por pagar de factura porque todavía no hay factura;
* crea saldo de anticipo disponible para aplicar posteriormente;
* crea relación:

```text
purchase_order -> payment_entry
```

Debe quedar pendiente una función posterior:

```text
Factura de Compra → Aplicar Anticipo
```

---

## 4.4 Anticipo de Cliente desde Orden de Venta

Desde orden de venta aprobada:

```text
Orden de Venta → Crear Cobro / Anticipo
```

Debe comportarse como **anticipo de cliente**.

Al aprobar:

* crea entrada bancaria;
* crea pasivo o cuenta puente de anticipo de cliente;
* no reduce cuenta por cobrar porque todavía no hay factura;
* crea saldo de anticipo disponible para aplicar posteriormente;
* crea relación:

```text
sales_order -> payment_entry
```

Debe quedar pendiente:

```text
Factura de Venta → Aplicar Anticipo
```

---

## 4.5 Pago de Nota Débito de Compra

Desde nota débito de compra aprobada:

```text
Nota Débito Compra → Crear Pago
```

Debe comportarse como pago a proveedor.

Al aprobar:

* reduce saldo abierto de la nota débito;
* genera salida bancaria;
* debita cuenta por pagar / proveedor;
* acredita banco;
* crea relación:

```text
purchase_debit_note -> payment_entry
```

---

## 4.6 Reembolso desde Nota Crédito de Compra

Desde nota crédito de compra aprobada:

```text
Nota Crédito Compra → Crear Reembolso
```

Esto representa dinero que entra desde el proveedor.

Debe comportarse como:

```text
supplier + receive
```

Al aprobar:

* registra entrada bancaria;
* reduce saldo abierto a favor con proveedor;
* crea relación:

```text
purchase_credit_note -> payment_entry
```

Contablemente, debe revertir o compensar el saldo a favor del proveedor según el modelo de AP.

---

## 4.7 Cobro de Nota Débito de Venta

Desde nota débito de venta aprobada:

```text
Nota Débito Venta → Crear Cobro
```

Debe comportarse como cobro a cliente.

Al aprobar:

* reduce saldo abierto de la nota débito;
* genera entrada bancaria;
* crea relación:

```text
sales_debit_note -> payment_entry
```

---

## 4.8 Reembolso de Nota Crédito de Venta

Desde nota crédito de venta aprobada:

```text
Nota Crédito Venta → Crear Reembolso
```

Esto representa dinero que sale hacia el cliente.

Debe comportarse como:

```text
customer + pay
```

Al aprobar:

* registra salida bancaria;
* reduce saldo a favor del cliente;
* crea relación:

```text
sales_credit_note -> payment_entry
```

---

# 5. Validaciones obligatorias

## 5.1 Validaciones generales

No se debe permitir aprobar un pago si:

* no tiene compañía;
* no tiene cuenta bancaria;
* no tiene tercero;
* no tiene moneda;
* no tiene monto positivo;
* no tiene fecha;
* la cuenta bancaria no pertenece a la compañía;
* el documento origen no está aprobado;
* el documento origen está anulado;
* el documento origen no pertenece a la misma compañía;
* el tercero del pago no coincide con el tercero del documento origen;
* el monto aplicado excede saldo abierto, salvo tolerancia configurada.

---

## 5.2 Validaciones por tipo

### Facturas y notas

Debe validar:

```text
allocated_amount <= outstanding_amount
```

Debe permitir pagos parciales.

Debe permitir múltiples pagos contra una misma factura/nota.

Debe bloquear pago si saldo abierto es cero.

---

### Órdenes

Debe validar:

* orden aprobada;
* proveedor/cliente existente;
* monto del anticipo positivo;
* monto no necesariamente igual al total de la orden;
* anticipo no debe reducir AR/AP de factura;
* anticipo debe quedar disponible para aplicación futura.

---

### Reembolsos

Debe validar:

* que la nota crédito tenga saldo abierto;
* que el monto del reembolso no exceda el saldo a favor;
* que el `payment_type` sea correcto:

  * `purchase_credit_note`: `receive`;
  * `sales_credit_note`: `pay`.

---

# 6. Saldos abiertos

Debe existir una función central, no duplicada, para calcular saldo abierto.

Actualmente se usa algo como:

```python
compute_outstanding_amount(document)
```

Debe soportar correctamente:

| Documento           | Efecto esperado                          |
| ------------------- | ---------------------------------------- |
| Factura Compra      | saldo por pagar                          |
| Factura Venta       | saldo por cobrar                         |
| Nota Débito Compra  | saldo por pagar                          |
| Nota Débito Venta   | saldo por cobrar                         |
| Nota Crédito Compra | saldo a favor / reembolsable             |
| Nota Crédito Venta  | saldo a favor del cliente / reembolsable |

## Reglas

El saldo abierto debe calcularse como:

```text
total_documento - suma_aplicada_no_anulada
```

Pero el signo semántico depende del documento:

* facturas y notas débito: saldo a cobrar/pagar;
* notas crédito: saldo a aplicar o reembolsar.

No usar montos negativos como atajo si complica la contabilidad. Es preferible mantener `grand_total` positivo y resolver la semántica por `document_type`.

---

# 7. Contabilidad requerida

Al aprobar `PaymentEntry`, debe generarse asiento contable.

## 7.1 Pago a Proveedor

```text
Dr Cuentas por Pagar - Proveedor
Cr Banco
```

## 7.2 Cobro de Cliente

```text
Dr Banco
Cr Cuentas por Cobrar - Cliente
```

## 7.3 Anticipo a Proveedor

```text
Dr Anticipos a Proveedores
Cr Banco
```

## 7.4 Anticipo de Cliente

```text
Dr Banco
Cr Anticipos de Clientes
```

## 7.5 Reembolso recibido desde proveedor

```text
Dr Banco
Cr Saldo a favor / Cuentas por Pagar / Anticipo proveedor, según modelo contable
```

## 7.6 Reembolso pagado a cliente

```text
Dr Saldo a favor cliente / Cuentas por Cobrar / Anticipo cliente, según modelo contable
Cr Banco
```

## 7.7 Gasto bancario

Si el pago/cobro incluye comisión bancaria:

Pago a proveedor:

```text
Dr Cuentas por Pagar
Dr Gasto Bancario
Cr Banco
```

Cobro de cliente con comisión descontada:

```text
Dr Banco
Dr Gasto Bancario
Cr Cuentas por Cobrar
```

## 7.8 Diferencia cambiaria

Si moneda del documento y moneda del pago difieren, o si tasa de factura y tasa de pago difieren:

Debe generar línea a:

* ganancia cambiaria; o
* pérdida cambiaria.

Las cuentas deben venir de configuración global de la compañía.

---

# 8. Relación documental

Al aprobar un pago, debe crearse `DocumentRelation`.

## Para factura normal

```text
purchase_invoice -> payment_entry
sales_invoice -> payment_entry
```

## Para notas

Debe usarse el tipo lógico real:

```text
purchase_credit_note -> payment_entry
purchase_debit_note -> payment_entry
sales_credit_note -> payment_entry
sales_debit_note -> payment_entry
```

## Para anticipos

```text
purchase_order -> payment_entry
sales_order -> payment_entry
```

El patch ya avanza en esta dirección al usar `invoice.document_type` real al crear la relación desde referencias de pago. Esto debe mantenerse. 

---

# 9. UI requerida

## 9.1 Formulario de pago

El formulario debe mostrar claramente:

```text
Tipo: Pago / Cobro / Reembolso / Anticipo
Tercero: Proveedor / Cliente
Cuenta bancaria
Moneda
Monto
Documentos aplicados
Saldo abierto
Monto aplicado
Diferencia pendiente
```

## 9.2 Desde acción Crear

Cuando el usuario entra desde un documento origen, el formulario debe cargar contexto automáticamente.

Ejemplo:

```text
Factura Compra → Crear Pago
```

Debe verse algo como:

```text
Pago a Proveedor
Proveedor: ABC
Factura: FC-001
Saldo abierto: 1,000.00
Monto a pagar: 1,000.00
```

Ejemplo:

```text
Nota Crédito Venta → Crear Reembolso
```

Debe verse:

```text
Reembolso a Cliente
Cliente: XYZ
Nota Crédito: NCV-001
Saldo a favor: 250.00
Monto a reembolsar: 250.00
```

## 9.3 Líneas de referencia

Debe permitirse:

* editar monto aplicado;
* aplicar parcialmente;
* eliminar una línea;
* agregar varias facturas/notas del mismo tercero;
* bloquear mezcla de proveedores/clientes distintos;
* bloquear mezcla de compañías distintas;
* permitir mezcla de documentos compatibles del mismo tercero.

---

# 10. Estados

`PaymentEntry` debe soportar:

| Estado   | Significado                                           |
| -------- | ----------------------------------------------------- |
| Borrador | Editable, no afecta saldos ni contabilidad            |
| Aprobado | Genera asiento, afecta saldos, crea relaciones        |
| Anulado  | Revierte asiento, restaura saldos, conserva auditoría |

## Al anular

Debe:

* revertir asiento contable;
* restaurar saldo abierto de documentos referenciados;
* marcar relaciones como anuladas o crear relación de reversa;
* no borrar historial.

---

# 11. Pruebas obligatorias

## 11.1 Pruebas unitarias / funcionales

Crear pruebas para:

* factura compra → pago parcial;
* factura compra → pago total;
* factura venta → cobro parcial;
* factura venta → cobro total;
* nota débito compra → pago;
* nota crédito compra → reembolso recibido;
* nota débito venta → cobro;
* nota crédito venta → reembolso pagado;
* orden compra → anticipo proveedor;
* orden venta → anticipo cliente;
* bloqueo por documento en borrador;
* bloqueo por documento anulado;
* bloqueo por compañía distinta;
* bloqueo por tercero distinto;
* bloqueo por monto mayor al saldo abierto;
* anulación de pago restaura saldo;
* pago crea `DocumentRelation` correcta con tipo lógico;
* pago genera asiento contable correcto.

---

## 11.2 Pruebas de UI / web actions

Validar que:

* cada acción `Crear` abre el formulario de pago;
* el formulario prellena tercero, compañía y tipo correcto;
* `document_flow_trace` muestra la acción solo para documentos aprobados;
* después de aprobar, el pago aparece en downstream;
* desde el pago, el origen aparece en upstream.

---

# 12. Criterios de aceptación

La implementación se considera cerrada cuando:

* [ ] `payment_entry` soporta facturas, notas y órdenes como origen.
* [ ] Los pagos/cobros desde facturas reducen saldo abierto.
* [ ] Los pagos/cobros desde notas reducen saldo abierto de la nota.
* [ ] Los anticipos desde órdenes no afectan AR/AP de factura.
* [ ] Los anticipos quedan disponibles para aplicación futura.
* [ ] Los reembolsos tienen dirección correcta según tipo de nota.
* [ ] Se genera asiento contable correcto al aprobar.
* [ ] Se revierte asiento contable al anular.
* [ ] Se crea `DocumentRelation` con tipo lógico correcto.
* [ ] La UI no usa botones hardcodeados.
* [ ] `document_flow_trace` muestra acciones correctas según `document_type`.
* [ ] Existen pruebas para pago, cobro, anticipo y reembolso.
* [ ] No se permite pagar documentos en borrador/anulados.
* [ ] No se permite pagar más del saldo abierto sin configuración explícita.
