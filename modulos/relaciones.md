# Flujo Documental y Relaciones
Este módulo define la trazabilidad transversal entre documentos.

## Acciones de Creación (Make/Create)
- **Ventas:** SO → Delivery → Invoice → Payment → Credit Note.
- **Compras:** PO → Receipt → Invoice → Payment → Debit/Credit Note.
- **Inventario:** Receipt → Stock Entry; Delivery → Stock Entry.

Registros de los modulos de Compras, Ventas, Inventario y Bancos deben incluir in boton "Crear" que permita al usuario crear transacciones relacionadas
al registro actual siguiendo el flujo logico de operación, ejemplos:

Solicitud de Compra permite Crear Solicitud de Cotización.
Solicitud de Cotización permite crear presupuesto de Proveedor.
Multiples Presupuestos de Proveedor se pueden unir en un comparativo de ofertas.
Comparativo de Oferta, Oferta de Proveedor o Solicitud de Compra Permiten Crear Orden de Compra.
Orden de Compra permite Crear Recibo en Almacen, Factura, Nota de Debito, Nota de Credito o Devolucion
etc, etc, etc, etc,

## Patrón "Actualizar Elementos"
Mecanismo para tirar líneas de documentos fuente hacia destinos:
- Factura ← Orden / Entrega / Recepción.
- Pago ← Facturas (múltiples).
- Nota de Crédito ← Factura.

## Reglas de Oro
- Mantener `pending_qty = qty - processed_qty`.
- No duplicar líneas consumidas.
- Trazabilidad bidireccional vía `DocumentRelation`.

El usuario debe poder generar un nuevo registro, aplicar filtros y obtener lineas de otros registros preexistentes que cumplan con los filtros aplicados.

Correcto: lo actual cubre solo el **happy path mínimo**, pero la acción **Crear** desde un registro existente debería modelar las relaciones naturales entre documentos operativos, inventario, facturación, bancos y ajustes.

La idea correcta no es que todos los documentos creen todo, sino que cada documento pueda crear los **siguientes documentos válidos** según su estado, saldos pendientes y tipo de operación.

---

# Matriz completa propuesta: acción “Crear” desde registro existente

## 1. Source to Pay / Compras

Flujo base:

```text
Solicitud de Compra
→ Solicitud de Cotización
→ Cotización de Proveedor
→ Orden de Compra
→ Recibo / Recepción de Compra
→ Factura de Compra
→ Pago
```

Pero deben existir ramas para devoluciones, notas, cargos, descuentos y almacén.

---

## 1.1 Solicitud de Compra

| Registro origen     | Crear                                                  | Motivo                                                                                  |
| ------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------------- |
| Solicitud de Compra | Solicitud de Cotización                                | Pedir precios a proveedores antes de comprar                                            |
| Solicitud de Compra | Orden de Compra                                        | Compra directa sin proceso formal de cotización                                         |
| Solicitud de Compra | Requisición interna / Movimiento solicitado de almacén | Cuando la necesidad puede cubrirse con inventario existente, si el sistema soporta esto |

### Reglas sugeridas

* Solo permitir crear documentos si la solicitud está aprobada.
* Debe poder crear documentos parciales por líneas.
* Debe rastrear cantidad solicitada, cotizada, ordenada y pendiente.

---

## 1.2 Solicitud de Cotización

| Registro origen         | Crear                         | Motivo                                                 |
| ----------------------- | ----------------------------- | ------------------------------------------------------ |
| Solicitud de Cotización | Cotización de Proveedor       | Registrar respuesta de un proveedor                    |
| Solicitud de Cotización | Orden de Compra               | Crear OC desde la cotización seleccionada o adjudicada |
| Solicitud de Cotización | Nueva Solicitud de Cotización | Reenviar o ampliar proceso a otros proveedores         |

### Reglas sugeridas

* Puede generar varias cotizaciones de proveedor.
* Una RFQ puede adjudicarse total o parcialmente.
* La Orden de Compra debería generarse desde la cotización ganadora, no necesariamente desde la RFQ directamente, salvo compra directa.

---

## 1.3 Cotización de Proveedor

| Registro origen         | Crear                            | Motivo                                  |
| ----------------------- | -------------------------------- | --------------------------------------- |
| Cotización de Proveedor | Orden de Compra                  | Convertir cotización aceptada en orden  |
| Cotización de Proveedor | Solicitud de Cotización revisada | Si se requiere renegociar               |
| Cotización de Proveedor | Comparativo de Cotizaciones      | Si existe proceso formal de comparación |

### Reglas sugeridas

* Solo cotizaciones aceptadas/adjudicadas deberían poder crear Orden de Compra.
* La OC debe heredar proveedor, moneda, precios, descuentos, impuestos, cargos y condiciones.

---

## 1.4 Orden de Compra

Actualmente existe:

```text
Orden de Compra → Recibo de Compra
Orden de Compra → Factura de Compra
```

Esto es correcto, pero incompleto.

