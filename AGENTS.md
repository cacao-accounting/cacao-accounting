# Instrucciones 

## Contexto
La aplicación esta desarrollada en Python y utiiza como versión minima python3.12
El backend es Flask el frontend usa alpine.js

Las siguientes instrucciones son relevantes para el diseño de interfaces:
- `.github/instructions/global.instructions.md`
- `.github/instructions/accounting-python.instructions.md`
- `.github/instructions/transaction-forms-html.instructions.md`


Incluye siempre dentro del contexto de cada sesión los siguientes archivos:
- `modulos/contexto/accounitng_dimensions.md`
- `modulos/contexto/advanced_accounting.md`
- `modulos/contexto/checklist.md`
- `modulos/contexto/contacs_and_address.md`
- `modulos/contexto/registros_overview.md`
- `modulos/contexto/uoms.md`
- `modulos/contexto/accouting_estructure.md`
- `modulos/contexto/aging.md`
- `modulos/contexto/collab.md`
- `modulos/contexto/desgin_principes.md`
- `modulos/contexto/series.md`

Debes considerar todos esos archivos para tener el contexto completo para sesiones.

Siempre considera los siguientes controles de calidad:

- Formato con black
- Chequeo de tipos con mypy
- Chequeo estatico con ruff y flake8
- Pruebas unitarias con pytest

Los tests unitarios se ejecutan con este comando:

CACAO_TEST=True LOGURU_LEVEL=WARNING SECRET_KEY=ASD123kljaAddS python -m pytest  -v -s --exitfirst --slow=True

Crear un archivo SESSIONS.md este archivo debe servir como una bitacora de desarrollo, incluye en orden cronologico
un resumen de la petición del usuario y un resumen de el plan implementado, analiza el contenido del archivo SESSIONS.md
como una fuente de contexto y de las desiciones de diseño que se han tomado y para dar continuidad a desarrollo por etapas para
no tener que planear todo desde cero y tener un continuidad en el desarrollo con un contexto completo de la evolucion del proyecto.

Actualiza siempre los archivos ESTADO_ACTUAL.md y PENDIENTE.md con el resultado de las iteraciones para tener siempre a
vista el estado del proyecto.

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

- Never trust request data directly

---

## Authentication & Security

- Use JWT or session-based authentication (depending on context)
- Always validate permissions (RBAC)
- Sanitize and validate all inputs
- Avoid exposing sensitive fields in responses

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

---

### i18n y l10n

All user visible strings must be marked for translation (e.g., `_("Hello")`), and the code must be structured to support internationalization (i18n) from the start.

Support for Spanish (es) and English (en) must be implemented, with the ability to easily add more languages in the future.