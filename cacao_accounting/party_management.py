"""Servicios compartidos para maestros de terceros."""

from __future__ import annotations

from datetime import date
from dataclasses import dataclass
from typing import Mapping

from sqlalchemy import select

from cacao_accounting.contabilidad.default_accounts import account_label
from cacao_accounting.database import (
    Address,
    Accounts,
    CompanyParty,
    Contact,
    Party,
    PartyAccount,
    PartyAddress,
    PartyContact,
    PartyGroup,
    database,
)
from cacao_accounting.database.helpers import generate_identifier
from cacao_accounting.party_settings import PartyCompanySettings, build_party_company_settings

NATIONALITY_LABELS = {"national": "Nacional", "foreign": "Extranjero"}
PERSON_TYPE_LABELS = {"natural": "Natural", "juridical": "Jurídica"}


@dataclass(frozen=True)
class ContactRow:
    """Contacto asociado a un tercero."""

    link_id: str
    contact: Contact
    role: str


@dataclass(frozen=True)
class AddressRow:
    """Direccion asociada a un tercero."""

    link_id: str
    address: Address
    address_type: str
    is_primary: bool


@dataclass(frozen=True)
class PartyDetailContext:
    """Datos agregados para la vista de detalle de un tercero."""

    group_label: str
    nationality_label: str
    person_type_label: str
    primary_phone: str
    primary_email: str
    website: str
    primary_address_label: str
    company_settings: list[PartyCompanySettings]
    contacts: list[ContactRow]
    addresses: list[AddressRow]


def party_group_label(group_id: str | None) -> str:
    """Devuelve el nombre de un grupo de tercero."""
    if not group_id:
        return ""
    group = database.session.get(PartyGroup, group_id)
    return group.name if group else ""


def validate_party_group(group_id: str | None, role: str) -> PartyGroup | None:
    """Valida que el grupo exista, este activo y corresponda al rol del tercero."""
    if not group_id:
        return None
    if role not in ("customer", "supplier"):
        raise ValueError("El rol debe ser 'customer' o 'supplier'.")
    group = database.session.get(PartyGroup, group_id)
    if not group:
        raise ValueError("El tipo seleccionado no existe.")
    if group.group_type != role:
        raise ValueError("El tipo seleccionado no corresponde al tercero.")
    if not group.is_active:
        raise ValueError("El tipo seleccionado no esta activo.")
    return group


def apply_party_group(party: Party, group_id: str | None, role: str) -> None:
    """Asigna el grupo segun el rol (customer/supplier)."""
    group = validate_party_group(group_id, role)
    party.party_group_id = group.id if group else None


def apply_party_profile(party: Party, values: Mapping[str, str | None]) -> None:
    """Asigna los campos basicos y legales de un tercero."""
    nationality_type = (values.get("nationality_type") or "").strip() or None
    person_type = (values.get("person_type") or "").strip() or None
    if nationality_type and nationality_type not in NATIONALITY_LABELS:
        raise ValueError("La nacionalidad seleccionada no es valida.")
    if person_type and person_type not in PERSON_TYPE_LABELS:
        raise ValueError("El tipo de persona seleccionada no es valido.")

    party.nationality_type = nationality_type
    party.person_type = person_type
    party.fiscal_name = _clean_text(values.get("fiscal_name"))
    party.primary_phone = _clean_text(values.get("primary_phone"))
    party.primary_email = _clean_text(values.get("primary_email"))
    party.website = _clean_text(values.get("website"))
    party.primary_address_line1 = _clean_text(values.get("primary_address_line1"))
    party.primary_address_line2 = _clean_text(values.get("primary_address_line2"))
    party.primary_address_city = _clean_text(values.get("primary_address_city"))
    party.primary_address_state = _clean_text(values.get("primary_address_state"))
    party.primary_address_country = _clean_text(values.get("primary_address_country"))
    party.primary_address_postal_code = _clean_text(values.get("primary_address_postal_code"))
    party.legal_representative_name = _clean_text(values.get("legal_representative_name"))
    party.legal_representative_id = _clean_text(values.get("legal_representative_id"))
    party.legal_representative_position = _clean_text(values.get("legal_representative_position"))
    party.legal_representative_email = _clean_text(values.get("legal_representative_email"))
    party.legal_representative_phone = _clean_text(values.get("legal_representative_phone"))
    party.legal_constitution_date = _parse_date(values.get("legal_constitution_date"))
    party.legal_constitution_place = _clean_text(values.get("legal_constitution_place"))
    party.legal_registration_number = _clean_text(values.get("legal_registration_number"))
    party.legal_notification_address = _clean_text(values.get("legal_notification_address"))
    party.legal_notes = _clean_text(values.get("legal_notes"))