| Registro origen | Crear                                   | Motivo                                                            |
| --------------- | --------------------------------------- | ----------------------------------------------------------------- |
| Orden de Compra | Recibo / Recepción de Compra            | Recibir mercancía en almacén                                      |
| Orden de Compra | Factura de Compra                       | Facturación directa contra OC, con o sin recepción previa         |
| Orden de Compra | Anticipo a Proveedor                    | Pago anticipado antes de recibir/facturar                         |
| Orden de Compra | Nota de Débito de Compra                | Cargo adicional del proveedor relacionado a la OC                 |
| Orden de Compra | Nota de Crédito de Compra               | Rebaja, bonificación o ajuste antes/después de facturar           |
| Orden de Compra | Cancelación / Cierre de saldo pendiente | Cerrar líneas no recibidas o no facturadas                        |
| Orden de Compra | Entrada de Almacén                      | Solo si se modela recepción directa como movimiento de inventario |

### Reglas sugeridas

* La OC debe controlar:

  * cantidad ordenada,
  * cantidad recibida,
  * cantidad facturada,
  * cantidad devuelta,
  * cantidad pendiente.
* Debe permitir recepción parcial.
* Debe permitir factura parcial.
* Debe permitir factura antes de recepción si la configuración lo permite.
* No debe permitir crear recibo si la OC está cerrada/cancelada.
* No debe permitir crear factura por encima del saldo pendiente salvo tolerancia configurada.

---

## 1.5 Recepción / Recibo de Compra

Actualmente existe:

```text
Recepción → Factura
Recepción → Devolución
Recepción → Entrada de Almacén
```

Esto es correcto, pero debe precisarse mejor.

| Registro origen     | Crear                              | Motivo                                                                     |
| ------------------- | ---------------------------------- | -------------------------------------------------------------------------- |
| Recepción de Compra | Factura de Compra                  | Facturar lo recibido                                                       |
| Recepción de Compra | Devolución de Compra               | Devolver mercancía al proveedor                                            |
| Recepción de Compra | Entrada de Almacén                 | Registrar movimiento físico si la recepción no lo hizo automáticamente     |
| Recepción de Compra | Reclamo a Proveedor                | Registrar diferencia, daño o faltante                                      |
| Recepción de Compra | Nota de Crédito de Compra          | Ajuste por devolución, daño, descuento posterior                           |
| Recepción de Compra | Nota de Débito de Compra           | Cargo adicional vinculado a recepción, por ejemplo flete o ajuste de costo |
| Recepción de Compra | Landed Cost / Costo de Importación | Agregar flete, seguro, aduana, DAI, ISC, transporte local, etc.            |

### Reglas sugeridas

* La devolución debe basarse en cantidades efectivamente recibidas.
* La factura debe basarse en cantidades recibidas no facturadas, salvo facturación contra OC.
* La entrada de almacén puede ser redundante si la recepción ya afecta inventario. Hay que decidir:

  * opción A: Recepción genera movimiento de almacén automáticamente;
  * opción B: Recepción es documento logístico y luego genera Entrada de Almacén.
* Si existe landed cost, debe poder afectar costo de inventario antes o después de factura, según diseño contable.

---

## 1.6 Devolución de Compra

Este documento falta en la matriz actual.

| Registro origen      | Crear                       | Motivo                                                 |
| -------------------- | --------------------------- | ------------------------------------------------------ |
| Devolución de Compra | Salida de Almacén           | Sacar físicamente inventario devuelto al proveedor     |
| Devolución de Compra | Nota de Crédito de Compra   | Reducir cuenta por pagar del proveedor                 |
| Devolución de Compra | Nota de Débito de Compra    | Si la devolución genera cargo al proveedor o penalidad |
| Devolución de Compra | Reemplazo / Nueva Recepción | Si el proveedor envía producto sustituto               |

### Reglas sugeridas

* Si la devolución ocurre antes de factura, reduce pendiente de facturar.
* Si ocurre después de factura, debe generar Nota de Crédito de Compra.
* Si afecta inventario, debe generar salida de almacén o reverso de entrada.
* Debe controlar cantidades devueltas por línea de recepción.

---

## 1.7 Factura de Compra

Actualmente existe:

```text
Factura de Compra → Pago
```

Esto es correcto, pero insuficiente.

| Registro origen   | Crear                                 | Motivo                                                                |
| ----------------- | ------------------------------------- | --------------------------------------------------------------------- |
| Factura de Compra | Pago                                  | Cancelar total o parcialmente la cuenta por pagar                     |
| Factura de Compra | Nota de Crédito de Compra             | Rebaja, devolución, descuento posterior, ajuste a favor de la empresa |
| Factura de Compra | Nota de Débito de Compra              | Cargo adicional del proveedor                                         |
| Factura de Compra | Retención                             | Si el sistema maneja retenciones fiscales                             |
| Factura de Compra | Anticipo aplicado                     | Aplicar anticipos existentes contra la factura                        |
| Factura de Compra | Gasto bancario / Diferencia cambiaria | Ajustes derivados del pago                                            |
| Factura de Compra | Reversión / Anulación                 | Si se requiere cancelar factura contabilizada                         |
| Factura de Compra | Asiento contable relacionado          | Ajuste contable manual controlado, si se permite                      |

