"""Servicios compartidos para configuracion de terceros por compania."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from sqlalchemy import or_, select

from cacao_accounting.contabilidad.default_accounts import account_label
from cacao_accounting.database import (
    Accounts,
    CompanyDefaultAccount,
    CompanyParty,
    PartyAccount,
    PriceList,
    TaxRule,
    TaxTemplate,
    database,
)


def _request_values(form: Mapping[str, Any], key: str) -> list[str]:
    """Devuelve los valores de una clave repetible de formulario."""
    getter = getattr(form, "getlist", None)
    if callable(getter):
        return [str(value or "") for value in getter(key)]
    return []


@dataclass(frozen=True)
class PartyCompanySettings:
    """Valores de configuracion por compania para un tercero."""

    company: str
    company_label: str
    is_active: bool
    receivable_account_id: str | None
    receivable_account_label: str
    payable_account_id: str | None
    payable_account_label: str
    tax_template_id: str | None
    tax_template_label: str
    default_tax_rule_id: str | None
    default_tax_rule_label: str
    default_price_list_id: str | None
    default_price_list_label: str
    allow_purchase_invoice_without_order: bool
    allow_purchase_invoice_without_receipt: bool
    default_currency: str | None
    default_income_account_id: str | None = None
    default_income_account_label: str = ""
    default_expense_account_id: str | None = None
    default_expense_account_label: str = ""
    default_purchase_account_id: str | None = None
    default_purchase_account_label: str = ""
    default_advance_account_id: str | None = None
    default_advance_account_label: str = ""
    default_cost_center: str | None = None
    default_business_unit: str | None = None
    default_bank_name: str | None = None
    default_bank_account_no: str | None = None
    default_bank_iban: str | None = None
    block_overdue: bool = False


@dataclass(frozen=True)
class PartyCompanySettingsParams:
    """Parametros para crear o actualizar configuracion de tercero por compania."""

    is_active: bool
    receivable_account_id: str | None
    payable_account_id: str | None
    tax_template_id: str | None
    default_tax_rule_id: str | None
    default_price_list_id: str | None
    allow_purchase_invoice_without_order: bool
    allow_purchase_invoice_without_receipt: bool
    default_currency: str | None = None
    default_income_account_id: str | None = None
    default_income_account_label: str = ""
    default_expense_account_id: str | None = None
    default_expense_account_label: str = ""
    default_purchase_account_id: str | None = None
    default_purchase_account_label: str = ""
    default_advance_account_id: str | None = None
    default_advance_account_label: str = ""
    default_cost_center: str | None = None
    default_business_unit: str | None = None
    default_bank_name: str | None = None
    default_bank_account_no: str | None = None
    default_bank_iban: str | None = None
    block_overdue: bool = False


def _account_by_id(account_id: str | None) -> Accounts | None:
    if not account_id:
        return None
    return database.session.get(Accounts, account_id)


def _account_for_company(company: str, account_id: str | None) -> Accounts | None:
    account = _account_by_id(account_id)
    if not account or account.entity != company:
        return None
    return account


def _tax_template_by_id(template_id: str | None) -> TaxTemplate | None:
    if not template_id:
        return None
    return database.session.get(TaxTemplate, template_id)


def _tax_template_label(template_id: str | None) -> str:
    template = _tax_template_by_id(template_id)
    return template.name if template else ""


def _tax_rule_by_id(rule_id: str | None) -> TaxRule | None:
    if not rule_id:
        return None
    return database.session.get(TaxRule, rule_id)


def _tax_rule_label(rule_id: str | None) -> str:
    rule = _tax_rule_by_id(rule_id)
    return rule.name if rule else ""


def _price_list_by_id(price_list_id: str | None) -> PriceList | None:
    if not price_list_id:
        return None
    return database.session.get(PriceList, price_list_id)


def _price_list_label(price_list_id: str | None) -> str:
    price_list = _price_list_by_id(price_list_id)
    return price_list.name if price_list else ""


def _company_label(company: str) -> str:
    return company


def _default_company_account(company: str, role: str) -> Accounts | None:
    config = database.session.execute(select(CompanyDefaultAccount).filter_by(company=company)).scalar_one_or_none()
    if not config:
        return None
    default_field = "default_receivable" if role == "customer" else "default_payable"
    return _account_for_company(company, getattr(config, default_field))


def _party_company_record(party_id: str, company: str) -> CompanyParty | None:
    return database.session.execute(select(CompanyParty).filter_by(party_id=party_id, company=company)).scalar_one_or_none()


def _party_account_record(party_id: str, company: str) -> PartyAccount | None:
    return database.session.execute(select(PartyAccount).filter_by(party_id=party_id, company=company)).scalar_one_or_none()


def _default_company_price_list(company: str, role: str) -> PriceList | None:
    query = select(PriceList).where(PriceList.is_active.is_(True), PriceList.is_default.is_(True))
    if role == "customer":
        query = query.where(PriceList.is_selling.is_(True))
    else:
        query = query.where(PriceList.is_buying.is_(True))
    query = query.where(or_(PriceList.company == company, PriceList.company.is_(None)))
    query = query.order_by(PriceList.company.is_(None), PriceList.name)
    return database.session.execute(query).scalars().first()


def _settings_for_account_labels(company: str, account_id: str | None) -> tuple[str | None, str]:
    account = _account_for_company(company, account_id) if account_id else None
    return (account.id if account else None, account_label(account))


def _build_settings(
    company: str,
    company_party: CompanyParty | None,
    receivable_account: Accounts | None,
    payable_account: Accounts | None,
    price_list: PriceList | None,
) -> PartyCompanySettings:
    """Construye la configuración completa por compañía."""
    inc_id, inc_label = _settings_for_account_labels(
        company, company_party.default_income_account_id if company_party else None
    )
    exp_id, exp_label = _settings_for_account_labels(
        company, company_party.default_expense_account_id if company_party else None
    )
    pur_id, pur_label = _settings_for_account_labels(
        company, company_party.default_purchase_account_id if company_party else None
    )
    adv_id, adv_label = _settings_for_account_labels(
        company, company_party.default_advance_account_id if company_party else None
    )
    return PartyCompanySettings(
        company=company,
        company_label=_company_label(company),
        is_active=bool(company_party.is_active) if company_party else True,
        receivable_account_id=receivable_account.id if receivable_account else None,
        receivable_account_label=account_label(receivable_account),
        payable_account_id=payable_account.id if payable_account else None,
        payable_account_label=account_label(payable_account),
        tax_template_id=company_party.tax_template_id if company_party else None,
        tax_template_label=_tax_template_label(company_party.tax_template_id if company_party else None),
        default_tax_rule_id=company_party.default_tax_rule_id if company_party else None,
        default_tax_rule_label=_tax_rule_label(company_party.default_tax_rule_id if company_party else None),
        default_price_list_id=price_list.id if price_list else None,
        default_price_list_label=price_list.name if price_list else "",
        allow_purchase_invoice_without_order=(
            bool(company_party.allow_purchase_invoice_without_order) if company_party else False
        ),
        allow_purchase_invoice_without_receipt=(
            bool(company_party.allow_purchase_invoice_without_receipt) if company_party else False
        ),
        default_currency=company_party.default_currency if company_party else None,
        default_income_account_id=inc_id,
        default_income_account_label=inc_label,
        default_expense_account_id=exp_id,
        default_expense_account_label=exp_label,
        default_purchase_account_id=pur_id,
        default_purchase_account_label=pur_label,
        default_advance_account_id=adv_id,
        default_advance_account_label=adv_label,
        default_cost_center=company_party.default_cost_center if company_party else None,
        default_business_unit=company_party.default_business_unit if company_party else None,
        default_bank_name=company_party.default_bank_name if company_party else None,
        default_bank_account_no=company_party.default_bank_account_no if company_party else None,
        default_bank_iban=company_party.default_bank_iban if company_party else None,
        block_overdue=bool(company_party.block_overdue) if company_party else False,
    )


def build_party_company_settings(
    party_id: str,
    company: str,
    *,
    role: str | None = None,
) -> PartyCompanySettings:
    """Construye los valores a prellenar en la tabla de configuracion por compania."""
    company_party = _party_company_record(party_id, company)
    party_account = _party_account_record(party_id, company) if party_id else None
    if role is None:
        from cacao_accounting.database import Party as PartyModel

        party = database.session.get(PartyModel, party_id)
        if party:
            role = "customer" if party.is_customer else "supplier"
    if role not in ("customer", "supplier"):
        role = "customer"
    default_account = _default_company_account(company, role)
    default_price_list = _default_company_price_list(company, role)
    configured_price_list = (
        _price_list_for_company(company, company_party.default_price_list_id)
        if company_party and company_party.default_price_list_id
        else None
    )
    resolved_price_list = configured_price_list or default_price_list

    receivable_account: Accounts | None = None
    payable_account: Accounts | None = None
    if role == "customer":
        account_id = party_account.receivable_account_id if party_account else None
        receivable_account = _account_for_company(company, account_id) or default_account
    else:
        account_id = party_account.payable_account_id if party_account else None
        payable_account = _account_for_company(company, account_id) or default_account

    return _build_settings(company, company_party, receivable_account, payable_account, resolved_price_list)


def party_company_settings_rows(
    party_id: str | None,
    selected_company: str | None,
    *,
    role: str,
) -> list[dict[str, Any]]:
    """Devuelve filas editables de configuracion por compania para Cliente/Proveedor."""
    companies: list[str] = []
    if party_id:
        query = select(CompanyParty.company).filter_by(party_id=party_id).order_by(CompanyParty.company)
        companies = [str(company) for company in database.session.execute(query).scalars()]
    if not companies and selected_company:
        companies = [selected_company]
    return [
        _party_company_settings_row(build_party_company_settings(party_id or "", company, role=role)) for company in companies
    ]


def _party_company_settings_row(settings: PartyCompanySettings) -> dict[str, Any]:
    """Convierte una configuracion por compania en payload JSON para Alpine."""
    return {
        "company": settings.company or "",
        "company_label": settings.company_label or settings.company or "",
        "is_active": bool(settings.is_active),
        "receivable_account_id": settings.receivable_account_id or "",
        "receivable_account_label": settings.receivable_account_label or "",
        "payable_account_id": settings.payable_account_id or "",
        "payable_account_label": settings.payable_account_label or "",
        "default_price_list_id": settings.default_price_list_id or "",
        "default_price_list_label": settings.default_price_list_label or "",
        "default_tax_rule_id": settings.default_tax_rule_id or "",
        "default_tax_rule_label": settings.default_tax_rule_label or "",
        "tax_template_id": settings.tax_template_id or "",
        "tax_template_label": settings.tax_template_label or "",
        "allow_purchase_invoice_without_order": bool(settings.allow_purchase_invoice_without_order),
        "allow_purchase_invoice_without_receipt": bool(settings.allow_purchase_invoice_without_receipt),
    }


def draft_party_company_settings_rows(role: str, values: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Reconstruye filas de configuracion por compania desde un POST fallido."""
    companies = _request_values(values, "company")
    rows: list[dict[str, Any]] = []
    field_names = (
        "receivable_account_id",
        "payable_account_id",
        "default_price_list_id",
        "default_tax_rule_id",
        "tax_template_id",
        "company_is_active",
        "allow_purchase_invoice_without_order",
        "allow_purchase_invoice_without_receipt",
    )
    fields = {field: _request_values(values, field) for field in field_names}
    for index, company in enumerate(companies):
        if not str(company or "").strip():
            continue
        rows.append(
            {
                "company": company,
                "company_label": company,
                "is_active": _truthy_row_value(fields["company_is_active"], index, default=True),
                "receivable_account_id": _row_value(fields["receivable_account_id"], index) if role == "customer" else "",
                "receivable_account_label": _row_value(fields["receivable_account_id"], index) if role == "customer" else "",
                "payable_account_id": _row_value(fields["payable_account_id"], index) if role == "supplier" else "",
                "payable_account_label": _row_value(fields["payable_account_id"], index) if role == "supplier" else "",
                "default_price_list_id": _row_value(fields["default_price_list_id"], index),
                "default_price_list_label": _row_value(fields["default_price_list_id"], index),
                "default_tax_rule_id": _row_value(fields["default_tax_rule_id"], index),
                "default_tax_rule_label": _row_value(fields["default_tax_rule_id"], index),
                "tax_template_id": _row_value(fields["tax_template_id"], index),
                "tax_template_label": _row_value(fields["tax_template_id"], index),
                "allow_purchase_invoice_without_order": _truthy_row_value(
                    fields["allow_purchase_invoice_without_order"], index
                ),
                "allow_purchase_invoice_without_receipt": _truthy_row_value(
                    fields["allow_purchase_invoice_without_receipt"], index
                ),
            }
        )
    return rows or [
        {
            "company": "",
            "company_label": "",
            "is_active": True,
            "receivable_account_id": "",
            "receivable_account_label": "",
            "payable_account_id": "",
            "payable_account_label": "",
            "default_price_list_id": "",
            "default_price_list_label": "",
            "default_tax_rule_id": "",
            "default_tax_rule_label": "",
            "tax_template_id": "",
            "tax_template_label": "",
            "allow_purchase_invoice_without_order": False,
            "allow_purchase_invoice_without_receipt": False,
        }
    ]