def _clean_text(value: str | None) -> str | None:
    """Normaliza texto opcional eliminando espacios vacios."""
    cleaned = (value or "").strip()
    return cleaned or None


def _parse_date(value: str | None) -> date | None:
    """Convierte una fecha ISO opcional en un objeto date."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - validado en rutas
        raise ValueError("La fecha de constitucion no es valida.") from exc


def _choice_label(labels: dict[str, str], value: str | None) -> str:
    """Resuelve un valor de lista a su etiqueta legible."""
    if not value:
        return ""
    return labels.get(value, "")


def _compose_address_label(
    line1: str | None,
    line2: str | None,
    city: str | None,
    state: str | None,
    country: str | None,
    postal_code: str | None,
) -> str:
    """Concatena una direccion principal en formato compacto."""
    parts = [line1, line2, city, state, postal_code, country]
    return ", ".join([part for part in parts if part])


def build_party_detail_context(party: Party) -> PartyDetailContext:
    """Construye el contexto completo del detalle de cliente/proveedor."""
    company_rows = (
        database.session.execute(select(CompanyParty).filter_by(party_id=party.id).order_by(CompanyParty.company))
        .scalars()
        .all()
    )
    settings = [build_party_company_settings(party.id, row.company) for row in company_rows]
    return PartyDetailContext(
        group_label=party_group_label(party.party_group_id) or "",
        nationality_label=_choice_label(NATIONALITY_LABELS, party.nationality_type),
        person_type_label=_choice_label(PERSON_TYPE_LABELS, party.person_type),
        primary_phone=party.primary_phone or "",
        primary_email=party.primary_email or "",
        website=party.website or "",
        primary_address_label=_compose_address_label(
            party.primary_address_line1,
            party.primary_address_line2,
            party.primary_address_city,
            party.primary_address_state,
            party.primary_address_country,
            party.primary_address_postal_code,
        ),
        company_settings=settings,
        contacts=list_party_contacts(party.id),
        addresses=list_party_addresses(party.id),
    )


def list_party_contacts(party_id: str) -> list[ContactRow]:
    """Lista contactos activos asociados a un tercero."""
    rows = database.session.execute(
        select(PartyContact, Contact)
        .join(Contact, Contact.id == PartyContact.contact_id)
        .filter(PartyContact.party_id == party_id, Contact.is_active.is_(True))
        .order_by(Contact.first_name, Contact.last_name)
    ).all()
    return [ContactRow(link_id=link.id, contact=contact, role=link.role or "") for link, contact in rows]


def list_party_addresses(party_id: str) -> list[AddressRow]:
    """Lista direcciones activas asociadas a un tercero."""
    rows = database.session.execute(
        select(PartyAddress, Address)
        .join(Address, Address.id == PartyAddress.address_id)
        .filter(PartyAddress.party_id == party_id, Address.is_active.is_(True))
        .order_by(PartyAddress.is_primary.desc(), Address.city, Address.address_line1)
    ).all()
    return [
        AddressRow(
            link_id=link.id,
            address=address,
            address_type=link.address_type or "",
            is_primary=bool(link.is_primary),
        )
        for link, address in rows
    ]


def create_party_contact(party_id: str, values: Mapping[str, str | None]) -> Contact:
    """Crea un contacto y lo vincula al tercero."""
    contact = Contact(
        first_name=(values.get("first_name") or "").strip(),
        last_name=(values.get("last_name") or "").strip() or None,
        email=(values.get("email") or "").strip() or None,
        phone=(values.get("phone") or "").strip() or None,
        mobile=(values.get("mobile") or "").strip() or None,
        is_active=True,
    )
    if not contact.first_name:
        raise ValueError("El nombre del contacto es obligatorio.")
    database.session.add(contact)
    database.session.flush()
    database.session.add(PartyContact(party_id=party_id, contact_id=contact.id, role=(values.get("role") or "") or None))
    return contact


def update_party_contact(party_id: str, link_id: str, values: Mapping[str, str | None]) -> Contact:
    """Actualiza un contacto vinculado al tercero."""
    link = _party_contact_link(party_id, link_id)
    contact = database.session.get(Contact, link.contact_id)
    if not contact:
        raise ValueError("Contacto no encontrado.")
    first_name = (values.get("first_name") or "").strip()
    if not first_name:
        raise ValueError("El nombre del contacto es obligatorio.")
    contact.first_name = first_name
    contact.last_name = (values.get("last_name") or "").strip() or None
    contact.email = (values.get("email") or "").strip() or None
    contact.phone = (values.get("phone") or "").strip() or None
    contact.mobile = (values.get("mobile") or "").strip() or None
    link.role = (values.get("role") or "").strip() or None
    return contact


def deactivate_party_contact(party_id: str, link_id: str) -> None:
    """Desactiva un contacto vinculado al tercero."""
    link = _party_contact_link(party_id, link_id)
    contact = database.session.get(Contact, link.contact_id)
    if contact:
        contact.is_active = False


def create_party_address(party_id: str, values: Mapping[str, str | None]) -> Address:
    """Crea una direccion y la vincula al tercero."""
    address = Address(
        address_line1=(values.get("address_line1") or "").strip(),
        address_line2=(values.get("address_line2") or "").strip() or None,
        city=(values.get("city") or "").strip() or None,
        state=(values.get("state") or "").strip() or None,
        country=(values.get("country") or "").strip() or None,
        postal_code=(values.get("postal_code") or "").strip() or None,
        is_active=True,
    )
    if not address.address_line1:
        raise ValueError("La direccion es obligatoria.")
    database.session.add(address)
    database.session.flush()
    database.session.add(
        PartyAddress(
            party_id=party_id,
            address_id=address.id,
            address_type=(values.get("address_type") or "").strip() or None,
            is_primary=values.get("is_primary") is not None,
        )
    )
    return address


def update_party_address(party_id: str, link_id: str, values: Mapping[str, str | None]) -> Address:
    """Actualiza una direccion vinculada al tercero."""
    link = _party_address_link(party_id, link_id)
    address = database.session.get(Address, link.address_id)
    if not address:
        raise ValueError("Direccion no encontrada.")
    line1 = (values.get("address_line1") or "").strip()
    if not line1:
        raise ValueError("La direccion es obligatoria.")
    address.address_line1 = line1
    address.address_line2 = (values.get("address_line2") or "").strip() or None
    address.city = (values.get("city") or "").strip() or None
    address.state = (values.get("state") or "").strip() or None
    address.country = (values.get("country") or "").strip() or None
    address.postal_code = (values.get("postal_code") or "").strip() or None
    link.address_type = (values.get("address_type") or "").strip() or None
    link.is_primary = values.get("is_primary") is not None
    return address


def deactivate_party_address(party_id: str, link_id: str) -> None:
    """Desactiva una direccion vinculada al tercero."""
    link = _party_address_link(party_id, link_id)
    address = database.session.get(Address, link.address_id)
    if address:
        address.is_active = False


def party_account_labels(party_id: str, company: str) -> tuple[str, str]:
    """Devuelve las etiquetas de cuentas AR/AP configuradas para un tercero."""
    record = database.session.execute(select(PartyAccount).filter_by(party_id=party_id, company=company)).scalar_one_or_none()
    if not record:
        return "", ""
    receivable = database.session.get(Accounts, record.receivable_account_id) if record.receivable_account_id else None
    payable = database.session.get(Accounts, record.payable_account_id) if record.payable_account_id else None
    return account_label(receivable), account_label(payable)


def _party_contact_link(party_id: str, link_id: str) -> PartyContact:
    link = database.session.get(PartyContact, link_id)
    if not link or link.party_id != party_id:
        raise ValueError("Contacto no encontrado.")
    return link


def _party_address_link(party_id: str, link_id: str) -> PartyAddress:
    link = database.session.get(PartyAddress, link_id)
    if not link or link.party_id != party_id:
        raise ValueError("Direccion no encontrada.")
    return link


def generate_party_code(party_id: str, company: str | None, role: str) -> str:
    """Genera un codigo unico para un tercero via naming series."""
    from datetime import date as date_func

    today = date_func.today()
    code = generate_identifier(
        entity_type=role,
        entity_id=party_id,
        posting_date=today,
        company=company or None,
    )
    return code


def build_party_code(party_id: str, company: str | None, role: str) -> str:
    """Obtiene o genera el codigo para un tercero."""
    return generate_party_code(party_id, company, role)