### Reglas sugeridas

* Pago solo debe crearse por saldo abierto.
* Nota de crédito no debe exceder saldo o monto facturado, salvo configuración.
* Nota de débito aumenta cuenta por pagar.
* Si la factura está pagada, una nota de crédito puede:

  * dejar saldo a favor del proveedor,
  * generar reembolso,
  * aplicarse a otra factura.
* Para compras de inventario, la factura debe reconciliarse con recepción/OC.

---

## 1.8 Nota de Crédito de Compra

| Registro origen           | Crear                               | Motivo                                             |
| ------------------------- | ----------------------------------- | -------------------------------------------------- |
| Nota de Crédito de Compra | Aplicación a Factura de Compra      | Aplicar crédito contra factura abierta             |
| Nota de Crédito de Compra | Reembolso de Proveedor              | Si el proveedor devuelve dinero                    |
| Nota de Crédito de Compra | Pago negativo / Movimiento bancario | Si se registra entrada de efectivo desde proveedor |
| Nota de Crédito de Compra | Asiento contable                    | Ajuste controlado si aplica                        |

### Reglas sugeridas

* Reduce cuenta por pagar.
* Puede originarse desde factura, devolución, recepción o directamente.
* Debe poder quedar abierta como saldo a favor.
* Debe poder aplicarse parcial o totalmente.

---

## 1.9 Nota de Débito de Compra

| Registro origen          | Crear                          | Motivo                                                         |
| ------------------------ | ------------------------------ | -------------------------------------------------------------- |
| Nota de Débito de Compra | Pago                           | Cancelar el cargo adicional                                    |
| Nota de Débito de Compra | Aplicación a Factura de Compra | Aumentar saldo relacionado                                     |
| Nota de Débito de Compra | Entrada de costo / Landed Cost | Si representa flete, seguro, aduana u otro costo capitalizable |
| Nota de Débito de Compra | Asiento contable               | Ajuste controlado si aplica                                    |

### Reglas sugeridas

* Aumenta cuenta por pagar.
* Puede representar cargo financiero, diferencia de precio, flete, seguro, aduana, penalidad, etc.
* Si afecta inventario, debe pasar por lógica de costo adicional, no solo por AP.

---

## 1.10 Anticipo a Proveedor

Documento importante para Source to Pay.

| Registro origen      | Crear                          | Motivo                               |
| -------------------- | ------------------------------ | ------------------------------------ |
| Anticipo a Proveedor | Pago Bancario                  | Registrar salida de efectivo         |
| Anticipo a Proveedor | Aplicación a Factura de Compra | Cruzar anticipo contra factura       |
| Anticipo a Proveedor | Reembolso de Proveedor         | Si el proveedor devuelve el anticipo |
| Anticipo a Proveedor | Nota de Crédito / Ajuste       | Si se convierte en saldo a favor     |

### Reglas sugeridas

* El anticipo puede nacer desde OC o directamente desde proveedor.
* No debería afectar gasto o inventario hasta aplicarse, salvo política contable específica.
* Debe controlar saldo disponible por proveedor, moneda y compañía.

---

# 2. Order to Cash / Ventas

El flujo indicado tiene un pequeño problema de orden lógico:

```text
Solicitud de Venta -> Orden de Venta -> Cotización -> Nota de Entrega -> Factura -> Pago
```

Normalmente debería ser:

```text
Solicitud de Venta / Lead / Pedido preliminar
→ Cotización de Venta
→ Orden de Venta
→ Nota de Entrega / Despacho
→ Factura de Venta
→ Cobro / Pago recibido
```

La cotización usualmente ocurre antes de la orden de venta. Si en Cacao Accounting se quiere permitir cotización después de una solicitud, la matriz debe reflejar eso.

---

## 2.1 Solicitud de Venta

| Registro origen    | Crear                 | Motivo                                 |
| ------------------ | --------------------- | -------------------------------------- |
| Solicitud de Venta | Cotización de Venta   | Enviar propuesta comercial al cliente  |
| Solicitud de Venta | Orden de Venta        | Venta directa sin cotización formal    |
| Solicitud de Venta | Reserva de Inventario | Apartar stock antes de confirmar venta |

### Reglas sugeridas

* Solo solicitudes aprobadas o calificadas deberían crear cotización/orden.
* Puede requerir validación de cliente, moneda, lista de precios y disponibilidad.

---

## 2.2 Cotización de Venta

| Registro origen     | Crear                       | Motivo                                               |
| ------------------- | --------------------------- | ---------------------------------------------------- |
| Cotización de Venta | Orden de Venta              | Cliente acepta la cotización                         |
| Cotización de Venta | Nueva Cotización / Revisión | Reenviar propuesta modificada                        |
| Cotización de Venta | Factura Proforma            | Si se requiere documento previo no contable          |
| Cotización de Venta | Anticipo de Cliente         | Si el cliente debe pagar antes de confirmar/entregar |

