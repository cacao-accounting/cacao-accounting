# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Adaptador para importación de clientes."""

from typing import List, Dict, Any
from ulid import ULID
from cacao_accounting.imports.adapters.base import BaseImportAdapter
from cacao_accounting.database import Party, database, CompanyParty
from cacao_accounting.party_identity import find_party_by_tax_id, normalize_tax_id
from cacao_accounting.i18n import _
from cacao_accounting.party_management import find_party_group_by_name


class CustomerAdapter(BaseImportAdapter):
    """Adaptador para Clientes."""

    columns = ["nombre", "nombre_comercial", "identificacion_fiscal", "clasificacion", "grupo"]
    required_columns = ["nombre"]

    def validate_row(self, row_data: Dict[str, Any]) -> List[str]:
        """Rechaza una identificación fiscal ya registrada (#1051)."""
        errors = super().validate_row(row_data)
        tax_id = row_data.get("identificacion_fiscal")
        if normalize_tax_id(tax_id) and find_party_by_tax_id(tax_id) is not None:
            errors.append(
                _("La identificación fiscal %(tax_id)s ya está registrada para otro tercero.") % {"tax_id": tax_id}
            )
        group_name = str(row_data.get("grupo") or "").strip()
        if group_name and find_party_group_by_name(group_name, "customer") is None:
            errors.append(
                _('El grupo "%(grupo)s" no existe, no está activo o no corresponde al tercero.') % {"grupo": group_name}
            )
        clasificacion = str(row_data.get("clasificacion") or "").strip()
        if clasificacion and clasificacion not in ("natural", "juridical"):
            errors.append(
                _('La clasificación "%(clasificacion)s" debe ser natural o juridical.')
                % {"clasificacion": row_data.get("clasificacion")}
            )
        return errors

    def build_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any]) -> Any:
        """Build a dictionary with customer and company info."""
        row = document_data[0]
        group_name = str(row.get("grupo") or "").strip()
        group = find_party_group_by_name(group_name, "customer") if group_name else None
        if group_name and group is None:
            raise ValueError(
                _('El grupo "%(grupo)s" no existe, no está activo o no corresponde al tercero.') % {"grupo": group_name}
            )
        clasificacion = str(row.get("clasificacion") or "").strip()
        if clasificacion and clasificacion not in ("natural", "juridical"):
            raise ValueError(
                _('La clasificación "%(clasificacion)s" debe ser natural o juridical.')
                % {"clasificacion": row.get("clasificacion")}
            )
        cliente = Party(
            code=str(ULID()),
            is_customer=True,
            name=row.get("nombre"),
            comercial_name=row.get("nombre_comercial"),
            tax_id=row.get("identificacion_fiscal"),
            party_group_id=group.id if group else None,
            person_type=clasificacion or None,
            is_active=True,
        )
        return {"party": cliente, "company_id": context.get("company_id")}

    def persist_document(self, document: Any) -> None:
        """Save the customer and its relationship with the company."""
        cliente = document["party"]
        company_id = document["company_id"]
        if find_party_by_tax_id(cliente.tax_id) is not None:
            raise ValueError(
                _("La identificación fiscal %(tax_id)s ya está registrada para otro tercero.")
                % {"tax_id": cliente.tax_id}
            )
        database.session.add(cliente)
        database.session.flush()
        from cacao_accounting.party_management import generate_party_code

        cliente.code = generate_party_code(cliente.id, company_id, "customer")

        if company_id:
            cp = CompanyParty(company=company_id, party_id=cliente.id, is_active=True)
            database.session.add(cp)
