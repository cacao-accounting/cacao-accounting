Follow the conventions defined in AGENTS.md (source of truth).

## Core Stack

* Python 3.12+, Flask backend, Alpine.js frontend

## Architecture (STRICT)

* Use Flask Blueprints by domain (auth, bancos, contabilidad, etc.)
* Enforce separation of concerns:

  * routes/controllers → HTTP only
  * services → business logic
  * repositories → database access
* Do NOT put business logic in routes
* Prefer dependency injection via parameters

## Coding Standards

* Always use type hints
* Prefer dataclasses, enums, and pattern matching where appropriate
* Use f-strings
* Follow PEP8 (favor clarity)
* Use descriptive names (no abbreviations)

## Design Rules

* Functions must do ONE thing and be small (~30 lines)
* Prefer early returns over nested logic
* Avoid deep nesting (>2 levels)
* Avoid side effects unless necessary

## Data & Typing

* Use dataclasses or TypedDict for structured data
* Do NOT expose ORM models directly in APIs
* Avoid `Any`, use explicit typing
* Define return types always

## Error Handling & Logging

* No bare except
* Catch specific exceptions
* Do not leak internal errors to API
* Use structured logging (no print)

## Flask & DB

* Use application factory pattern
* No global app
* Use SQLAlchemy ORM (queries only in repositories)
* Never access DB from routes

## Security

* Validate all inputs
* Enforce permissions (RBAC)
* Do not expose sensitive data

## Testing & Quality

* Use pytest
* Code must pass: black, mypy, ruff, flake8
* Write testable, decoupled code

## Performance

* Avoid N+1 queries
* Use pagination
* Cache when appropriate

## Output Expectations

When generating features:

1. Create/update route, service, repository
2. Maintain separation of concerns
3. Include type hints
4. Keep consistent naming

All user visible strings must be marked for translation (e.g., `_("Hello")`), and the code must be structured to support internationalization (i18n) from the start.

Support for Spanish (es) and English (en) must be implemented, with the ability to easily add more languages in the future.

If AGENTS.md is available, use it as extended context.