### Reglas sugeridas

* Solo cotizaciones aceptadas deberían crear Orden de Venta.
* Debe preservar precios, descuentos, impuestos, cargos, moneda y condiciones comerciales.
* Debe permitir crear orden parcial.

---

## 2.3 Orden de Venta

Actualmente existe:

```text
Orden de Venta → Nota de Entrega
Orden de Venta → Factura de Venta
```

Esto es correcto, pero incompleto.

| Registro origen | Crear                                   | Motivo                                          |
| --------------- | --------------------------------------- | ----------------------------------------------- |
| Orden de Venta  | Nota de Entrega / Despacho              | Entregar mercancía desde almacén                |
| Orden de Venta  | Factura de Venta                        | Facturación directa, con o sin entrega previa   |
| Orden de Venta  | Reserva de Inventario                   | Apartar inventario                              |
| Orden de Venta  | Picking / Preparación                   | Preparar mercancía antes de entrega             |
| Orden de Venta  | Anticipo de Cliente                     | Cobro anticipado                                |
| Orden de Venta  | Nota de Crédito de Venta                | Descuento, bonificación o ajuste comercial      |
| Orden de Venta  | Nota de Débito de Venta                 | Cargo adicional al cliente                      |
| Orden de Venta  | Cancelación / Cierre de saldo pendiente | Cerrar cantidades no entregadas o no facturadas |

### Reglas sugeridas

* Debe controlar:

  * cantidad ordenada,
  * cantidad reservada,
  * cantidad entregada,
  * cantidad facturada,
  * cantidad devuelta,
  * cantidad pendiente.
* Debe permitir entrega parcial.
* Debe permitir factura parcial.
* Factura antes de entrega debe depender de configuración.
* No debe permitir despacho por encima del saldo pendiente, salvo tolerancia configurada.

---

## 2.4 Nota de Entrega / Despacho

Actualmente existe:

```text
Entrega → Factura de Venta
```

Faltan las ramas de devolución y almacén.

| Registro origen | Crear                              | Motivo                                                               |
| --------------- | ---------------------------------- | -------------------------------------------------------------------- |
| Nota de Entrega | Factura de Venta                   | Facturar mercancía entregada                                         |
| Nota de Entrega | Salida de Almacén                  | Registrar movimiento físico si la entrega no lo hizo automáticamente |
| Nota de Entrega | Nota de Crédito de Venta (devolución operativa) | Cliente devuelve mercancía sin doctype separado de devolución        |
| Nota de Entrega | Nota de Crédito de Venta           | Ajuste por devolución, daño, rebaja o diferencia                     |
| Nota de Entrega | Nota de Débito de Venta            | Cargo adicional posterior a la entrega                               |
| Nota de Entrega | Reentrega / Entrega complementaria | Corregir faltantes o completar despacho                              |

### Reglas sugeridas

* La factura debe tomar cantidades entregadas no facturadas.
* La devolución debe tomar cantidades entregadas no devueltas.
* Si la entrega ya genera salida de almacén, no debería requerir documento adicional de salida.
* Si la entrega es solo logística, debe generar salida de almacén.

---

## 2.5 Devolución de Venta

En la implementación actual, la devolución de venta se modela operativamente con **Nota de Crédito de Venta** (no existe un doctype separado `sales_return`).

| Registro origen     | Crear                     | Motivo                                     |
| ------------------- | ------------------------- | ------------------------------------------ |
| Devolución de Venta | Entrada de Almacén        | Reingresar inventario devuelto             |
| Devolución de Venta | Nota de Crédito de Venta  | Reducir cuenta por cobrar del cliente      |
| Devolución de Venta | Reemplazo / Nueva Entrega | Enviar producto sustituto                  |
| Devolución de Venta | Nota de Débito de Venta   | Cargo por penalidad, daño o diferencia     |
| Devolución de Venta | Reembolso al Cliente      | Si el cliente ya pagó y se devuelve dinero |

### Reglas sugeridas

* Si la devolución ocurre antes de factura, reduce pendiente de facturar.
* Si ocurre después de factura, debe generar Nota de Crédito de Venta.
* Debe controlar cantidades devueltas por línea de entrega/factura.
* Puede requerir inspección antes de reintegrar stock disponible.

---

## 2.6 Factura de Venta

Actualmente existe:

```text
Factura de Venta → Pago
```

Esto es correcto, pero incompleto.

| Registro origen  | Crear                        | Motivo                                                               |
| ---------------- | ---------------------------- | -------------------------------------------------------------------- |
| Factura de Venta | Cobro / Pago recibido        | Cancelar total o parcialmente cuenta por cobrar                      |
| Factura de Venta | Nota de Crédito de Venta     | Devolución, descuento posterior, rebaja o ajuste a favor del cliente |
| Factura de Venta | Nota de Débito de Venta      | Cargo adicional al cliente                                           |
| Factura de Venta | Recibo de Caja / Banco       | Si se distingue cobro de pago bancario                               |
| Factura de Venta | Aplicación de Anticipo       | Aplicar anticipo recibido del cliente                                |
| Factura de Venta | Reembolso al Cliente         | Si queda saldo a favor                                               |
| Factura de Venta | Reversión / Anulación        | Cancelar factura contabilizada                                       |
| Factura de Venta | Asiento contable relacionado | Ajuste controlado si aplica                                          |

