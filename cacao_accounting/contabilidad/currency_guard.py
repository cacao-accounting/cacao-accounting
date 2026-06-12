"""Validaciones reutilizables para el uso operativo de monedas."""

from __future__ import annotations

from dataclasses import dataclass

from cacao_accounting.database import Book, Currency, Entity, database


class CurrencyGuardError(ValueError):
    """Error de negocio al validar una moneda."""


@dataclass(frozen=True)
class CurrencyGuard:
    """Centraliza reglas de activacion y uso de monedas."""

    def get_currency(self, code: str | None) -> Currency:
        """Devuelve una moneda existente o falla con mensaje de negocio."""
        if not code:
            raise CurrencyGuardError("La moneda es obligatoria.")
        currency = database.session.execute(database.select(Currency).filter_by(code=code)).scalar_one_or_none()
        if currency is None:
            raise CurrencyGuardError("La moneda indicada no existe.")
        return currency

    def validate_active_currency(self, code: str | None, message: str | None = None) -> Currency:
        """Valida que una moneda exista y este activa."""
        currency = self.get_currency(code)
        if not bool(currency.active):
            raise CurrencyGuardError(message or "La moneda indicada esta inactiva.")
        return currency

    def assert_can_deactivate(self, currency: Currency) -> None:
        """Evita desactivar monedas criticas para companias o libros activos."""
        if bool(currency.default):
            raise CurrencyGuardError("No se puede deshabilitar la moneda predeterminada del sistema.")
        active_company = database.session.execute(
            database.select(Entity).filter(Entity.currency == currency.code, Entity.enabled.is_(True)).limit(1)
        ).scalar_one_or_none()
        if active_company is not None:
            raise CurrencyGuardError("No se puede deshabilitar la moneda porque esta en uso por una compania activa.")
        active_book = database.session.execute(
            database.select(Book).filter(Book.currency == currency.code, Book.status == "activo").limit(1)
        ).scalar_one_or_none()
        if active_book is not None:
            raise CurrencyGuardError("No se puede deshabilitar la moneda porque esta en uso por un libro contable activo.")

    def apply_currency_edit(self, currency: Currency, *, active: bool, default: bool) -> None:
        """Aplica cambios de una moneda preservando reglas de negocio."""
        if default and not active:
            raise CurrencyGuardError("La moneda predeterminada del sistema debe permanecer activa.")
        if not active:
            self.assert_can_deactivate(currency)
        if default:
            current_defaults = database.session.execute(
                database.select(Currency).filter(Currency.code != currency.code, Currency.default.is_(True))
            ).scalars()
            for current_default in current_defaults:
                current_default.default = False
        currency.active = active
        currency.default = default

    def validate_company_functional_currency(self, company_code: str | None) -> Currency:
        """Valida la moneda funcional activa de una compania."""
        if not company_code:
            raise CurrencyGuardError("La compania es obligatoria.")
        company = database.session.execute(database.select(Entity).filter_by(code=company_code)).scalar_one_or_none()
        if company is None or company.enabled is False:
            raise CurrencyGuardError("La compania indicada no existe o esta inactiva.")
        return self.validate_active_currency(
            company.currency,
            "La moneda funcional de la compania debe existir y estar activa.",
        )
