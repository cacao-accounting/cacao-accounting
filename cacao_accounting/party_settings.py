"""Servicios compartidos para configuracion de terceros por compania."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from sqlalchemy import select

from cacao_accounting.contabilidad.default_accounts import account_label
from cacao_accounting.database import Accounts, CompanyDefaultAccount, CompanyParty, PartyAccount, TaxTemplate, database


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
    if party_type == "customer":
        resolved_account = _account_for_company(company, party_account.receivable_account_id if party_account else None)
        if resolved_account is None:
            resolved_account = default_account
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
            allow_purchase_invoice_without_order=False,
            allow_purchase_invoice_without_receipt=False,
        )

    resolved_account = _account_for_company(company, party_account.payable_account_id if party_account else None)
    if resolved_account is None:
        resolved_account = default_account
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
        allow_purchase_invoice_without_order=(
            bool(company_party.allow_purchase_invoice_without_order) if company_party else False
        ),
        allow_purchase_invoice_without_receipt=(
            bool(company_party.allow_purchase_invoice_without_receipt) if company_party else False
        ),
    )


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
            allow_purchase_invoice_without_order=False,
            allow_purchase_invoice_without_receipt=False,
        )

    payable_account_id = values.get("payable_account_id") or base.payable_account_id
    payable_account = _account_for_company(company, payable_account_id)
    tax_template_id = values.get("tax_template_id") or base.tax_template_id
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


def upsert_party_company_settings(
    party_id: str,
    party_type: str,
    company: str,
    *,
    is_active: bool,
    receivable_account_id: str | None,
    payable_account_id: str | None,
    tax_template_id: str | None,
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

    company_party = _party_company_record(party_id, company)
    if company_party is None:
        company_party = CompanyParty(company=company, party_id=party_id)
        database.session.add(company_party)

    company_party.is_active = is_active
    company_party.tax_template_id = tax_template_id
    company_party.allow_purchase_invoice_without_order = allow_purchase_invoice_without_order
    company_party.allow_purchase_invoice_without_receipt = allow_purchase_invoice_without_receipt

    party_account = _party_account_record(party_id, company)
    if party_account is None:
        party_account = PartyAccount(party_id=party_id, company=company)
        database.session.add(party_account)

    party_account.receivable_account_id = receivable_account_id
    party_account.payable_account_id = payable_account_id
