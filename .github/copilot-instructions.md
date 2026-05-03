# Copilot Instructions – Flask Project

## Context
This is an accounting Python project using Flask as a microframework.
The goal is to maintain a clean, modular, and scalable architecture.
This project also includes repository-specific Copilot instructions in:
- `.github/instructions/global.instructions.md`
- `.github/instructions/accounting-python.instructions.md`
- `.github/instructions/transaction-forms-html.instructions.md`

Cacao Accounting — Data Architecture Contract
1. 📌 Introducción

Este documento define las decisiones de diseño fundamentales del proyecto Cacao Accounting a nivel de arquitectura de datos.

Su propósito es servir como contrato técnico para agentes de IA y desarrolladores, evitando reinterpretaciones, inconsistencias o rediseños innecesarios.

Este documento es la fuente de verdad sobre cómo debe pensarse el sistema, no solo cómo implementarlo.

2. 🎯 Objetivo del Proyecto

Cacao Accounting es un:

Motor contable moderno, modular y extensible, diseñado para cubrir el core financiero de una empresa sin convertirse en un ERP completo.

3. 📦 Scope del Proyecto
Incluido
Contabilidad general (GL)
Bancos
Compras
Ventas
Inventario
Multimoneda avanzada
Multi-libro contable
Series e identificadores robustos
Excluido (por ahora)
UI/UX
APIs
Lógica de negocio compleja
Reportería
Automatización de workflows

5. 🧱 Principios Arquitectónicos
5.1 Ledger-Centric
El General Ledger (gl_entry) es la única fuente de verdad
Todo flujo debe terminar en GL
5.2 Document-Oriented
Patrón obligatorio:
Header + Items
5.3 Multi-Company First
Todo dato transaccional tiene `company` y/o `entity` según el esquema actual
Aislamiento estricto por compañía
5.4 Multi-Ledger Nativo
Soporte para múltiples libros contables
Ejemplo:
Fiscal (NIO)
NIIF (USD)
5.5 Multi-Moneda Real
No se restringe moneda por:
cliente
proveedor
cuenta
5.6 Inmutabilidad
No borrado físico en datos contables
Uso de:
`docstatus`
`is_reversal` / `reversal_of`
5.7 Tipificación por Atributos
No crear tablas por tipo
Usar:
flags
enums
6. 🧠 Decisiones Críticas de Diseño
6.1 Multi-Ledger

✔ Un solo documento
✔ Múltiples gl_entry (uno por libro)
❌ NO duplicar Journal Entries

6.2 Multimoneda

✔ Cada transacción tiene:

moneda original
moneda base
tipo de cambio

✔ GL guarda ambas

6.3 Series e Identificadores

✔ Separación:

Serie lógica (naming_series)
Secuencia física (sequence)

✔ Tokens dinámicos:

basados en posting_date (NO created_at)

✔ Soporte:

múltiples secuencias por serie
6.4 Master Data vs Company Data

✔ party es global
✔ company_party activa uso por compañía

6.5 Inventario

Tipos:

Servicio → nunca inventario
Bien:
inventariable → stock ledger
no inventariable → gasto directo
6.6 UOM (Unidades de Medida)

✔ Conversión por ítem (NO global)

✔ Ledger siempre usa unidad base

6.7 Lotes y Series

✔ Opcionales por ítem
✔ Inmutables después de uso

6.8 GI/IR

✔ Cuenta intermedia obligatoria
✔ Recepción ≠ Facturación

6.9 Account Mapping

Orden de resolución:

Item
Party
Company
6.10 Reversión

✔ No eliminar
✔ Siempre reversar

7. 📊 Dominios del Sistema
Core
GL
Ledger
Company
Identidad
Party
Contact
Address
Operativo
Compras
Ventas
Inventario
Bancos
Soporte
Series
Tax
Pricing
Reconciliation
Transversal
Auditoría
Workflow 
Comentarios 

