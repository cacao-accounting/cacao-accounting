# Cacao Accounting — Auditoría del Motor de Valuación de Inventarios (PEPS y Costo Promedio Móvil)

Este documento presenta una auditoría técnica y funcional profunda del motor de valuación de inventarios implementado en Cacao Accounting. El alcance cubre los algoritmos de acumulación y consumo de capas, el cálculo del costo real bajo los métodos **PEPS (Primero en Entrar, Primero en Salir / FIFO)** y **Costo Promedio Móvil**, el reporte de valoración y la gestión de casos especiales como stock negativo, ajustes de valor sin cantidad y transacciones retroactivas.

---

## 1. Introducción y Arquitectura de Datos

El motor de inventarios de Cacao Accounting opera bajo un enfoque contable y logístico integrado, asegurando que cada movimiento físico de entrada o salida tenga un reflejo exacto y balanceado en el Libro Mayor General (GL).

La arquitectura de persistencia se compone de tres entidades core:

1. **`StockLedgerEntry` (Kardex Físico)**: Registro histórico inmutable de cada transacción física (entradas, salidas, transferencias, ajustes, conteos).
2. **`StockValuationLayer` (Capas de Valuación)**: Registro detallado de deltas de cantidad (`qty`) y de valor (`stock_value_difference`). Sirve como fuente de verdad cronológica para reconstruir costos históricos y saldos al corte.
3. **`StockBin` (Snapshot Atómico)**: Almacena la existencia física actual (`actual_qty`) y el valor acumulado del inventario (`stock_value`) por cada combinación de `(company, item_code, warehouse)`. Cuenta con bloqueos pesimistas (`FOR UPDATE`) para serializar transacciones concurrentes.

---

## 2. Análisis del Algoritmo de Capas: `_valuation_queue`

El método central de reconstrucción y consolidación de capas es `_valuation_queue` (definido en `cacao_accounting/contabilidad/posting.py`). Este algoritmo procesa secuencialmente todas las capas históricas para generar una cola limpia de inventario disponible `[(qty, rate)]`.

### Flujo de Reconstrucción de la Cola:
1. **Ordenamiento Estricto**: Recupera las capas de `StockValuationLayer` ordenadas por `posting_date`, `created` y `id`. Esto asegura la integridad cronológica del historial de movimientos.
2. **Gestión de Saldos Negativos**:
   - El sistema realiza un seguimiento del déficit mediante la variable `negative_balance`.
   - Si una transacción de entrada positiva (`qty > 0`) se registra, primero compensa cualquier déficit acumulado (`negative_balance`). Solo la cantidad remanente se encola como capa disponible:
     $$\text{qty\_encolada} = \max(0, \text{layer.qty} - \text{negative\_balance})$$
3. **Consumo FIFO Interno**:
   - Cuando ocurre una salida (`qty < 0`), se consume de manera estrictamente cronológica desde el inicio de la cola acumulada utilizando `_consume_valuation_layer`.
   - Si la salida supera a las capas acumuladas, el excedente se suma a `negative_balance`.
4. **Distribución de Ajustes Financieros (`qty == 0`)**:
   - Durante la capitalización de costos indirectos (Landed Cost) o revaluaciones de inventario, se crean capas con cantidad cero (`qty == 0`) pero diferencia de valor (`stock_value_difference != 0`).
   - El algoritmo distribuye este valor uniformemente sobre todas las cantidades de las capas activas actualmente en la cola:
     $$\text{adjustment\_rate} = \frac{\text{layer.stock\_value\_difference}}{\text{total\_qty\_in\_queue}}$$
     $$\text{new\_rate} = \text{old\_rate} + \text{adjustment\_rate}$$
   - Esto incrementa el costo unitario de las capas existentes sin alterar el saldo físico.

---

## 3. Auditoría del Método PEPS (FIFO)

El método **PEPS (Primero en Entrar, Primero en Salir)** asume que los primeros artículos en entrar al inventario son los primeros en consumirse o venderse.

### Algoritmo de Consumo (`_fifo_valuation`):
Cuando se solicita una salida de $Q$ unidades, el sistema invoca `_fifo_valuation` pasándole la cola reconstruida por `_valuation_queue`:

