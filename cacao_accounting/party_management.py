"""Servicios compartidos para maestros de terceros."""

from __future__ import annotations

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
from cacao_accounting.party_settings import PartyCompanySettings, build_party_company_settings

PARTY_TYPE_LABELS = {"customer": "Cliente", "supplier": "Proveedor"}


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
    company_settings: list[PartyCompanySettings]
    contacts: list[ContactRow]
    addresses: list[AddressRow]


def party_group_label(group_id: str | None) -> str:
    """Devuelve el nombre de un grupo de tercero."""
    if not group_id:
        return ""
    group = database.session.get(PartyGroup, group_id)
    return group.name if group else ""


def validate_party_group(group_id: str | None, party_type: str) -> PartyGroup | None:
    """Valida que el grupo exista, este activo y corresponda al tipo de tercero."""
    if not group_id:
        return None
    group = database.session.get(PartyGroup, group_id)
    if not group:
        raise ValueError("El tipo seleccionado no existe.")
    if group.group_type != party_type:
        raise ValueError("El tipo seleccionado no corresponde al tercero.")
    if not group.is_active:
        raise ValueError("El tipo seleccionado no esta activo.")
    return group


def apply_party_group(party: Party, group_id: str | None) -> None:
    """Asigna el grupo y sincroniza la clasificacion legacy."""
    group = validate_party_group(group_id, party.party_type)
    party.party_group_id = group.id if group else None
    party.classification = group.name if group else None


def build_party_detail_context(party: Party) -> PartyDetailContext:
    """Construye el contexto completo del detalle de cliente/proveedor."""
    company_rows = (
        database.session.execute(select(CompanyParty).filter_by(party_id=party.id).order_by(CompanyParty.company))
        .scalars()
        .all()
    )
    settings = [build_party_company_settings(party.party_type, row.company, party_id=party.id) for row in company_rows]
    return PartyDetailContext(
        group_label=party_group_label(party.party_group_id) or party.classification or "",
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
