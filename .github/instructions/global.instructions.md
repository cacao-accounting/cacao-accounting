---
applyTo: "**/*.py"
---
# Global Coding Standards

- **Python 3.12+:** Use dataclasses, pattern matching, f-strings, and type hints.
- **Architecture:** Flask Blueprints. HTTP logic in routes; business logic in services; DB access in repositories.
- **Error Handling:** Specific exceptions only. No bare `except`. Raise domain errors.
- **Clean Code:** Functions < 30 lines. Early returns. Descriptive names (verbs for functions).
- **Typing:** Strict typing. Use `Protocol` for interfaces and `TypedDict` for structured data.
- **Flask:** Application factory pattern. No global app instances. Environment-based config.
- **SQLAlchemy:** Use ORM. No raw SQL. Handle transactions explicitly.
- **Quality:** Black, Ruff, Flake8, Mypy, and Pytest mandatory.
- **I18n:** Mark all user-visible strings for translation with `_()`.