1. **Iteración de Capas**: Recorre la lista de capas disponibles de izquierda a derecha (las más antiguas primero).
2. **Deducción de Cantidad**: Consume de cada capa el mínimo entre la cantidad disponible en la capa ($Q_{disp}$) y la cantidad remanente por consumir ($Q_{rem}$):
   $$q_{cons} = \min(Q_{disp}, Q_{rem})$$
3. **Acumulación de Costo**: Suma el costo de cada porción consumida:
   $$\text{total\_cost} = \sum (q_{cons} \times \text{rate})$$
4. **Tasa de Consumo Final**: Al finalizar, calcula la tasa promedio efectiva de la salida:
   $$\text{rate\_final} = \frac{\text{total\_cost}}{Q}$$

### Evaluación de PEPS:
- **Precisión Matemática**: El uso de `Decimal` de alta precisión evita cualquier error por redondeo de flotantes.
- **Control de Suficiencia**: Si la cola disponible se agota y aún queda cantidad por consumir ($Q_{rem} > 0$), lanza un error controlado `PostingError("No hay suficiente inventario para calcular el costo real.")`, protegiendo la cuenta contable de inventario de desbalances.
- **Flujo de Devoluciones**: Las devoluciones de ventas ingresan nuevamente al inventario como capas positivas con su costo respectivo, reestableciendo el orden correcto.

---

## 4. Auditoría del Método de Costo Promedio Móvil

El método de **Costo Promedio Móvil** recalcula el costo unitario del inventario de forma global con cada nueva entrada.

### Algoritmo de Consumo (`_moving_average_valuation`):
El cálculo del costo promedio móvil en Cacao Accounting cuenta con una optimización de "camino rápido" y un método de reconstrucción de seguridad:

1. **Camino Rápido (Basado en Bin)**:
   Si la cantidad física en el snapshot (`StockBin.actual_qty`) es mayor o igual a la cantidad requerida y mayor que cero, la tasa se calcula directamente sobre el snapshot en caché para maximizar el rendimiento:
   $$\text{average\_rate} = \frac{\text{StockBin.stock\_value}}{\text{StockBin.actual\_qty}}$$
   $$\text{total\_cost} = Q \times \text{average\_rate}$$
2. **Camino de Seguridad (Reconstrucción Completa)**:
   Si el bin no cuenta con stock suficiente o no existe, el sistema calcula la tasa ponderada de toda la cola acumulada dinámica:
   $$\text{total\_value} = \sum (\text{qty} \times \text{rate})$$
   $$\text{total\_available} = \sum \text{qty}$$
   $$\text{average\_rate} = \frac{\text{total\_value}}{\text{total\_available}}$$
   $$\text{total\_cost} = Q \times \text{average\_rate}$$

### Evaluación de Costo Promedio:
- **Resiliencia ante Descalces**: El camino de seguridad protege al sistema contra posibles desincronizaciones temporales del bin o inconsistencias de caché, reconstruyendo el promedio real de forma determinista basándose únicamente en el histórico de capas.
- **Invariante de Valor**: Garantiza que el valor de salida sea proporcional al costo promedio ponderado exacto en el momento del movimiento.

---

## 5. Gestión de Casos Especiales y Complejos

El motor de inventarios de Cacao Accounting demuestra una madurez excepcional en el manejo de casos límite de la contabilidad logística:

### A. Stock Negativo (`allow_negative_stock = True`)
Cuando un artículo tiene habilitada la configuración para permitir stock negativo, las salidas pueden realizarse aun cuando no existan capas físicas suficientes en la cola:
1. **Consumo de Capas Disponibles**: Primero, el sistema consume las capas que estén disponibles en ese momento.
2. **Uso de Tasa de Respaldo**: Para la porción excedente que cae en saldo negativo, el sistema obtiene el costo promedio de las capas consumibles disponibles mediante `_consume_available_layers_for_negative_stock`. Si la cola está completamente vacía, aplica una tasa de respaldo (fallback rate) basada en el costo histórico o costo estándar.
3. **Compensación de Entrada Posterior**: Cuando una compra o entrada posterior se contabiliza, la cola detecta el déficit mediante la variable `negative_balance` en `_valuation_queue`, neutralizando algebraicamente las cantidades antes de registrar nuevas capas positivas de costo. Esto previene que se infle artificialmente el saldo físico o el valor contable.

