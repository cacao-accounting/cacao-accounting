# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Adaptador para importación de clientes."""

from typing import List, Dict, Any
from ulid import ULID
from cacao_accounting.imports.adapters.base import BaseImportAdapter
from cacao_accounting.database import Party, database, CompanyParty
from cacao_accounting.party_identity import find_party_by_tax_id, normalize_tax_id
from cacao_accounting.party_management import find_party_group_by_name, normalize_person_type


class CustomerAdapter(BaseImportAdapter):
    """Adaptador para Clientes."""

    columns = ["nombre", "nombre_comercial", "identificacion_fiscal", "clasificacion", "grupo"]
    required_columns = ["nombre"]

    def validate_row(self, row_data: Dict[str, Any]) -> List[str]:
        """Rechaza una identificación fiscal ya registrada (#1051)."""
        errors = super().validate_row(row_data)
        tax_id = row_data.get("identificacion_fiscal")
        if normalize_tax_id(tax_id) and find_party_by_tax_id(tax_id) is not None:
            errors.append(f"La identificación fiscal {tax_id} ya está registrada para otro tercero.")
        group_name = str(row_data.get("grupo") or "").strip()
        if group_name and find_party_group_by_name(group_name, "customer") is None:
            errors.append(f"El grupo '{group_name}' no existe, no está activo o no corresponde al tercero.")
        person_type = normalize_person_type(row_data.get("clasificacion"))
        if person_type and person_type not in ("natural", "juridical"):
            errors.append(f"La clasificación '{row_data.get('clasificacion')}' debe ser natural o juridical.")
        return errors

    def build_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any]) -> Any:
        """Build a dictionary with customer and company info."""
        row = document_data[0]
        group_name = str(row.get("grupo") or "").strip()
        group = find_party_group_by_name(group_name, "customer") if group_name else None
        if group_name and group is None:
            raise ValueError(f"El grupo '{group_name}' no existe, no está activo o no corresponde al tercero.")
        person_type = normalize_person_type(row.get("clasificacion"))
        if person_type and person_type not in ("natural", "juridical"):
            raise ValueError(f"La clasificación '{row.get('clasificacion')}' debe ser natural o juridical.")
        cliente = Party(
            code=str(ULID()),
            is_customer=True,
            name=row.get("nombre"),
            comercial_name=row.get("nombre_comercial"),
            tax_id=row.get("identificacion_fiscal"),
            party_group_id=group.id if group else None,
            person_type=person_type,
            is_active=True,
        )
        return {"party": cliente, "company_id": context.get("company_id")}

    def persist_document(self, document: Any) -> None:
        """Save the customer and its relationship with the company."""
        cliente = document["party"]
        company_id = document["company_id"]
        if find_party_by_tax_id(cliente.tax_id) is not None:
            raise ValueError(f"La identificación fiscal {cliente.tax_id} ya está registrada para otro tercero.")
        database.session.add(cliente)
        database.session.flush()
        from cacao_accounting.party_management import generate_party_code

        cliente.code = generate_party_code(cliente.id, company_id, "customer")

        if company_id:
            cp = CompanyParty(company=company_id, party_id=cliente.id, is_active=True)
            database.session.add(cp)