### Reglas sugeridas

* Cobro solo debe crearse por saldo abierto.
* Nota de crédito reduce AR.
* Nota de débito aumenta AR.
* Si la factura ya está cobrada, una nota de crédito puede:

  * dejar saldo a favor del cliente,
  * aplicarse a otra factura,
  * generar reembolso bancario.
* Debe soportar pagos parciales, multimoneda, diferencias cambiarias y descuentos por pronto pago.

---

## 2.7 Nota de Crédito de Venta

| Registro origen          | Crear                               | Motivo                                   |
| ------------------------ | ----------------------------------- | ---------------------------------------- |
| Nota de Crédito de Venta | Aplicación a Factura de Venta       | Reducir saldo abierto                    |
| Nota de Crédito de Venta | Reembolso al Cliente                | Devolver dinero si ya había pago         |
| Nota de Crédito de Venta | Pago negativo / Movimiento bancario | Registrar salida de efectivo             |
| Nota de Crédito de Venta | Entrada de Almacén                  | Si corresponde a devolución de mercancía |
| Nota de Crédito de Venta | Asiento contable                    | Ajuste controlado si aplica              |

### Reglas sugeridas

* Reduce cuenta por cobrar.
* Puede originarse desde factura, entrega, devolución o directamente.
* Puede quedar abierta como saldo a favor del cliente.
* Puede aplicarse parcial o totalmente.

---

## 2.8 Nota de Débito de Venta

| Registro origen         | Crear                         | Motivo                      |
| ----------------------- | ----------------------------- | --------------------------- |
| Nota de Débito de Venta | Cobro / Pago recibido         | Cobrar cargo adicional      |
| Nota de Débito de Venta | Aplicación a Factura de Venta | Aumentar saldo relacionado  |
| Nota de Débito de Venta | Asiento contable              | Ajuste controlado si aplica |

### Reglas sugeridas

* Aumenta cuenta por cobrar.
* Puede representar intereses, penalidades, flete, diferencia de precio, cargo administrativo, etc.
* Debe tener impuestos configurables cuando aplique.

---

## 2.9 Anticipo de Cliente

| Registro origen     | Crear                         | Motivo                         |
| ------------------- | ----------------------------- | ------------------------------ |
| Anticipo de Cliente | Cobro Bancario                | Registrar entrada de efectivo  |
| Anticipo de Cliente | Aplicación a Factura de Venta | Cruzar anticipo contra factura |
| Anticipo de Cliente | Reembolso al Cliente          | Devolver anticipo              |
| Anticipo de Cliente | Nota de Crédito / Ajuste      | Convertir en saldo a favor     |

### Reglas sugeridas

* Puede nacer desde cotización, orden o directamente desde cliente.
* No debería reconocer ingreso hasta aplicarse a factura, salvo política contable específica.
* Debe controlar saldo disponible por cliente, moneda y compañía.

---

# 3. Inventario / Almacén como puente operativo

Inventario conecta compras y ventas con existencia física, costo y movimientos.

## 3.1 Entrada de Almacén

| Registro origen    | Crear                    | Motivo                                |
| ------------------ | ------------------------ | ------------------------------------- |
| Entrada de Almacén | Factura de Compra        | Facturar mercancía recibida           |
| Entrada de Almacén | Devolución de Compra     | Revertir entrada relacionada a compra |
| Entrada de Almacén | Ajuste de Inventario     | Corregir diferencia                   |
| Entrada de Almacén | Transferencia de Almacén | Mover stock a otro almacén            |
| Entrada de Almacén | Landed Cost              | Capitalizar costos adicionales        |

### Orígenes posibles para Entrada

| Crear Entrada de Almacén desde   | Motivo                              |
| -------------------------------- | ----------------------------------- |
| Recepción de Compra              | Ingreso por compra                  |
| Devolución de Venta              | Reingreso por devolución de cliente |
| Ajuste de Inventario             | Corrección positiva                 |
| Transferencia de Almacén         | Entrada en almacén destino          |
| Producción / Ensamble, si existe | Entrada de producto terminado       |

---

## 3.2 Salida de Almacén

| Registro origen   | Crear                    | Motivo                                  |
| ----------------- | ------------------------ | --------------------------------------- |
| Salida de Almacén | Factura de Venta         | Facturar despacho, si no existe entrega |
| Salida de Almacén | Devolución de Venta      | Reversar salida                         |
| Salida de Almacén | Ajuste de Inventario     | Corregir diferencia                     |
| Salida de Almacén | Transferencia de Almacén | Mover stock a otro almacén              |

### Orígenes posibles para Salida