def _row_value(values: list[str], index: int) -> str:
    return values[index].strip() if index < len(values) else ""


def _truthy_row_value(values: list[str], index: int, *, default: bool = False) -> bool:
    if index >= len(values):
        return default
    return values[index].strip().lower() in {"1", "true", "yes", "on"}


def upsert_party_company_settings_rows(party_id: str, role: str, values: Mapping[str, Any]) -> None:
    """Crea o actualiza multiples filas de configuracion por compania para un tercero."""
    companies = _request_values(values, "company")
    fields = {
        "company_is_active": _request_values(values, "company_is_active"),
        "receivable_account_id": _request_values(values, "receivable_account_id"),
        "payable_account_id": _request_values(values, "payable_account_id"),
        "tax_template_id": _request_values(values, "tax_template_id"),
        "default_tax_rule_id": _request_values(values, "default_tax_rule_id"),
        "default_price_list_id": _request_values(values, "default_price_list_id"),
        "allow_purchase_invoice_without_order": _request_values(values, "allow_purchase_invoice_without_order"),
        "allow_purchase_invoice_without_receipt": _request_values(values, "allow_purchase_invoice_without_receipt"),
    }
    seen: set[str] = set()
    for index, raw_company in enumerate(companies):
        company = str(raw_company or "").strip()
        if not company:
            continue
        if company in seen:
            raise ValueError("No se puede repetir la misma compañía en la configuración.")
        seen.add(company)
        params = PartyCompanySettingsParams(
            is_active=_truthy_row_value(fields["company_is_active"], index, default=True),
            receivable_account_id=_row_value(fields["receivable_account_id"], index) or None,
            payable_account_id=_row_value(fields["payable_account_id"], index) or None,
            tax_template_id=_row_value(fields["tax_template_id"], index) or None,
            default_tax_rule_id=_row_value(fields["default_tax_rule_id"], index) or None,
            default_price_list_id=_row_value(fields["default_price_list_id"], index) or None,
            allow_purchase_invoice_without_order=_truthy_row_value(fields["allow_purchase_invoice_without_order"], index),
            allow_purchase_invoice_without_receipt=_truthy_row_value(fields["allow_purchase_invoice_without_receipt"], index),
        )
        upsert_party_company_settings(party_id, role, company, params)
    _delete_removed_company_settings(party_id, seen)


