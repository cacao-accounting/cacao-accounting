# Conceptos fundamentales

El sistema separa las responsabilidades de cálculo en tres motores especializados coordinados por un Orquestador central.

## Los tres motores

### 1. Motor fiscal
Responsable de calcular todas las obligaciones relacionadas con impuestos.
- **Entradas**: Ítems, Reglas de impuestos.
- **Calcula**: IVA, ISC, DAI, impuestos municipales y retenciones.
- **Característica clave**: Soporta impuestos en cascada e impuestos incluidos en los precios.

### 2. Motor de costo de importación (Landed Cost)
Responsable de calcular el costo real capitalizable de los ítems.
- **Entradas**: Ítems, Resultados fiscales capitalizables, Cargos accesorios.
- **Calcula**: Costo unitario tras el prorrateo de flete, seguro y aranceles.
- **Métodos de prorrateo**: Por valor, cantidad, peso, volumen o distribución equitativa.

### 3. Motor de liquidación
Responsable de resolver la liquidación financiera de un documento.
- **Entradas**: Total del documento, Saldo abierto, Monto del pago, Reglas de retención.
- **Calcula**: Efectivo a pagar/recibir, retenciones al momento del pago y saldo restante.
- **Característica clave**: Maneja retenciones proporcionales para pagos parciales.

## Orquestador de eventos de negocio

El Orquestador conecta los motores con el flujo de negocio del sistema. Cuando un documento se confirma (p. ej., `purchase_invoice_confirmed`), el Orquestador:
1. Construye el `CalculationContext`.
2. Resuelve las Reglas aplicables.
3. Invoca los Motores en secuencia.
4. Genera un **Snapshot** auditable.
5. Pasa los resultados a los mappers de Contabilidad e Inventario.