| Crear Salida de Almacén desde | Motivo                   |
| ----------------------------- | ------------------------ |
| Nota de Entrega               | Despacho a cliente       |
| Devolución de Compra          | Salida hacia proveedor   |
| Ajuste de Inventario          | Corrección negativa      |
| Transferencia de Almacén      | Salida de almacén origen |
| Consumo interno, si existe    | Uso operativo            |

---

## 3.3 Transferencia de Almacén

| Registro origen          | Crear                | Motivo                           |
| ------------------------ | -------------------- | -------------------------------- |
| Transferencia de Almacén | Salida de Almacén    | Sacar del almacén origen         |
| Transferencia de Almacén | Entrada de Almacén   | Ingresar al almacén destino      |
| Transferencia de Almacén | Ajuste de Inventario | Corregir diferencias de traslado |

### Reglas sugeridas

* Puede ser un solo documento con dos movimientos automáticos:

  * salida en origen,
  * entrada en destino.
* Debe manejar tránsito si se quiere un flujo más robusto:

  * enviado,
  * en tránsito,
  * recibido.

---

## 3.4 Ajuste de Inventario

| Registro origen      | Crear              | Motivo                                       |
| -------------------- | ------------------ | -------------------------------------------- |
| Ajuste de Inventario | Entrada de Almacén | Ajuste positivo                              |
| Ajuste de Inventario | Salida de Almacén  | Ajuste negativo                              |
| Ajuste de Inventario | Asiento Contable   | Reconocer diferencia contra cuenta de ajuste |
| Ajuste de Inventario | Conteo Físico      | Si se maneja inventario físico formal        |

---

# 4. Bancos como puente financiero

Bancos conecta compras, ventas, anticipos, reembolsos, notas y movimientos de efectivo.

## 4.1 Pago a Proveedor

Actualmente existe:

```text
Factura de Compra → Pago
```

Debe ampliarse.

| Registro origen  | Crear                                 | Motivo                                         |
| ---------------- | ------------------------------------- | ---------------------------------------------- |
| Pago a Proveedor | Movimiento Bancario                   | Salida de dinero                               |
| Pago a Proveedor | Aplicación a Factura de Compra        | Cancelar factura                               |
| Pago a Proveedor | Aplicación a Nota de Débito de Compra | Cancelar cargo adicional                       |
| Pago a Proveedor | Anticipo a Proveedor                  | Registrar pago anticipado                      |
| Pago a Proveedor | Diferencia Cambiaria                  | Si moneda de factura y pago generan diferencia |
| Pago a Proveedor | Gasto Bancario                        | Comisión bancaria                              |
| Pago a Proveedor | Retención                             | Si aplica retención al pagar                   |
| Pago a Proveedor | Reversión / Anulación                 | Anular pago                                    |

### Crear pago desde

| Registro origen           | Crear                              |
| ------------------------- | ---------------------------------- |
| Factura de Compra         | Pago a Proveedor                   |
| Nota de Débito de Compra  | Pago a Proveedor                   |
| Orden de Compra           | Anticipo / Pago anticipado         |
| Proveedor                 | Pago no aplicado / Anticipo        |
| Nota de Crédito de Compra | Reembolso recibido, no pago normal |

---

## 4.2 Cobro de Cliente

Actualmente existe:

```text
Factura de Venta → Pago
```

Debe distinguirse conceptualmente como cobro, aunque el backend pueda usar un modelo común de payment.

| Registro origen  | Crear                                | Motivo                                          |
| ---------------- | ------------------------------------ | ----------------------------------------------- |
| Cobro de Cliente | Movimiento Bancario                  | Entrada de dinero                               |
| Cobro de Cliente | Aplicación a Factura de Venta        | Cancelar factura                                |
| Cobro de Cliente | Aplicación a Nota de Débito de Venta | Cancelar cargo adicional                        |
| Cobro de Cliente | Anticipo de Cliente                  | Registrar cobro anticipado                      |
| Cobro de Cliente | Diferencia Cambiaria                 | Si moneda de factura y cobro generan diferencia |
| Cobro de Cliente | Gasto Bancario                       | Comisión descontada por banco/tarjeta           |
| Cobro de Cliente | Descuento por pronto pago            | Ajuste comercial/financiero                     |
| Cobro de Cliente | Reversión / Anulación                | Anular cobro                                    |

### Crear cobro desde

| Registro origen          | Crear                                 |
| ------------------------ | ------------------------------------- |
| Factura de Venta         | Cobro de Cliente                      |
| Nota de Débito de Venta  | Cobro de Cliente                      |
| Orden de Venta           | Anticipo de Cliente                   |
| Cotización de Venta      | Anticipo de Cliente                   |
| Cliente                  | Cobro no aplicado / Anticipo          |
| Nota de Crédito de Venta | Reembolso al cliente, no cobro normal |

---

## 4.3 Nota de Débito Bancaria

| Registro origen         | Crear                 | Motivo                                      |
| ----------------------- | --------------------- | ------------------------------------------- |
| Nota de Débito Bancaria | Asiento Contable      | Registrar comisión, cargo o salida bancaria |
| Nota de Débito Bancaria | Gasto Bancario        | Clasificar cargo bancario                   |
| Nota de Débito Bancaria | Conciliación Bancaria | Asociar cargo con extracto                  |
| Nota de Débito Bancaria | Pago / Ajuste de Pago | Si corresponde a comisión de pago           |