def _delete_removed_company_settings(party_id: str, submitted_companies: set[str]) -> None:
    """Elimina configuraciones por compania removidas de la tabla editable."""
    existing = database.session.execute(select(CompanyParty).filter_by(party_id=party_id)).scalars().all()
    for company_party in existing:
        if company_party.company in submitted_companies:
            continue
        party_account = _party_account_record(party_id, company_party.company)
        if party_account is not None:
            database.session.delete(party_account)
        database.session.delete(company_party)


def _validate_account(company: str, account_id: str | None, expected_type: str) -> None:
    if not account_id:
        return
    account = _account_for_company(company, account_id)
    if account is None:
        raise ValueError("La cuenta seleccionada no pertenece a la compañía.")
    account_type = (account.account_type or "").strip().lower()
    if account_type and account_type != expected_type:
        raise ValueError(f"La cuenta {account.code} debe ser de tipo {expected_type}.")


def _validate_tax_template(company: str, tax_template_id: str | None) -> None:
    if not tax_template_id:
        return
    template = _tax_template_by_id(tax_template_id)
    if template is None:
        raise ValueError("La plantilla de impuestos seleccionada no existe.")
    if template.company not in (None, company):
        raise ValueError("La plantilla de impuestos debe pertenecer a la misma compañía.")


