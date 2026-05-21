# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Adaptador para importación de proveedores."""

from typing import List, Dict, Any
from cacao_accounting.imports.adapters.base import BaseImportAdapter
from cacao_accounting.database import Party, database, CompanyParty


class VendorAdapter(BaseImportAdapter):
    """Adaptador para Proveedores."""

    columns = ["nombre", "nombre_comercial", "identificacion_fiscal", "clasificacion", "grupo"]
    required_columns = ["nombre"]

    def build_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any]) -> Any:
        """Construye un objeto Party de tipo proveedor."""
        row = document_data[0]
        proveedor = Party(
            party_type="supplier",
            name=row.get("nombre"),
            comercial_name=row.get("nombre_comercial"),
            tax_id=row.get("identificacion_fiscal"),
            classification=row.get("clasificacion"),
            is_active=True,
        )
        return {"party": proveedor, "company_id": context.get("company_id")}

    def persist_document(self, document: Any) -> None:
        """Guarda el proveedor y lo vincula a la compañía."""
        proveedor = document["party"]
        company_id = document["company_id"]
        database.session.add(proveedor)
        database.session.flush()

        if company_id:
            cp = CompanyParty(company=company_id, party_id=proveedor.id, is_active=True)
            database.session.add(cp)