8. 🔗 Patrones Técnicos Obligatorios
8.1 Reference Pattern

Todas las relaciones genéricas usan:

reference_type
reference_id
8.2 Voucher Pattern
voucher_type
voucher_id
8.3 Multi-Dimensional GL
GL soporta dimensiones analíticas

9. ⚠️ Restricciones No Negociables
No duplicar lógica en múltiples tablas
No eliminar registros contables
No usar `created` o `created_at` para lógica financiera; usa `posting_date`
No acoplar módulos al GL directamente
No restringir moneda por entidad
No usar `company_id` cuando el esquema actual usa `company`/`entity`

10. 🧪 Casos que el sistema DEBE soportar
Pagos parciales
Facturas parciales
Multi-moneda por cliente
Múltiples libros contables
Inventario con lotes
Inventario con seriales
Diferencias de cambio
Conciliación bancaria

11. 🖥️ Modos de Ejecución
Desktop (Single User)
Todas las tablas existen
Funcionalidad multiusuario deshabilitada a nivel aplicación
Cloud (Multi User)
Comentarios
Workflow
Asignaciones
Archivos

12. 🚀 Objetivo Final

Construir:

Un framework contable extensible, capaz de soportar:

múltiples países
múltiples monedas
múltiples normativas contables
13. 🧭 Regla Operativa para Agentes IA

Antes de sugerir cambios:

¿Rompe GL como fuente única? → ❌ prohibido
¿Rompe multi-ledger? → ❌ prohibido
¿Rompe multimoneda real? → ❌ prohibido
¿Introduce duplicación? → ❌ prohibido
¿Viola inmutabilidad? → ❌ prohibido

Cacao Accounting — Data Architecture Contract
1. 📌 Introducción

Este documento define las decisiones de diseño fundamentales del proyecto Cacao Accounting a nivel de arquitectura de datos.

Su propósito es servir como contrato técnico para agentes de IA y desarrolladores, evitando reinterpretaciones, inconsistencias o rediseños innecesarios.

Este documento es la fuente de verdad sobre cómo debe pensarse el sistema, no solo cómo implementarlo.

2. 🎯 Objetivo del Proyecto

Cacao Accounting es un:

Motor contable moderno, modular y extensible, diseñado para cubrir el core financiero de una empresa sin convertirse en un ERP completo.

3. 📦 Scope del Proyecto
Incluido
Contabilidad general (GL)
Bancos
Compras
Ventas
Inventario
Multimoneda avanzada
Multi-libro contable
Series e identificadores robustos
Excluido (por ahora)
UI/UX
APIs
Lógica de negocio compleja
Reportería
Automatización de workflows
4. ⚙️ Alcance Actual

🚨 FASE ACTUAL: DISEÑO DE MODELO DE DATOS

Este proyecto se encuentra exclusivamente en:

Definición de esquema
Estructura relacional
Integridad de datos
Capacidad futura

NO se está implementando:

lógica de negocio
validaciones operativas
servicios
5. 🧱 Principios Arquitectónicos
5.1 Ledger-Centric
El General Ledger (gl_entry) es la única fuente de verdad
Todo flujo debe terminar en GL
5.2 Document-Oriented
Patrón obligatorio:
Header + Items
5.3 Multi-Company First
Todo dato transaccional tiene company_id
Aislamiento estricto por compañía
5.4 Multi-Ledger Nativo
Soporte para múltiples libros contables
Ejemplo:
Fiscal (NIO)
NIIF (USD)
5.5 Multi-Moneda Real
No se restringe moneda por:
cliente
proveedor
cuenta
5.6 Inmutabilidad
No deletes en datos contables
Uso de:
docstatus
reversals
5.7 Tipificación por Atributos
No crear tablas por tipo
Usar:
flags
enums
6. 🧠 Decisiones Críticas de Diseño
6.1 Multi-Ledger

✔ Un solo documento
✔ Múltiples gl_entry (uno por libro)
❌ NO duplicar Journal Entries

