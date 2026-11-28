# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Adaptador para importación de catálogo de cuentas."""

from graphlib import TopologicalSorter
from typing import List, Dict, Any
from cacao_accounting.imports.adapters.base import BaseImportAdapter
from cacao_accounting.database import Accounts, Currency, database
from cacao_accounting.default_scope import lock_default_scope
from cacao_accounting.contabilidad.services import _validate_account_parent
from cacao_accounting.i18n import _


class ChartOfAccountsAdapter(BaseImportAdapter):
    """Adaptador para Catálogo de Cuentas."""

    columns = ["codigo", "nombre", "padre", "grupo", "moneda", "clasificacion", "tipo"]
    required_columns = ["codigo", "nombre", "clasificacion"]

    def validate_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any] | None = None) -> List[str]:
        """Validate account domains and an existing account parent."""
        errors = self._validate_domains(document_data)
        errors.extend(self._validate_currencies(document_data))
        if not document_data:
            return errors
        row = document_data[0]
        parent_code = _normalized_parent(row.get("padre"))
        if parent_code is None:
            return errors

        company_id = (context or {}).get("company_id")
        parent = database.session.execute(
            database.select(Accounts).filter_by(entity=company_id, code=parent_code)
        ).scalar_one_or_none()
        if parent is None:
            # A parent may be another row in this file; the batch validator
            # resolves it after seeing the complete catalog.
            return errors
        if not parent.active or not parent.enabled:
            errors.append(_("La cuenta padre debe estar activa."))
        elif not parent.group:
            errors.append(_("La cuenta padre debe ser una cuenta de grupo."))
        return errors

    @staticmethod
    def _validate_currencies(document_data: List[Dict[str, Any]]) -> List[str]:
        """Reject missing or inactive currencies while allowing an empty cell."""
        errors: List[str] = []
        for row in document_data:
            code = _normalized_currency(row.get("moneda"))
            if code is None:
                continue
            currency = database.session.execute(database.select(Currency).filter_by(code=code)).scalar_one_or_none()
            if currency is None or not currency.active:
                errors.append(_("La moneda no existe o está inactiva."))
        return errors

    @staticmethod
    def _validate_domains(document_data: List[Dict[str, Any]]) -> List[str]:
        """Reject classifications and account types outside the catalog domain."""
        from cacao_accounting.contabilidad.forms import ACCOUNT_TYPE_CHOICES
        from cacao_accounting.reportes.services import account_classification_is_known

        allowed_types = {value for value, _label in ACCOUNT_TYPE_CHOICES if value}
        errors: List[str] = []
        for row in document_data:
            classification = str(row.get("clasificacion") or "").strip()
            if classification and not account_classification_is_known(classification):
                errors.append(_("Clasificación no permitida para cuentas contables."))
            account_type = str(row.get("tipo") or "").strip().lower()
            if account_type and account_type not in allowed_types:
                errors.append(_("Tipo de cuenta no permitido para cuentas contables."))
        return errors

    def validate_batch_documents(self, documents: Dict[str, List[Dict[str, Any]]], context: Dict[str, Any]) -> List[str]:
        """Validate parent references and cycles across the complete imported catalog."""
        rows = [row for document_rows in documents.values() for row in document_rows]
        company_id = context.get("company_id")
        rows_by_code: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            code = _normalized_parent(row.get("codigo"))
            if code:
                rows_by_code.setdefault(code, []).append(row)

        errors = self._validate_batch_parents(rows, rows_by_code, company_id)
        errors.extend(self._validate_batch_parent_cycles(rows, rows_by_code, company_id))
        return errors

    @staticmethod
    def _validate_batch_parents(
        rows: List[Dict[str, Any]], rows_by_code: Dict[str, List[Dict[str, Any]]], company_id: str | None
    ) -> List[str]:
        """Resolve imported parent codes and reject missing or ambiguous references."""
        errors: List[str] = []
        for row in rows:
            parent_code = _normalized_parent(row.get("padre"))
            if parent_code is None:
                continue
            imported_parents = rows_by_code.get(parent_code, [])
            if len(imported_parents) > 1:
                errors.append(_("El código de cuenta padre aparece varias veces en el archivo."))
                continue
            if imported_parents:
                if not _is_group_account(imported_parents[0].get("grupo")):
                    errors.append(_("La cuenta padre debe ser una cuenta de grupo."))
                continue
            existing_parent = database.session.execute(
                database.select(Accounts).filter_by(entity=company_id, code=parent_code)
            ).scalar_one_or_none()
            if existing_parent is None:
                errors.append(_("La cuenta padre indicada no existe para la entidad seleccionada."))
        return errors

    @staticmethod
    def _validate_batch_parent_cycles(
        rows: List[Dict[str, Any]], rows_by_code: Dict[str, List[Dict[str, Any]]], company_id: str | None
    ) -> List[str]:
        """Reject cycles that connect imported accounts to existing hierarchy rows."""
        parent_by_code = {
            code: _normalized_parent(rows_for_code[0].get("padre"))
            for code, rows_for_code in rows_by_code.items()
            if len(rows_for_code) == 1
        }
        visited: set[str] = set()
        errors: List[str] = []
        for row in rows:
            code = _normalized_parent(row.get("codigo"))
            if code is None or code in visited:
                continue
            cycle = _find_parent_cycle(code, parent_by_code, company_id, visited)
            if cycle:
                errors.append(_("La cuenta padre seleccionada genera un ciclo jerarquico."))
        return errors

    def build_document(self, document_data: List[Dict[str, Any]], context: Dict[str, Any]) -> Any:
        """Build an Accounts object from the data."""
        from cacao_accounting.reportes.services import normalize_account_classification_value

        # Una cuenta por fila
        row = document_data[0]
        cuenta = Accounts(
            entity=context.get("company_id"),
            code=_normalized_parent(row.get("codigo")),
            name=row.get("nombre"),
            parent=_normalized_parent(row.get("padre")),
            group=_is_group_account(row.get("grupo")),
            currency=_normalized_currency(row.get("moneda")),
            classification=normalize_account_classification_value(str(row.get("clasificacion") or "")),
            account_type=(str(row.get("tipo") or "").strip().lower() or None),
            active=True,
            enabled=True,
        )
        return cuenta

    def persist_document(self, document: Any) -> None:
        """Serialize hierarchy writes and revalidate the parent at persistence time."""
        lock_default_scope("account_hierarchy", document.entity)
        errors = self._validate_currencies([{"moneda": document.currency}])
        if errors:
            raise ValueError(errors[0])
        document.parent = _validate_account_parent(
            document.entity, document.parent, current_code=document.code, for_update=True
        )
        database.session.add(document)

    def order_documents(self, documents: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        """Persist imported parents first, even if the file lists children first."""
        codes = {_normalized_parent(rows[0].get("codigo")): ref for ref, rows in documents.items()}
        dependencies = {}
        for ref, rows in documents.items():
            parent_ref = codes.get(_normalized_parent(rows[0].get("padre")))
            dependencies[ref] = (parent_ref,) if parent_ref is not None else ()
        return {ref: documents[ref] for ref in TopologicalSorter(dependencies).static_order()}


def _normalized_parent(value: Any) -> str | None:
    """Normalize an optional parent code so blank cells represent a root account."""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalized_currency(value: Any) -> str | None:
    """Normalize the optional currency cell so blank values mean no currency."""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _is_group_account(value: Any) -> bool:
    """Interpret supported spreadsheet boolean values for the group flag."""
    return str(value or "").strip().lower() in ("true", "1", "si", "sí", "yes")


def _find_parent_cycle(
    start: str,
    parent_by_code: Dict[str, str | None],
    company_id: str | None,
    visited: set[str],
) -> set[str]:
    """Return cycle members reached by following imported and persisted parent links."""
    path: list[str] = []
    positions: Dict[str, int] = {}
    current: str | None = start
    while current is not None and current not in visited:
        if current in positions:
            visited.update(path)
            return set(path[positions[current] :])
        positions[current] = len(path)
        path.append(current)
        if current in parent_by_code:
            current = parent_by_code[current]
        else:
            current = _persisted_parent_code(current, company_id)
    visited.update(path)
    return set()


def _persisted_parent_code(code: str, company_id: str | None) -> str | None:
    """Load one persisted parent link from the same account catalog."""
    parent_code = database.session.execute(
        database.select(Accounts.parent).filter_by(entity=company_id, code=code)
    ).scalar_one_or_none()
    return _normalized_parent(parent_code)
