"""Servicios compartidos para configuracion de terceros por compania."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

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


def _default_company_account(company: str, party_type: str) -> Accounts | None:
    config = database.session.execute(select(CompanyDefaultAccount).filter_by(company=company)).scalar_one_or_none()
    if not config:
        return None
    default_field = "default_receivable" if party_type == "customer" else "default_payable"
    return _account_for_company(company, getattr(config, default_field))


def _party_company_record(party_id: str, company: str) -> CompanyParty | None:
    return database.session.execute(select(CompanyParty).filter_by(party_id=party_id, company=company)).scalar_one_or_none()


def _party_account_record(party_id: str, company: str) -> PartyAccount | None:
    return database.session.execute(select(PartyAccount).filter_by(party_id=party_id, company=company)).scalar_one_or_none()


def _default_company_price_list(company: str, party_type: str) -> PriceList | None:
    query = select(PriceList).where(PriceList.is_active.is_(True), PriceList.is_default.is_(True))
    if party_type == "customer":
        query = query.where(PriceList.is_selling.is_(True))
    else:
        query = query.where(PriceList.is_buying.is_(True))
    query = query.where(or_(PriceList.company == company, PriceList.company.is_(None)))
    query = query.order_by(PriceList.company.is_(None), PriceList.name)
    return database.session.execute(query).scalars().first()


def _build_customer_settings(
    company: str,
    resolved_account: Accounts | None,
    company_party: CompanyParty | None,
    price_list: PriceList | None,
) -> PartyCompanySettings:
    """Construye configuración para cliente."""
    return PartyCompanySettings(
        company=company,
        company_label=_company_label(company),
        is_active=bool(company_party.is_active) if company_party else True,
        receivable_account_id=resolved_account.id if resolved_account else None,
        receivable_account_label=account_label(resolved_account),
        payable_account_id=None,
        payable_account_label="",
        tax_template_id=company_party.tax_template_id if company_party else None,
        tax_template_label=_tax_template_label(company_party.tax_template_id if company_party else None),
        default_tax_rule_id=company_party.default_tax_rule_id if company_party else None,
        default_tax_rule_label=_tax_rule_label(company_party.default_tax_rule_id if company_party else None),
        default_price_list_id=price_list.id if price_list else None,
        default_price_list_label=price_list.name if price_list else "",
        allow_purchase_invoice_without_order=False,
        allow_purchase_invoice_without_receipt=False,
    )


def _build_supplier_settings(
    company: str,
    resolved_account: Accounts | None,
    company_party: CompanyParty | None,
    price_list: PriceList | None,
) -> PartyCompanySettings:
    """Construye configuración para proveedor."""
    return PartyCompanySettings(
        company=company,
        company_label=_company_label(company),
        is_active=bool(company_party.is_active) if company_party else True,
        receivable_account_id=None,
        receivable_account_label="",
        payable_account_id=resolved_account.id if resolved_account else None,
        payable_account_label=account_label(resolved_account),
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
    )


def build_party_company_settings(
    party_type: str,
    company: str,
    *,
    party_id: str | None = None,
) -> PartyCompanySettings:
    """Construye los valores a prellenar en la tabla de configuracion por compania."""
    company_party = _party_company_record(party_id, company) if party_id else None
    party_account = _party_account_record(party_id, company) if party_id else None
    default_account = _default_company_account(company, party_type)
    default_price_list = _default_company_price_list(company, party_type)
    configured_price_list = (
        _price_list_for_company(company, company_party.default_price_list_id)
        if company_party and company_party.default_price_list_id
        else None
    )
    resolved_price_list = configured_price_list or default_price_list

    if party_type == "customer":
        account_id = party_account.receivable_account_id if party_account else None
        resolved_account = _account_for_company(company, account_id) or default_account
        return _build_customer_settings(company, resolved_account, company_party, resolved_price_list)

    account_id = party_account.payable_account_id if party_account else None
    resolved_account = _account_for_company(company, account_id) or default_account
    return _build_supplier_settings(company, resolved_account, company_party, resolved_price_list)


def draft_party_company_settings(
    party_type: str,
    company: str,
    values: Mapping[str, str | None],
) -> PartyCompanySettings:
    """Construye un estado temporal a partir del formulario enviado."""
    base = build_party_company_settings(party_type, company)
    if party_type == "customer":
        receivable_account_id = values.get("receivable_account_id") or base.receivable_account_id
        receivable_account = _account_for_company(company, receivable_account_id)
        tax_template_id = values.get("tax_template_id") or base.tax_template_id
        default_tax_rule_id = values.get("default_tax_rule_id") or base.default_tax_rule_id
        default_price_list_id = values.get("default_price_list_id") or base.default_price_list_id
        default_price_list = _price_list_for_company(company, default_price_list_id)
        return PartyCompanySettings(
            company=company,
            company_label=base.company_label,
            is_active=values.get("company_is_active") is not None,
            receivable_account_id=receivable_account.id if receivable_account else None,
            receivable_account_label=account_label(receivable_account),
            payable_account_id=None,
            payable_account_label="",
            tax_template_id=tax_template_id,
            tax_template_label=_tax_template_label(tax_template_id),
            default_tax_rule_id=default_tax_rule_id,
            default_tax_rule_label=_tax_rule_label(default_tax_rule_id),
            default_price_list_id=default_price_list.id if default_price_list else None,
            default_price_list_label=default_price_list.name if default_price_list else "",
            allow_purchase_invoice_without_order=False,
            allow_purchase_invoice_without_receipt=False,
        )

    payable_account_id = values.get("payable_account_id") or base.payable_account_id
    payable_account = _account_for_company(company, payable_account_id)
    tax_template_id = values.get("tax_template_id") or base.tax_template_id
    default_tax_rule_id = values.get("default_tax_rule_id") or base.default_tax_rule_id
    default_price_list_id = values.get("default_price_list_id") or base.default_price_list_id
    default_price_list = _price_list_for_company(company, default_price_list_id)
    return PartyCompanySettings(
        company=company,
        company_label=base.company_label,
        is_active=values.get("company_is_active") is not None,
        receivable_account_id=None,
        receivable_account_label="",
        payable_account_id=payable_account.id if payable_account else None,
        payable_account_label=account_label(payable_account),
        tax_template_id=tax_template_id,
        tax_template_label=_tax_template_label(tax_template_id),
        default_tax_rule_id=default_tax_rule_id,
        default_tax_rule_label=_tax_rule_label(default_tax_rule_id),
        default_price_list_id=default_price_list.id if default_price_list else None,
        default_price_list_label=default_price_list.name if default_price_list else "",
        allow_purchase_invoice_without_order=values.get("allow_purchase_invoice_without_order") is not None,
        allow_purchase_invoice_without_receipt=values.get("allow_purchase_invoice_without_receipt") is not None,
    )


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


def _validate_tax_rule(company: str, rule_id: str | None, party_type: str) -> None:
    if not rule_id:
        return
    rule = _tax_rule_by_id(rule_id)
    if rule is None:
        raise ValueError("La regla fiscal seleccionada no existe.")
    if rule.company not in (None, company):
        raise ValueError("La regla fiscal debe pertenecer a la misma compañía.")
    expected_applies_to = "sales" if party_type == "customer" else "purchase"
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


def _validate_price_list(company: str, price_list_id: str | None, party_type: str) -> None:
    if not price_list_id:
        return
    price_list = _price_list_for_company(company, price_list_id)
    if price_list is None:
        raise ValueError("La lista de precio seleccionada no pertenece a la compañía.")
    if not price_list.is_active:
        raise ValueError("La lista de precio seleccionada no esta activa.")
    if party_type == "customer" and not price_list.is_selling:
        raise ValueError("La lista de precio debe ser de ventas para clientes.")
    if party_type == "supplier" and not price_list.is_buying:
        raise ValueError("La lista de precio debe ser de compras para proveedores.")


def upsert_party_company_settings(
    party_id: str,
    party_type: str,
    company: str,
    *,
    is_active: bool,
    receivable_account_id: str | None,
    payable_account_id: str | None,
    tax_template_id: str | None,
    default_tax_rule_id: str | None,
    default_price_list_id: str | None,
    allow_purchase_invoice_without_order: bool,
    allow_purchase_invoice_without_receipt: bool,
) -> None:
    """Crea o actualiza la configuracion de activacion del tercero por compania."""
    if party_type == "customer":
        _validate_account(company, receivable_account_id, "receivable")
        payable_account_id = None
    else:
        _validate_account(company, payable_account_id, "payable")
        receivable_account_id = None

    _validate_tax_template(company, tax_template_id)
    _validate_tax_rule(company, default_tax_rule_id, party_type)
    _validate_price_list(company, default_price_list_id, party_type)

    company_party = _party_company_record(party_id, company)
    if company_party is None:
        company_party = CompanyParty(company=company, party_id=party_id)
        database.session.add(company_party)

    company_party.is_active = is_active
    company_party.tax_template_id = tax_template_id
    company_party.default_tax_rule_id = default_tax_rule_id
    company_party.default_price_list_id = default_price_list_id
    company_party.allow_purchase_invoice_without_order = allow_purchase_invoice_without_order
    company_party.allow_purchase_invoice_without_receipt = allow_purchase_invoice_without_receipt

    party_account = _party_account_record(party_id, company)
    if party_account is None:
        party_account = PartyAccount(party_id=party_id, company=company)
        database.session.add(party_account)

    party_account.receivable_account_id = receivable_account_id
    party_account.payable_account_id = payable_account_id
