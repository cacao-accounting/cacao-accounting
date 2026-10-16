# Auditabilidad y snapshots

Cada cálculo realizado por los motores es auditable y reproducible.

## Snapshots

Cuando un documento se **confirma**, el sistema guarda un Snapshot JSON de todo el contexto de cálculo y sus resultados.

### Propósito de los snapshots

1. **Reproducibilidad histórica**: Si las reglas de impuestos cambian en el futuro, el documento conserva su cálculo original.
2. **Reversión (notas de crédito)**: Cuando se emite una nota de crédito contra una factura pasada, el sistema usa el Snapshot para asegurar que los montos de reversión coincidan exactamente con los originales.
