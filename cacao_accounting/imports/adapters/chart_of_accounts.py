# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Adaptador para importación de catálogo de cuentas."""

from typing import List, Dict, Any
from cacao_accounting.imports.adapters.base import BaseImportAdapter
from cacao_accounting.database import Accounts, database


class ChartOfAccountsAdapter(BaseImportAdapter):
    """Adaptador para Catálogo de Cuentas."""

    columns = ["codigo", "nombre", "padre", "grupo", "moneda", "clasificacion", "tipo"]
    required_columns = ["codigo", "nombre", "clasificacion"]

    def build_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any]) -> Any:
        """Build an Accounts object from the data."""
        # Una cuenta por fila
        row = document_data[0]
        cuenta = Accounts(
            entity=context.get("company_id"),
            code=row.get("codigo"),
            name=row.get("nombre"),
            parent=row.get("padre"),
            group=str(row.get("grupo")).lower() in ("true", "1", "si", "yes"),
            currency=row.get("moneda"),
            classification=row.get("clasificacion"),
            account_type=row.get("tipo"),
            active=True,
            enabled=True,
        )
        return cuenta

    def persist_document(self, document: Any) -> None:
        """Save the account to the database."""
        database.session.add(document)
