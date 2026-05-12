Implementation Requirement
Cacao Accounting — Series & Identifiers Framework
1. 🎯 Objetivo

Diseñar e implementar un subsistema de series e identificadores desacoplado, flexible y multi-contexto, capaz de:

Generar identificadores únicos y auditables
Soportar múltiples compañías
Manejar secuencias internas y externas
Adaptarse a requerimientos fiscales y operativos
Integrarse con todos los dominios transaccionales y maestros
2. 🧱 Clasificación de Entidades

El sistema debe distinguir explícitamente:

2.1 Master Data Global

Datos compartidos entre compañías:

party (clientes, proveedores)
item
catálogos globales

📌 Características:

No llevan prefijo de compañía
Serie global única
Independientes del contexto contable
2.2 Master Data por Compañía (Activation Layer)

Relación entre entidad global y compañía:

company_party
company_item

📌 Características:

Activa el uso dentro de una compañía
Puede tener atributos específicos (cuentas, condiciones, etc.)
Puede tener identificadores propios por compañía
2.3 Transacciones

Documentos operativos:

Facturas
Pagos
Movimientos de inventario
Asientos contables

📌 Características:

Siempre asociados a company_id
Siempre usan series por compañía
Impactan uno o más ledgers
3. 🔑 Reglas de Identificación
3.1 Requisito General

Toda entidad persistente debe tener un identificador generado por el sistema de series.

Incluye:

Master data
Configuración
Transacciones
3.2 Prefijo por Compañía (Obligatorio)

Para cualquier registro que impacte directa o indirectamente un ledger:

Debe incluir prefijo de compañía

Ejemplo:

CHOCO-JE-00001
CAFE-JE-00001
3.3 Fecha de Contabilización vs Fecha de Creación

Los tokens dinámicos deben resolverse usando:

posting_date (NO created_at)

Ejemplo:

Creado: 2026-05-01
Posting: 2026-04-30

Token:

*MMM* → APR (no MAY)
4. 🧩 Modelo de Series
4.1 Tabla: naming_series

Define el formato lógico:

id
name
entity_type (sales_invoice, payment_entry, etc.)
company_id (nullable para global)
prefix_template
(ej: CHOCO-SI-*YYYY*-*MMM*-)
is_active
4.2 Tabla: sequence

Define contadores físicos:

id
name
current_value
increment
padding
reset_policy:
never
yearly
monthly
4.3 Tabla: series_sequence_map

Permite flexibilidad N:M:

id
naming_series_id
sequence_id
priority
condition (JSON opcional)

📌 Esto permite:

Una serie → múltiples secuencias
Selección dinámica según contexto
4.4 Tabla: generated_identifier_log

Auditoría obligatoria:

id
entity_type
entity_id
full_identifier
sequence_id
generated_at
company_id
5. 🔣 Tokens Dinámicos

El sistema debe soportar:

*YYYY* → año (posting_date)
*YY*
*MMM* → mes (APR, MAY…)
*MM*
*DD*
*COMP* → código de compañía
*BRANCH* (futuro)
*POS* (punto de venta)

📌 Debe ser extensible (no hardcoded)

6. 🔄 Resolución de Identificadores

Proceso:

Seleccionar naming_series por:
entidad
compañía
Evaluar condiciones (si aplica)
Seleccionar sequence correspondiente
Resolver tokens con posting_date
Incrementar secuencia (transaccional)
Generar identificador final
7. 🏦 Casos Especiales
7.1 Pagos con múltiples secuencias externas

Ejemplo:

Serie: PAY-*YYYY*-
Secuencias:
Cheques Banco A
Cheques Banco B
Transferencias

📌 Selección basada en:

método de pago
banco
7.2 Ventas POS
Serie por punto de venta:
POS1-SI-
POS2-SI-
7.3 Facturación fiscal
Serie única por tipo fiscal
Secuencia externa (ej: autorizada por gobierno)
8. ⚙️ Inicialización Automática

Al crear una compañía:

El sistema debe:

Generar automáticamente:
Series por defecto para:
Journal Entry
Sales Invoice
Purchase Invoice
Payment Entry
Stock Entry
Crear secuencias asociadas
Asignar prefijo basado en:
código de compañía
9. 🔒 Reglas de Integridad
Identificadores deben ser únicos
Secuencias deben ser transaccionales (no duplicación)
No se permite reutilización
Auditoría obligatoria
10. 🚫 Anti-Patrones Prohibidos

❌ Un contador por tabla
❌ Series hardcodeadas
❌ Uso de created_at para tokens
❌ No soportar múltiples secuencias
❌ Identificadores sin trazabilidad

11. 🚀 Criterio de Éxito

El sistema será exitoso si:

Soporta múltiples compañías sin colisión
Permite integración con sistemas externos (bancos, fiscal)
Permite múltiples secuencias por serie
Garantiza consistencia temporal (posting_date)
No requiere rediseño para nuevos casos