def _validate_tax_rule(company: str, rule_id: str | None, role: str) -> None:
    if not rule_id:
        return
    rule = _tax_rule_by_id(rule_id)
    if rule is None:
        raise ValueError("La regla fiscal seleccionada no existe.")
    if rule.company not in (None, company):
        raise ValueError("La regla fiscal debe pertenecer a la misma compañía.")
    expected_applies_to = "sales" if role == "customer" else "purchase"
    if rule.applies_to not in ("both", expected_applies_to):
        raise ValueError("La regla fiscal no corresponde al tipo de tercero seleccionado.")
    if not rule.is_active:
        raise ValueError("La regla fiscal seleccionada no esta activa.")


def _price_list_for_company(company: str, price_list_id: str | None) -> PriceList | None:
    price_list = _price_list_by_id(price_list_id)
    if not price_list:
        return None
    if price_list.company not in (None, company):
        return None
    return price_list


def _validate_price_list(company: str, price_list_id: str | None, role: str) -> None:
    if not price_list_id:
        return
    price_list = _price_list_for_company(company, price_list_id)
    if price_list is None:
        raise ValueError("La lista de precio seleccionada no pertenece a la compañía.")
    if not price_list.is_active:
        raise ValueError("La lista de precio seleccionada no esta activa.")
    if role == "customer" and not price_list.is_selling:
        raise ValueError("La lista de precio debe ser de ventas para clientes.")
    if role == "supplier" and not price_list.is_buying:
        raise ValueError("La lista de precio debe ser de compras para proveedores.")