### Uso típico

* Comisión bancaria.
* Cargos por transferencia.
* Impuestos bancarios.
* Ajustes negativos del banco.

---

## 4.4 Nota de Crédito Bancaria

| Registro origen          | Crear                   | Motivo                                           |
| ------------------------ | ----------------------- | ------------------------------------------------ |
| Nota de Crédito Bancaria | Asiento Contable        | Registrar ingreso bancario o reverso de cargo    |
| Nota de Crédito Bancaria | Conciliación Bancaria   | Asociar crédito con extracto                     |
| Nota de Crédito Bancaria | Cobro / Ajuste de Cobro | Si corresponde a ingreso relacionado con cliente |

### Uso típico

* Intereses bancarios.
* Reverso de comisión.
* Depósito no identificado.
* Ajuste positivo del banco.

---

## 4.5 Transferencia Bancaria

| Registro origen        | Crear                          | Motivo                                |
| ---------------------- | ------------------------------ | ------------------------------------- |
| Transferencia Bancaria | Movimiento Bancario de salida  | Salida desde cuenta origen            |
| Transferencia Bancaria | Movimiento Bancario de entrada | Entrada a cuenta destino              |
| Transferencia Bancaria | Diferencia Cambiaria           | Si las cuentas tienen distinta moneda |
| Transferencia Bancaria | Gasto Bancario                 | Comisión por transferencia            |
| Transferencia Bancaria | Conciliación Bancaria          | Conciliar ambos lados                 |

### Reglas sugeridas

* Si cuenta origen y destino tienen monedas distintas, el backend calcula conversión.
* Debe generar dos movimientos bancarios vinculados.
* Puede generar diferencia cambiaria si aplica.

---

# 5. Matriz resumida origen → Crear

Esta es la matriz más importante para implementar el dropdown **Crear**.

## Compras

| Desde                     | Crear                                                                                                                         |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| Solicitud de Compra       | Solicitud de Cotización, Orden de Compra                                                                                      |
| Solicitud de Cotización   | Cotización de Proveedor, Orden de Compra                                                                                      |
| Cotización de Proveedor   | Orden de Compra                                                                                                               |
| Orden de Compra           | Recepción de Compra, Factura de Compra, Anticipo a Proveedor, Nota de Débito de Compra, Nota de Crédito de Compra             |
| Recepción de Compra       | Factura de Compra, Devolución de Compra, Entrada de Almacén, Nota de Crédito de Compra, Nota de Débito de Compra, Landed Cost |
| Devolución de Compra      | Salida de Almacén, Nota de Crédito de Compra, Reemplazo / Nueva Recepción                                                     |
| Factura de Compra         | Pago a Proveedor, Nota de Crédito de Compra, Nota de Débito de Compra, Aplicar Anticipo, Reversión                            |
| Nota de Crédito de Compra | Aplicar a Factura, Reembolso de Proveedor, Movimiento Bancario                                                                |
| Nota de Débito de Compra  | Pago a Proveedor, Aplicar a Factura, Landed Cost                                                                              |
| Anticipo a Proveedor      | Pago Bancario, Aplicar a Factura, Reembolso                                                                                   |

---

## Ventas

| Desde                    | Crear                                                                                                                            |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| Solicitud de Venta       | Cotización de Venta, Orden de Venta                                                                                              |
| Cotización de Venta      | Orden de Venta, Factura Proforma, Anticipo de Cliente                                                                            |
| Orden de Venta           | Nota de Entrega, Factura de Venta, Reserva de Inventario, Anticipo de Cliente, Nota de Débito de Venta, Nota de Crédito de Venta |
| Nota de Entrega          | Factura de Venta, Salida de Almacén, Devolución de Venta, Nota de Crédito de Venta, Nota de Débito de Venta                      |
| Devolución de Venta      | Entrada de Almacén, Nota de Crédito de Venta, Reemplazo / Nueva Entrega, Reembolso al Cliente                                    |
| Factura de Venta         | Cobro de Cliente, Nota de Crédito de Venta, Nota de Débito de Venta, Aplicar Anticipo, Reversión                                 |
| Nota de Crédito de Venta | Aplicar a Factura, Reembolso al Cliente, Entrada de Almacén                                                                      |
| Nota de Débito de Venta  | Cobro de Cliente, Aplicar a Factura                                                                                              |
| Anticipo de Cliente      | Cobro Bancario, Aplicar a Factura, Reembolso                                                                                     |

---

## Inventario

| Desde                    | Crear                                                          |
| ------------------------ | -------------------------------------------------------------- |
| Entrada de Almacén       | Factura de Compra, Devolución de Compra, Transferencia, Ajuste |
| Salida de Almacén        | Factura de Venta, Devolución de Venta, Transferencia, Ajuste   |
| Transferencia de Almacén | Salida de Origen, Entrada de Destino, Ajuste                   |
| Ajuste de Inventario     | Entrada, Salida, Asiento Contable                              |
| Conteo Físico            | Ajuste de Inventario                                           |

