Implementation Requirement
Cacao Accounting — Advanced Financial Capabilities (SAP-Grade Features)
1. 🎯 Objetivo

Extender el modelo de datos para soportar:

Proceso GI/IR (Goods Receipt / Invoice Receipt)
Revalorización en moneda extranjera
Cockpit de cierre mensual
Multimoneda avanzada (multi-currency per entity)
Múltiples libros contables (Multi-Ledger Accounting)
2. 📦 GI / IR (Goods Receipt / Invoice Receipt)
2.1 Objetivo

Permitir desacoplar:

Recepción de inventario
Registro de factura

Y reconciliarlos posteriormente.

2.2 Modelo
gr_ir_account (por compañía)
id
company_id
account_id
Flujo estructural
Recepción de almacén:
Débito → Inventario
Crédito → GR/IR
Factura de proveedor:
Débito → GR/IR
Crédito → Cuentas por pagar
2.3 Reglas
El saldo de GR/IR representa:
mercancía recibida no facturada
o facturada no recibida
Debe poder reconciliarse por:
item
documento
proveedor
2.4 Tabla opcional
gr_ir_reconciliation
id
purchase_receipt_id
purchase_invoice_id
matched_amount
3. 💱 Revalorización en Moneda Extranjera
3.1 Objetivo

Recalcular saldos en moneda base para:

Bancos
Cuentas por cobrar (AR)
Cuentas por pagar (AP)
3.2 Modelo
exchange_revaluation
id
company_id
posting_date
target_account_id
currency
exchange_revaluation_item
id
revaluation_id
reference_type
reference_id
old_rate
new_rate
difference_amount
3.3 Reglas
Genera automáticamente:
Journal Entry de ajuste
No modifica transacciones originales
Puede revertirse
4. 🧾 Cockpit de Cierre Mensual
4.1 Objetivo

Controlar y auditar el cierre contable.

4.2 Modelo
period_close_run
id
company_id
period_id
status (open, in_progress, closed)
period_close_check
id
close_run_id
check_type
status
message
4.3 Checks sugeridos
GL balanceado
GR/IR limpio
AR/AP conciliado
Inventario consistente
4.4 Regla

No se puede cerrar un período si existen inconsistencias

5. 💲 Multimoneda Avanzada
5.1 Principio

NO restringir moneda por:

cliente
proveedor
cuenta
5.2 Modelo requerido
En TODAS las transacciones:
transaction_currency
base_currency
exchange_rate
En gl_entry:
debit / credit (base)
debit_currency / credit_currency (original)
5.3 Reglas
Un mismo cliente puede tener facturas en múltiples monedas
Un mismo proveedor igual
Una cuenta puede registrar múltiples monedas
5.4 Implicación

El saldo contable se calcula SIEMPRE en moneda base + análisis por moneda secundaria

6. 📚 Multi-Ledger Accounting
6.1 Objetivo

Soportar múltiples libros contables paralelos:

Ejemplo:

Fiscal (NIO)
NIIF (USD)
6.2 Modelo
ledger
id
name
company_id
currency
is_primary
6.3 Extensión crítica
gl_entry

Agregar:

ledger_id
6.4 Estrategia de implementación (decisión clave)
❗ OPCIÓN ADOPTADA (recomendada)

Un solo documento → múltiples líneas GL por libro

NO crear un JE separado por libro.

Justificación
Evita duplicación de documentos
Mantiene trazabilidad unificada
Permite consistencia cross-ledger
6.5 Regla de oro
Módulos operativos → impactan TODOS los libros
Módulo contable → puede seleccionar libros
6.6 Tabla opcional
ledger_mapping_rule
define diferencias entre libros
(ej: depreciación distinta)
7. 🔄 Generación Multi-Ledger

Para cada transacción:

Determinar libros activos
Generar gl_entry por cada libro
Aplicar moneda del libro
Aplicar reglas específicas
8. 📊 Reportes

Todos los reportes deben soportar:

ledger_id
company_id
moneda del libro
9. ⚠️ Reglas Críticas
9.1 Inmutabilidad
No cambiar libros después de transacciones
9.2 Consistencia
Cada transacción debe balancear en cada libro
9.3 Independencia
Libros pueden tener:
moneda distinta
reglas distintas
10. 🚀 Criterio de Éxito

El sistema será exitoso si:

Permite múltiples libros sin duplicar lógica
Soporta multimoneda real sin restricciones artificiales
Permite reconciliación GI/IR
Automatiza revalorizaciones
Permite cierre contable controlado
11. 🧭 Decisión Arquitectónica Clave

A diferencia de SAP:

❌ NO crear un Journal Entry por libro
✅ Usar un solo documento con múltiples gl_entry por ledger_id