def upsert_party_company_settings(
    party_id: str,
    role: str,
    company: str,
    params: PartyCompanySettingsParams,
) -> None:
    """Crea o actualiza la configuracion de activacion del tercero por compania."""
    receivable_account_id = params.receivable_account_id
    payable_account_id = params.payable_account_id

    if role == "customer":
        _validate_account(company, receivable_account_id, "receivable")
        payable_account_id = None
    else:
        _validate_account(company, payable_account_id, "payable")
        receivable_account_id = None

    _validate_tax_template(company, params.tax_template_id)
    _validate_tax_rule(company, params.default_tax_rule_id, role)
    _validate_price_list(company, params.default_price_list_id, role)

    company_party = _party_company_record(party_id, company)
    if company_party is None:
        company_party = CompanyParty(company=company, party_id=party_id)
        database.session.add(company_party)

    company_party.is_active = params.is_active
    company_party.tax_template_id = params.tax_template_id
    company_party.default_tax_rule_id = params.default_tax_rule_id
    company_party.default_price_list_id = params.default_price_list_id
    company_party.allow_purchase_invoice_without_order = params.allow_purchase_invoice_without_order
    company_party.allow_purchase_invoice_without_receipt = params.allow_purchase_invoice_without_receipt
    company_party.default_currency = params.default_currency
    company_party.default_income_account_id = params.default_income_account_id
    company_party.default_expense_account_id = params.default_expense_account_id
    company_party.default_purchase_account_id = params.default_purchase_account_id
    company_party.default_advance_account_id = params.default_advance_account_id
    company_party.default_cost_center = params.default_cost_center
    company_party.default_business_unit = params.default_business_unit
    company_party.default_bank_name = params.default_bank_name
    company_party.default_bank_account_no = params.default_bank_account_no
    company_party.default_bank_iban = params.default_bank_iban
    company_party.block_overdue = params.block_overdue

    party_account = _party_account_record(party_id, company)
    if party_account is None:
        party_account = PartyAccount(party_id=party_id, company=company)
        database.session.add(party_account)

    party_account.receivable_account_id = receivable_account_id
    party_account.payable_account_id = payable_account_id