6.2 Multimoneda

✔ Cada transacción tiene:

moneda original
moneda base
tipo de cambio

✔ GL guarda ambas

6.3 Series e Identificadores

✔ Separación:

Serie lógica (naming_series)
Secuencia física (sequence)

✔ Tokens dinámicos:

basados en posting_date (NO created_at)

✔ Soporte:

múltiples secuencias por serie
6.4 Master Data vs Company Data

✔ party es global
✔ company_party activa uso por compañía

6.5 Inventario

Tipos:

Servicio → nunca inventario
Bien:
inventariable → stock ledger
no inventariable → gasto directo
6.6 UOM (Unidades de Medida)

✔ Conversión por ítem (NO global)

✔ Ledger siempre usa unidad base

6.7 Lotes y Series

✔ Opcionales por ítem
✔ Inmutables después de uso

6.8 GI/IR

✔ Cuenta intermedia obligatoria
✔ Recepción ≠ Facturación

6.9 Account Mapping

Orden de resolución:

Item
Party
Company
6.10 Reversión

✔ No eliminar
✔ Siempre reversar

7. 📊 Dominios del Sistema
Core
GL
Ledger
Company
Identidad
Party
Contact
Address
Operativo
Compras
Ventas
Inventario
Bancos
Soporte
Series
Tax
Pricing
Reconciliation
Transversal
Auditoría
Workflow (futuro)
Comentarios (futuro)
8. 🔗 Patrones Técnicos Obligatorios
8.1 Reference Pattern

Todas las relaciones genéricas usan:

reference_type
reference_id
8.2 Voucher Pattern
voucher_type
voucher_id
8.3 Multi-Dimensional GL
GL soporta dimensiones analíticas
9. ⚠️ Restricciones No Negociables
No duplicar lógica en múltiples tablas
No eliminar registros contables
No usar created_at para lógica financiera
No acoplar módulos al GL directamente
No restringir moneda por entidad
10. 🧪 Casos que el sistema DEBE soportar
Pagos parciales
Facturas parciales
Multi-moneda por cliente
Múltiples libros contables
Inventario con lotes
Inventario con seriales
Diferencias de cambio
Conciliación bancaria
11. 🖥️ Modos de Ejecución
Desktop (Single User)
Todas las tablas existen
Funcionalidad multiusuario deshabilitada a nivel aplicación
Cloud (Multi User)
Comentarios
Workflow
Asignaciones
Archivos
12. 🚀 Objetivo Final

Construir:

Un framework contable extensible, capaz de soportar:

múltiples países
múltiples monedas
múltiples normativas contables
13. 🧭 Regla Operativa para Agentes IA

Antes de sugerir cambios:

¿Rompe GL como fuente única? → ❌ prohibido
¿Rompe multi-ledger? → ❌ prohibido
¿Rompe multimoneda real? → ❌ prohibido
¿Introduce duplicación? → ❌ prohibido
¿Viola inmutabilidad? → ❌ prohibido

---

## Architecture Guidelines

- Use Flask Blueprints to organize modules by domain (e.g., auth, courses, users).
- Do NOT place business logic inside route handlers.
- Separate layers clearly:
  - routes/controllers → HTTP handling only
  - services → business logic
  - repositories → database access
- Prefer dependency injection via function parameters where possible.

## This a accounting project, so we will have modules like:

- auth (authentication and authorization)
- admin (admin dashboard and management)
- bancos (bank accounts and transactions)
- contabilidad (accounting logic and reports)
- inventario (inventory management)
- compras (purchase orders and suppliers)

Solo el core del negocio vive en el repositorio principal, funciones adicionales
podran agrergarse como plugins o modulos externos.

---

## Coding Standards

- Use Python 3.12+ features where appropriate:
  - prefer dataclasses for simple data structures
  - use pattern matching for complex conditionals
  - prefer f-strings for string formatting
  - use type hints for all functions and methods
  - prefer match-case over if-elif chains when checking multiple conditions
  - Use the walrus operator (:=) for inline assignments when it improves readability
  - use emuns for fixed sets of values (e.g., user roles, status codes)
