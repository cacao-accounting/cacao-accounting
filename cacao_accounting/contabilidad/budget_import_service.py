# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicio para la importación de presupuestos desde hojas de cálculo."""

import csv
import io
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

from cacao_accounting.database import (
    AccountingPeriod,
    Accounts,
    Budget,
    BudgetLine,
    BudgetImport,
    BudgetImportLine,
    CostCenter,
    Project,
    Unit,
    database,
)
from cacao_accounting.contabilidad.budget_service import BudgetError

_LABEL_CENTRO_COSTO = "Centro de Costo"
_LABEL_UNIDAD_NEGOCIO = "Unidad de Negocio"
_LABEL_DESCRIPCION = "Descripción"


class BudgetImportService:
    """Servicio para manejar la importación de líneas de presupuesto."""

    def get_template_columns(self, budget_id: str) -> List[Dict[str, Any]]:
        """Define las columnas esperadas para la plantilla de importación."""
        budget = database.session.get(Budget, budget_id)
        if not budget:
            raise BudgetError("Presupuesto no encontrado.")

        columns = [
            {"name": "Cuenta", "required": True, "type": "string"},
            {"name": _LABEL_CENTRO_COSTO, "required": True, "type": "string"},
            {"name": _LABEL_UNIDAD_NEGOCIO, "required": False, "type": "string"},
            {"name": "Proyecto", "required": False, "type": "string"},
            {"name": _LABEL_DESCRIPCION, "required": False, "type": "string"},
        ]

        # Agregar una columna por cada período del año fiscal
        periods = (
            database.session.query(AccountingPeriod)
            .filter_by(fiscal_year_id=budget.fiscal_year_id)
            .order_by(AccountingPeriod.start)
            .all()
        )
        for p in periods:
            columns.append({"name": p.name, "required": False, "type": "decimal"})

        columns.append({"name": "Total", "required": False, "type": "decimal"})
        return columns

    def parse_file(self, filename: str, file_content: bytes) -> List[Dict[str, str]]:
        """Parsea un archivo según su extensión (CSV, XLSX, XLS, ODS)."""
        extension = filename.split(".")[-1].lower() if "." in filename else ""
        match extension:
            case "csv":
                return self._parse_csv(file_content)
            case "xlsx":
                return self._parse_xlsx(file_content)
            case "xls":
                return self._parse_xls(file_content)
            case "ods":
                return self._parse_ods(file_content)
            case _:
                raise BudgetError("Formato de archivo no soportado.")

    def _parse_csv(self, file_content: bytes) -> List[Dict[str, str]]:
        """Parsea un archivo CSV."""
        text_stream = io.StringIO(file_content.decode("utf-8"))
        reader = csv.DictReader(text_stream)
        return [row for row in reader]

    def _parse_xlsx(self, file_content: bytes) -> List[Dict[str, str]]:
        """Parsea un archivo XLSX usando openpyxl."""
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(file_content), data_only=True)
        ws = wb.active
        return self._matrix_to_dicts(ws.values)

    def _parse_xls(self, file_content: bytes) -> List[Dict[str, str]]:
        """Parsea un archivo XLS usando xlrd."""
        import xlrd

        wb = xlrd.open_workbook(file_contents=file_content)
        ws = wb.sheet_by_index(0)
        values = []
        for rx in range(ws.nrows):
            values.append(ws.row_values(rx))
        return self._matrix_to_dicts(values)

    def _parse_ods(self, file_content: bytes) -> List[Dict[str, str]]:
        """Parsea un archivo ODS usando odfpy con soporte para columnas repetidas."""
        from odf.opendocument import load
        from odf.table import Table, TableRow, TableCell
        from odf.teletype import extractText

        doc = load(io.BytesIO(file_content))
        tables = doc.getElementsByType(Table)
        if not tables:
            return []
        rows = self._ods_rows(tables[0], TableRow, TableCell, extractText)
        return self._matrix_to_dicts(rows)

    def _matrix_to_dicts(self, values_iter) -> List[Dict[str, str]]:
        """Convierte una matriz de valores (primera fila encabezados) a lista de diccionarios."""
        rows = list(values_iter)
        if not rows:
            return []
        headers = self._normalize_headers(rows[0])
        return [self._row_to_dict(headers, row) for row in rows[1:] if self._row_has_content(row)]

    def _validate_row_periods(
        self,
        row: dict,
        i: int,
        account_id: str | None,
        cc_id: str | None,
        unit_id: str | None,
        project_id: str | None,
        period_map: dict,
        period_names: set,
        existing_lines: set,
        row_combs_to_add: list,
    ) -> tuple[list, Decimal, list]:
        """Procesa los valores por periodo de una fila del presupuesto."""
        row_lines_to_add = []
        row_total = Decimal("0")
        row_errors: list[str] = []

        for p_name in period_names:
            row_line, row_total_delta, row_error, comb = self._build_period_row_entry(
                row,
                i,
                p_name,
                account_id,
                cc_id,
                unit_id,
                project_id,
                period_map,
                existing_lines,
                row_combs_to_add,
            )
            if row_error:
                row_errors.append(row_error)
                continue
            if row_line:
                row_lines_to_add.append(row_line)
                row_combs_to_add.append(comb)
                row_total += row_total_delta

        return row_lines_to_add, row_total, row_errors

    def _build_period_row_entry(
        self,
        row: dict,
        row_index: int,
        period_name: str,
        account_id: str | None,
        cc_id: str | None,
        unit_id: str | None,
        project_id: str | None,
        period_map: dict,
        existing_lines: set,
        row_combs_to_add: list,
    ) -> tuple[dict[str, Any] | None, Decimal, str | None, tuple[str | None, str | None, str | None, str | None, str | None]]:
        amount, amount_error = self._parse_period_amount(row, period_name)
        if amount_error:
            return None, Decimal("0"), amount_error, (None, None, None, None, None)
        if amount is None:
            return None, Decimal("0"), None, (None, None, None, None, None)
        period_id = period_map[period_name]
        comb = (account_id, cc_id, period_id, unit_id or "", project_id or "")
        if comb in existing_lines or comb in row_combs_to_add:
            return None, Decimal("0"), f"Duplicado para {period_name}.", comb
        return (
            {
                "row_index": row_index,
                "account_id": account_id,
                "cost_center_id": cc_id,
                "period_id": period_id,
                "business_unit_id": unit_id,
                "project_id": project_id,
                "amount": amount,
                "description": row.get(_LABEL_DESCRIPCION),
            },
            amount,
            None,
            comb,
        )

    def _ods_rows(self, table, table_row_class, table_cell_class, extract_text) -> list[list[str]]:
        rows = []
        for row in table.getElementsByType(table_row_class):
            rows.append(self._ods_row_values(row, table_cell_class, extract_text))
        return rows

    def _ods_row_values(self, row, table_cell_class, extract_text) -> list[str]:
        row_values: list[str] = []
        for cell in row.getElementsByType(table_cell_class):
            repeat = self._ods_cell_repeat(cell)
            row_values.extend([extract_text(cell)] * repeat)
        return row_values

    def _ods_cell_repeat(self, cell) -> int:
        repeat = cell.getAttributeNS("urn:oasis:names:tc:opendocument:xmlns:table:1.0", "number-columns-repeated")
        if not repeat:
            repeat = cell.getAttribute("numbercolumnsrepeated")
        try:
            return int(repeat) if repeat else 1
        except (ValueError, TypeError):
            return 1

    def _normalize_headers(self, headers_row) -> list[str]:
        return [str(header).strip() if header is not None else "" for header in headers_row]

    def _row_has_content(self, row: list[Any]) -> bool:
        return any(cell is not None and str(cell).strip() != "" for cell in row)

    def _row_to_dict(self, headers: list[str], row: list[Any]) -> Dict[str, str]:
        row_dict: Dict[str, str] = {}
        for i, header in enumerate(headers):
            row_dict[header] = self._cell_value(row, i)
        return row_dict

    def _cell_value(self, row: list[Any], index: int) -> str:
        if index < len(row):
            val = row[index]
            return str(val).strip() if val is not None else ""
        return ""

    def validate_import(self, budget_id: str, filename: str, file_content: bytes, user_id: str) -> BudgetImport:
        """Valida e inicializa un lote de importación en staging."""
        rows = self.parse_file(filename, file_content)
        budget = database.session.get(Budget, budget_id)
        if not budget:
            raise BudgetError("Presupuesto no encontrado.")
        if budget.status != "draft":
            raise BudgetError("Solo se pueden importar líneas a presupuestos en borrador.")

        import_batch = self._create_import_batch(budget_id, filename, len(rows), user_id)
        caches = self._build_caches(budget)
        self._validate_headers(rows, caches["period_names"])

        existing_lines = self._get_existing_line_combos(budget_id)
        errors, validated_lines_count = self._process_import_rows(rows, import_batch.id, caches, existing_lines)

        if errors:
            import_batch.status = "failed"
            import_batch.errors_count = len(errors)
            database.session.commit()
            raise BudgetError("\n".join(errors))

        import_batch.status = "validated"
        import_batch.rows_inserted = validated_lines_count
        database.session.commit()
        return import_batch

    def _create_import_batch(self, budget_id: str, filename: str, rows_count: int, user_id: str) -> BudgetImport:
        """Create and flush the import batch record."""
        batch = BudgetImport(
            budget_id=budget_id,
            filename=filename,
            status="failed",
            rows_read=rows_count,
            created_by=user_id,
        )
        database.session.add(batch)
        database.session.flush()
        return batch

    def _build_caches(self, budget: Budget) -> Dict[str, Any]:
        """Build lookup maps for accounts, cost centers, units, projects, and periods."""
        accounts_map = {
            a.code: a.id for a in database.session.query(Accounts).filter_by(entity=budget.company, group=False).all()
        }
        cc_map = {c.code: c.id for c in database.session.query(CostCenter).filter_by(entity=budget.company).all()}
        unit_map = {u.code: u.id for u in database.session.query(Unit).filter_by(entity=budget.company).all()}
        project_map = {p.code: p.id for p in database.session.query(Project).filter_by(entity=budget.company).all()}
        periods = database.session.query(AccountingPeriod).filter_by(fiscal_year_id=budget.fiscal_year_id).all()
        period_map = {p.name: p.id for p in periods}
        period_names = set(period_map.keys())

        return {
            "accounts_map": accounts_map,
            "cc_map": cc_map,
            "unit_map": unit_map,
            "project_map": project_map,
            "period_map": period_map,
            "period_names": period_names,
        }

    def _validate_headers(self, rows: List[Dict[str, Any]], period_names: set) -> None:
        """Validate that all column headers are recognized."""
        if not rows:
            return
        allowed_headers = {
            "Cuenta",
            _LABEL_CENTRO_COSTO,
            _LABEL_UNIDAD_NEGOCIO,
            "Proyecto",
            _LABEL_DESCRIPCION,
            "Total",
        } | period_names
        first_row_headers = set(rows[0].keys())
        for header in first_row_headers:
            if header and header not in allowed_headers:
                raise BudgetError(f"Columna desconocida detectada: '{header}'.")

    def _get_existing_line_combos(self, budget_id: str) -> set:
        """Get existing budget line combinations to detect duplicates."""
        return {
            (bl.account_id, bl.cost_center_id, bl.period_id, bl.business_unit_id or "", bl.project_id or "")
            for bl in database.session.query(BudgetLine).filter_by(budget_id=budget_id).all()
        }

    def _process_import_rows(
        self, rows: List[Dict[str, Any]], import_id: str, caches: Any, existing_lines: set
    ) -> tuple[List[str], int]:
        """Process all import rows and return errors and validated count."""
        errors = []
        validated_lines_count = 0
        for i, row in enumerate(rows, start=2):
            row_errors, row_combs_to_add, row_lines_to_add = self._validate_single_row(i, row, caches, existing_lines)
            if row_errors:
                errors.append(f"Fila {i}: " + " | ".join(row_errors))
            else:
                existing_lines.update(row_combs_to_add)
                for line_data in row_lines_to_add:
                    database.session.add(BudgetImportLine(import_id=import_id, **line_data))
                    validated_lines_count += 1
        return errors, validated_lines_count

    def _validate_single_row(
        self, row_idx: int, row: Dict[str, Any], caches: Any, existing_lines: set
    ) -> tuple[List[str], list, list]:
        """Validate a single import row and return errors, combinations, and lines."""
        row_errors: list[str] = []
        account_id = self._resolve_required_lookup(
            caches["accounts_map"], row.get("Cuenta"), "Cuenta", row_errors
        )
        cc_id = self._resolve_required_lookup(
            caches["cc_map"], row.get(_LABEL_CENTRO_COSTO), _LABEL_CENTRO_COSTO, row_errors
        )
        unit_id = self._resolve_optional_lookup(
            caches["unit_map"], row.get(_LABEL_UNIDAD_NEGOCIO), "Unidad de Negocio", row_errors
        )
        project_id = self._resolve_optional_lookup(caches["project_map"], row.get("Proyecto"), "Proyecto", row_errors)

        row_combs_to_add: List[Any] = []
        row_lines_to_add, row_total, period_errors = self._validate_row_periods(
            row,
            row_idx,
            account_id,
            cc_id,
            unit_id,
            project_id,
            caches["period_map"],
            caches["period_names"],
            existing_lines,
            row_combs_to_add,
        )
        row_errors.extend(period_errors)

        total_error = self._validate_total_value(row.get("Total", ""), row_total)
        if total_error:
            row_errors.append(total_error)

        return row_errors, row_combs_to_add, row_lines_to_add

    def get_staged_lines(self, import_id: str, limit: int = 100) -> list[BudgetImportLine]:
        """Obtiene líneas en staging para previsualización de importación."""
        query = (
            database.session.query(BudgetImportLine)
            .filter_by(import_id=import_id)
            .order_by(BudgetImportLine.row_index.asc(), BudgetImportLine.created.asc())
        )
        if limit > 0:
            query = query.limit(limit)
        return query.all()

    def insert_lines(self, import_id: str, user_id: str):
        """Transfiere líneas de staging a BudgetLine atómicamente."""
        batch = database.session.get(BudgetImport, import_id)
        if not batch or batch.status != "validated":
            raise BudgetError("Lote de importación no válido o ya procesado.")

        try:
            staging_lines = self.get_staged_lines(import_id=import_id, limit=0)
            for sl in staging_lines:
                line = BudgetLine(
                    budget_id=batch.budget_id,
                    account_id=sl.account_id,
                    cost_center_id=sl.cost_center_id,
                    business_unit_id=sl.business_unit_id,
                    project_id=sl.project_id,
                    period_id=sl.period_id,
                    amount=sl.amount,
                    description=sl.description,
                    created_by=user_id,
                )
                database.session.add(line)

            batch.status = "imported"
            # Limpiar staging
            database.session.query(BudgetImportLine).filter_by(import_id=import_id).delete()
            database.session.commit()
        except Exception as e:
            database.session.rollback()
            failed_batch = database.session.get(BudgetImport, import_id)
            if failed_batch:
                failed_batch.status = "failed"
            database.session.commit()
            raise BudgetError(f"Error atómico en inserción: {str(e)}")

    def _parse_period_amount(self, row: dict, period_name: str) -> tuple[Decimal | None, str | None]:
        raw_value = row.get(period_name, "").strip()
        if not raw_value:
            return None, None
        try:
            amount = Decimal(raw_value)
        except InvalidOperation:
            return None, f"Monto '{raw_value}' no numérico en {period_name}."
        if amount == 0:
            return None, None
        return amount, None

    def _resolve_required_lookup(
        self, lookup_map: dict[str, str], key: Any, label: str, row_errors: list[str]
    ) -> str | None:
        resolved = lookup_map.get(key)
        if not resolved:
            row_errors.append(f"{label} '{key}' no válida.")
        return resolved

    def _resolve_optional_lookup(
        self, lookup_map: dict[str, str], key: Any, label: str, row_errors: list[str]
    ) -> str | None:
        if not key:
            return None
        resolved = lookup_map.get(key)
        if not resolved:
            row_errors.append(f"{label} '{key}' no válida.")
        return resolved

    def _validate_total_value(self, total_value: Any, row_total: Decimal) -> str | None:
        total_val = str(total_value or "").strip()
        if not total_val:
            return None
        try:
            if abs(Decimal(total_val) - row_total) > Decimal("0.01"):
                return f"Total {total_val} no coincide con suma {row_total}."
        except InvalidOperation:
            return f"Total '{total_val}' no numérico."
        return None
