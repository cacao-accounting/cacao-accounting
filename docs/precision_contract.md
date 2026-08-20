# Contrato de Precisión Financiera

## Propósito

Este documento define el contrato de precisión y redondeo para todos los valores
monetarios y cuantitativos del sistema contable. Su objetivo es eliminar el
riesgo de pérdida de precisión por conversiones a `float` binario en
fronteras de presentación/API.

## Especificaciones de base de datos

Todas las columnas numéricas usan `Numeric(precision=20, scale=N)` en
SQLAlchemy, garantizando exactitud decimal en PostgreSQL y SQLite.

### Escala por tipo de valor

| Tipo de valor | Columnas representativas | Escala | Comentario |
|---|---|---|---|
| **Importes monetarios** | `grand_total`, `total`, `outstanding_amount`, `allocated_amount`, `rate` (líneas) | 4 | Monedas con hasta 4 decimales (ej. JPY 0 decimales, IQD 3) |
| **Cantidades** | `qty`, `qty_in_base_uom`, `received_qty`, `billed_qty`, `matched_qty` | 9 | Fracciones de unidad (ej. 1/3 kg) |
| **Tipos de cambio** | `exchange_rate`, `rate` (items), `conversion_factor` | 9 | Precisión para conversión entre monedas |
| **Tasas de impuestos** | `rate` (tax_line) | 9 | Porcentajes con alta precisión |

### Valores de referencia

| Valor | Escala requerida | Escala del sistema |
|---|---|---|
| `0.01` | 2 | 4 ✓ |
| `0.1` | 1 | 4 ✓ |
| `0.333333` | 6 | 9 ✓ (cant/tasa) / 4 ✓ (importe) |
| `1.005` | 3 | 4 ✓ |
| `999999999.99` | 2 | 4 ✓ |
| `0.0001` (mínimo monetary) | 4 | 4 ✓ |
| `36.123456789` (rate) | 9 | 9 ✓ |

## Reglas de conversión

### Python (backend)

1. **Nunca** convertir `Decimal` a `float` en cálculos financieros.
2. Las funciones de serialización (`_to_json_number`, `_number`) usan
   `str(Decimal(...))` para preservar precisión exacta en el límite HTTP.
3. La entrada de datos de formularios se convierte con
   `decimal_or_zero(value)` → `Decimal(str(value))`.
4. Los valores `NaN` e `Infinity` se rechazan o se normalizan a `Decimal("0")`.

### JavaScript (frontend)

1. **Nunca** usar `parseFloat` para valores financieros que se enviarán al
   servidor. Los cálculos de presentación pueden usar `Number`/`parseFloat`
   siempre que el valor enviado al backend sea una cadena decimal limpia.
2. La función `toCurrencyString(value)` formatea un número a cadena decimal
   usando `toFixed(9)` (escala máxima del sistema) y elimina ceros finales,
   evitando representaciones IEEE 754 como `0.020000000000000004`.
3. Los valores enviados al servidor (form POST, JSON payload) deben ser
   cadenas: `"300"`, `"300.0000"`, `"1.005"`, etc.
4. El backend usa `Decimal(str(value))` que convierte correctamente tanto
   enteros como decimales, preservando la precisión exacta.

## Puntos de redondeo autorizados

El redondeo a decimales de visualización (2 decimales para importes) es
**exclusivo de la capa de presentación** (CSS `toLocaleString`). Nunca
afecta el valor persistido o transmitido.

## Diferencias de redondeo

Cuando el sistema debe redondear (ej. al facturar con monedas de bajo
decimales), la diferencia se contabiliza explícitamente como ajuste de
redondeo en lugar de ser descartada.

## Referencias

- Issue [#284](https://github.com/cacao-accounting/cacao-accounting/issues/284)
- Commit `b227fec5` — `fix(precision): preserve exact decimal API values`
- Commit `9095b82a` — `fix(precision): preserve payment decimal payloads`
- Commit `ac10597d` — `fix(printing): retain decimal values in contexts`
- Commit `295acf71` — `fix(fx): validate historical revaluation rates`
- Commit `3e5814ec` — `fix(printing): preserve decimal values during rendering`