---

## Bancos

| Desde                     | Crear                                                                           |
| ------------------------- | ------------------------------------------------------------------------------- |
| Factura de Compra         | Pago a Proveedor                                                                |
| Nota de Débito de Compra  | Pago a Proveedor                                                                |
| Nota de Crédito de Compra | Reembolso de Proveedor / Movimiento Bancario de entrada                         |
| Orden de Compra           | Anticipo a Proveedor                                                            |
| Factura de Venta          | Cobro de Cliente                                                                |
| Nota de Débito de Venta   | Cobro de Cliente                                                                |
| Nota de Crédito de Venta  | Reembolso al Cliente / Movimiento Bancario de salida                            |
| Orden de Venta            | Anticipo de Cliente                                                             |
| Pago a Proveedor          | Movimiento Bancario, Diferencia Cambiaria, Gasto Bancario, Reversión            |
| Cobro de Cliente          | Movimiento Bancario, Diferencia Cambiaria, Gasto Bancario, Descuento, Reversión |
| Transferencia Bancaria    | Movimiento salida, Movimiento entrada, Diferencia Cambiaria, Gasto Bancario     |
| Nota de Débito Bancaria   | Asiento Contable, Gasto Bancario                                                |
| Nota de Crédito Bancaria  | Asiento Contable, Ingreso Bancario                                              |

### Estado de implementación (2026-05-21)

Pares ya implementados en `document_flow` y expuestos con prefill en Bancos:

* `purchase_credit_note -> payment_entry` (reembolso recibido de proveedor).
* `purchase_debit_note -> payment_entry` (pago de cargo adicional).
* `sales_credit_note -> payment_entry` (reembolso al cliente).
* `sales_debit_note -> payment_entry` (cobro de cargo adicional).

---

# 6. Brecha contra implementación actual

Según lo que compartiste, hoy existe esto:

## Compras actual

| Origen            | Crear actual                            | Estado                    |
| ----------------- | --------------------------------------- | ------------------------- |
| Orden de Compra   | Recibo de Compra, Factura de Compra     | Correcto, pero incompleto |
| Recepción         | Factura, Devolución, Entrada de Almacén | Bien encaminado           |
| Factura de Compra | Pago                                    | Correcto, pero incompleto |

### Faltantes principales en compras

Faltan relaciones para:

* Solicitud de Compra.
* Solicitud de Cotización.
* Cotización de Proveedor.
* Anticipo a Proveedor.
* Nota de Crédito de Compra.
* Nota de Débito de Compra.
* Devolución de Compra hacia Nota de Crédito.
* Devolución de Compra hacia Salida de Almacén.
* Factura de Compra hacia Nota de Crédito.
* Factura de Compra hacia Nota de Débito.
* Factura de Compra hacia Aplicar Anticipo.
* Orden de Compra hacia Anticipo.
* Orden de Compra hacia Nota de Débito / Nota de Crédito.
* Recepción hacia Landed Cost.

---

## Ventas actual

| Origen           | Crear actual                      | Estado                    |
| ---------------- | --------------------------------- | ------------------------- |
| Orden de Venta   | Nota de Entrega, Factura de Venta | Correcto, pero incompleto |
| Entrega          | Factura de Venta                  | Correcto, pero incompleto |
| Factura de Venta | Pago                              | Correcto, pero incompleto |

### Faltantes principales en ventas

Faltan relaciones para:

* Solicitud de Venta.
* Cotización de Venta.
* Anticipo de Cliente.
* Devolución de Venta.
* Orden de Venta hacia Anticipo.
* Orden de Venta hacia Nota de Crédito / Nota de Débito.
* Entrega hacia Devolución.
* Entrega hacia Salida de Almacén.
* Entrega hacia Nota de Crédito / Nota de Débito.
* Factura de Venta hacia Nota de Crédito.
* Factura de Venta hacia Nota de Débito.
* Factura de Venta hacia Aplicar Anticipo.
* Nota de Crédito de Venta hacia Reembolso.
* Nota de Débito de Venta hacia Cobro.

---

## Bancos actual

| Origen            | Crear actual | Estado   |
| ----------------- | ------------ | -------- |
| Factura de Compra | Pago         | Correcto |
| Factura de Venta  | Pago         | Correcto |

### Faltantes principales en bancos

* Pago desde Nota de Débito de Compra.
* Cobro desde Nota de Débito de Venta.
* Reembolso desde Nota de Crédito de Compra.
* Reembolso a cliente desde Nota de Crédito de Venta.
* Anticipo a proveedor desde Orden de Compra.
* Anticipo de cliente desde Orden de Venta o Cotización.
* Movimiento bancario desde pago/cobro.
* Diferencia cambiaria.
* Gasto bancario.
* Transferencia bancaria multimoneda.
* Nota de débito bancaria.
* Nota de crédito bancaria.