- Always use type hints
- Follow PEP8 (but prefer clarity over strictness)
- Use descriptive variable and function names
- Avoid abbreviations

---

## Typing & Contracts

- Use explicit typing, avoid `Any` unless absolutely necessary
- Prefer `TypedDict` or dataclasses for structured data
- Use `Protocol` for defining interfaces (instead of inheritance when possible)
- Keep function signatures small and predictable
- Always define return types explicitly

---

## Data Modeling

- Prefer dataclasses for:
  - DTOs (data transfer objects)
  - service-layer inputs/outputs
- Do NOT use ORM models as API response objects directly
- Keep domain data separate from persistence models

---

## Control Flow & Readability

- Prefer early returns over nested conditionals
- Avoid deeply nested logic (>2 levels)
- Extract complex conditions into well-named variables or functions
- Use match-case only when it improves clarity (not by default)

---

## Functions & Design

- Functions should do ONE thing
- Keep functions under ~30 lines when possible
- Avoid side effects unless explicitly required
- Name functions using verbs (e.g., `create_user`, `validate_token`)

---

## Error Handling

- Do not use bare `except`
- Catch specific exceptions
- Raise domain-specific errors where appropriate
- Do not leak internal errors directly to API responses

---

## Logging

- Use structured logging
- Do not use print statements
- Include context (user_id, request_id, etc.) when relevant

---

## Constants & Enums

- Use enums instead of magic strings
- Group related constants in a single module
- Avoid hardcoded values in business logic

---

## Imports

- Avoid circular imports
- Group imports:
  - standard library
  - third-party
  - local modules
- Prefer absolute imports over relative imports

---

## Documentation

- Add docstrings for:
  - public functions
  - services
  - complex logic
- Keep docstrings concise and technical (no fluff)

---

## What to Avoid

- Overuse of clever Python tricks
- Implicit behavior that reduces readability
- Mixing multiple responsibilities in one function
- Hidden mutations of shared objects

## Flask Practices

- Always use application factory pattern
- Do not use global app instances
- Initialize extensions without binding, then attach in factory
- Use environment-based configuration (dev, testing, prod)
- Never hardcode secrets

---

## Database (SQLAlchemy)

- Use SQLAlchemy ORM (not raw SQL unless necessary)
- Keep queries inside repositories
- Do not query the database directly in routes
- Use transactions where needed
- Handle exceptions explicitly

---

## Validation & Serialization

- Use schemas (e.g., Marshmallow) for:
  - input validation
  - output serialization
- Never trust request data directly

---

## Authentication & Security

- Use JWT or session-based authentication (depending on context)
- Always validate permissions (RBAC)
- Sanitize and validate all inputs
- Avoid exposing sensitive fields in responses

---

## Error Handling

- Use centralized error handlers
- Return consistent JSON responses:

{
  "success": false,
  "message": "Error description",
  "data": null
}

---

## Testing

- Write testable code (avoid tight coupling)
- Prefer unit tests for services
- Mock external dependencies
- Format code with black and check with flake8, ruff, and mypy
- Use pytest for testing and coverage
- All test must pass before merging

---

## Performance & Scalability

- Avoid unnecessary DB queries (N+1 problems)
- Use pagination for lists
- Cache when appropriate (Flask-Caching)

---

## What to Avoid

- Fat controllers (routes with business logic)
- Direct DB access in routes
- God services (huge classes/functions)
- Circular imports
- Hidden side effects

---

## Preferred Style

When generating code:

- Be explicit rather than implicit
- Favor readability over cleverness
- Keep functions small and focused
- Add docstrings for non-trivial logic

---

## Output Expectations

When generating new features:

1. Create/update:
   - route
   - service
   - repository (if needed)
2. Keep separation of concerns
3. Include type hints
4. Use consistent naming
