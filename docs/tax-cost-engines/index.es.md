# Motores de cálculo de impuestos y costos

Bienvenido a la documentación de los motores de Impuestos, Costo de Importación (Landed Cost) y Liquidación de Cacao Accounting.

Este módulo proporciona una arquitectura centralizada, determinista y auditable para gestionar todos los cálculos financieros asociados a las transacciones de negocio.

## Mapa de la documentación

- **[Conceptos fundamentales](concepts.md)**: Introducción a la arquitectura de tres motores.
- **[Motor fiscal](fiscal-engine.md)**: Detalles sobre los cálculos de impuestos y retenciones.
- **[Motor de costo de importación](landed-cost-engine.md)**: Valoración de inventario y prorrateo de costos.
- **[Motor de liquidación](settlement-engine.md)**: Liquidaciones financieras y pagos.
- **[Prioridad y resolución de reglas](rule-priority.md)**: Cómo el sistema decide qué reglas se aplican.
- **[Auditabilidad y snapshots](auditability.md)**: Cómo aseguramos que cada cálculo sea explicable.
- **[Estrategia de pruebas](testing.md)**: Cómo verificar los motores y las nuevas reglas.

## Ejemplos prácticos

- [Ejemplos de resolución de reglas de impuestos](rule-examples.md)
- [Ejemplo de ciclo de importación y compra](import-purchase-example.md)
- [Ejemplo de cálculo de ventas e impuestos](sales-example.md)
- [Ejemplo de pagos y retenciones](payment-withholding-example.md)

## Principios de diseño

1. **Determinista**: Dada la misma entrada (contexto), la salida es siempre la misma.
2. **Funciones puras**: Los motores no acceden a la base de datos ni modifican el estado directamente.
3. **Auditabilidad**: Cada paso del cálculo queda registrado en una pista de auditoría.
4. **Explicabilidad**: El sistema puede explicar exactamente cómo llegó a un resultado.
5. **Configurabilidad**: Ningún impuesto está codificado de forma fija; todo el comportamiento se rige por reglas.
