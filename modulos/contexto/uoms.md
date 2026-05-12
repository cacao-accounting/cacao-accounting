Implementation Requirement
Cacao Accounting — Items, Units of Measure & Inventory Control Framework
1. 🎯 Objetivo

Diseñar un modelo de datos robusto y extensible para la gestión de ítems, unidades de medida e inventario, que:

Diferencie correctamente bienes vs servicios
Controle inventario solo cuando corresponda
Soporte conversiones de unidades por ítem
Permita trazabilidad por lote y número de serie
Garantice consistencia en los ledgers
2. 🧱 Clasificación de Ítems
2.1 Tipos de Ítem

Campo obligatorio:

item.type
goods
service
2.2 Comportamiento Contable

Campo obligatorio:

item.is_stock_item (boolean)
Tipo	Inventariable	Comportamiento
service	false	Gasto directo
goods	false	Gasto directo
goods	true	Afecta inventario

📌 Regla:

Un service nunca puede ser is_stock_item = true

3. 🔄 Flujo de Compras (Impacto Contable)
3.1 Orden de Compra
No impacta ledger
3.2 Recepción (Purchase Receipt / Stock Entry)
Caso 1: Servicio o bien NO inventariable
Impacto directo:
Débito → cuenta de gasto
Crédito → cuenta de recepción/acumulación
Caso 2: Bien inventariable
Impacto:
Débito → cuenta de inventario
Registro en stock_ledger_entry
4. ⚖️ Unidad de Medida (UOM)
4.1 Tabla: uom
id
name
is_active

📌 Reglas:

Puede eliminarse solo si nunca ha sido usada
Si fue usada → solo is_active = false
4.2 Unidad por defecto
item.default_uom_id (obligatorio)
4.3 Conversiones por Ítem
Tabla: item_uom_conversion
id
item_id
from_uom_id
to_uom_id (default)
conversion_factor

📌 Ejemplo:

Caja → Unidad = 12 (para item A)
Caja → Unidad = 14 (para item B)
5. 🔁 Reglas de Conversión
Las transacciones pueden usar cualquier UOM válida
Antes de persistir en ledger:

TODA cantidad debe convertirse a default_uom

6. 📊 Ledger de Inventario
Tabla: stock_ledger_entry

Campos mínimos:

item_id
warehouse_id
qty_change (en UOM base)
valuation_rate
voucher_type
voucher_id

📌 Regla crítica:

El ledger SIEMPRE usa la unidad base del ítem

7. 📦 Control por Lotes (Batch)
7.1 Configuración
item.has_batch (boolean)
7.2 Tabla: batch
id
item_id
batch_no
expiry_date (opcional)
7.3 Regla
Si has_batch = true:
TODA transacción debe especificar lote
8. 🔢 Control por Número de Serie
8.1 Configuración
item.has_serial_no (boolean)
8.2 Tabla: serial_number
id
item_id
serial_no
status
warehouse_id
8.3 Reglas
Cada unidad tiene un serial único
Cantidad = número de seriales
No se permiten duplicados
9. 🚫 Inmutabilidad de Configuración

Una vez que un ítem tiene transacciones:

NO se puede modificar:

default_uom
has_batch
has_serial_no
is_stock_item

📌 Esto debe validarse a nivel de integridad (no solo lógica futura)

10. 📈 Consistencia de Inventario
Regla obligatoria:

Stock total por ítem = SUM(stock por lote/serie)

Implicaciones:
No puede existir stock “huérfano”
Todo movimiento debe estar ligado a:
lote o
serie (si aplica)
11. 🔗 Relación con Transacciones

Tablas como:

purchase_receipt_item
delivery_note_item
stock_entry_item

Deben incluir:

item_id
uom_id
qty
qty_in_base_uom
batch_id (opcional)
serial_no (opcional)
12. ⚠️ Reglas de Validación Estructural
service → nunca en stock ledger
is_stock_item = false → nunca en stock ledger
has_batch = true → batch obligatorio
has_serial_no = true → serial obligatorio
conversion_factor > 0
qty siempre positiva (dirección en ledger)
13. 🧠 Extensibilidad

El diseño debe permitir:

UOM jerárquicas futuras
múltiples almacenes
valuación (FIFO / Moving Average)
control por ubicación (binning)
14. 🚀 Criterio de Éxito

El sistema será exitoso si:

Evita inconsistencias de inventario desde DB
Permite múltiples configuraciones por ítem
Soporta trazabilidad completa
No requiere rediseño para agregar lógica futura