### B. Transacciones Retroactivas (Backdated Transactions)
En la práctica contable real, es común registrar movimientos con fechas pasadas. Cacao Accounting resuelve esto de forma elegante:
- El reporte de Kardex (`get_kardex`) y el Reporte de Existencias (`get_inventory_existence`) no confían en los snapshots del `StockBin` actual.
- En su lugar, **reconstruyen los saldos cronológicamente** recalculando la suma corrida de los deltas de las capas de valoración ordenadas hasta la fecha de corte solicitada.
- Esto asegura que las transacciones retroactivas participen correctamente en el saldo inicial y final del período auditado, resolviendo imprecisiones históricas.

### C. Revalorización sin Cantidad (Ajustes de Valor)
- Los ajustes de inventario que incrementan o disminuyen únicamente el valor contable (sin alterar las unidades físicas) se procesan aplicando el ajuste directamente sobre el costo unitario de las capas actualmente en inventario.
- Esto mantiene el balance perfecto entre el Mayor de Inventarios y el Subledger físico (Kardex).

---

## 6. Reporte de Valuación de Inventario (`get_inventory_valuation`)

La función `get_inventory_valuation` (en `cacao_accounting/reportes/services.py`) consolida la valoración del inventario para los estados financieros:
- **Diseño Libre de Contaminación Temporal**: Filtra los registros de `StockValuationLayer` aplicando la fecha de corte (`posting_date <= filters.date_to`).
- **Agrupación y Reconstrucción Dinámica**: Suma dinámicamente los campos `qty` y `stock_value_difference` por artículo y almacén.
- **Salida Limpia**: Excluye registros cuyo saldo final reconstruido sea exactamente cero y calcula los totales financieros en la moneda correspondiente.

---

## 7. Fortalezas, Riesgos y Recomendaciones

### Fortalezas del Motor Actual:
1. **Integridad de Datos Excepcional**: El uso de transacciones con bloqueo pesimista (`FOR UPDATE`) y el control del estado atómico de `StockBin` evitan condiciones de carrera concurrentes en entornos de alto volumen.
2. **Reconstrucción Determinista**: No se confía de manera exclusiva en datos calculados previamente (snapshots de saldo actual) para reportes históricos. La posibilidad de reconstruir de manera dinámica el Kardex por deltas de capas garantiza la precisión de los estados financieros.
3. **Manejo de Diferencias de Centavos**: La distribución de ajustes y varianzas mediante divisiones exactas en tipo `Decimal` previene pérdidas o ganancias huérfanas por redondeo aritmético.

### Riesgos y Recomendaciones de Mejora:
1. **Rendimiento de Consultas en Reconstrucción**:
   - *Riesgo*: A medida que el volumen transaccional de un artículo en una bodega crezca a miles de filas, la reconstrucción dinámica de la cola mediante `_valuation_queue` (que ejecuta un `SELECT` sobre todas las capas históricas) podría impactar el rendimiento en el submit de documentos.
   - *Recomendación*: Implementar un mecanismo de consolidación o "cierre de capas" periódico (por ejemplo, al cierre mensual), donde las capas completamente consumidas sean marcadas o archivadas, reduciendo el número de filas a procesar activamente a solo aquellas capas con cantidad remanente mayor a cero.
2. **Validación de Unidades de Medida (UOM)**:
   - *Riesgo*: El motor asume que todas las cantidades registradas en las capas de valoración están convertidas a la Unidad de Medida Base (UOM Base).
   - *Recomendación*: Fortalecer la validación en los formularios y el Posting Engine para rechazar cualquier registro que no cuente con una tasa de conversión de UOM válida respecto a la UOM Base del catálogo de artículos.

---

## Conclusión

El motor de valuación de inventario de Cacao Accounting por los métodos PEPS (FIFO) y Costo Promedio Móvil es altamente **sólido, preciso y cumple con los estándares internacionales de contabilidad (NIIF / IAS 2)**. Su diseño basado en la inmutabilidad de movimientos y la reconstrucción dinámica basada en deltas de capas asegura la consistencia e integridad absoluta de los estados financieros.
