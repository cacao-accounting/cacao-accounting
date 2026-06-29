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
        ws = tables[0]
        rows = []
        for row in ws.getElementsByType(TableRow):
            row_values = []
            for cell in row.getElementsByType(TableCell):
                # ODS uses number-columns-repeated attribute to compact identical cells
                repeat = cell.getAttributeNS("urn:oasis:names:tc:opendocument:xmlns:table:1.0", "number-columns-repeated")
                if not repeat:
                    repeat = cell.getAttribute("numbercolumnsrepeated")

                try:
                    count = int(repeat) if repeat else 1
                except (ValueError, TypeError):
                    count = 1

                txt = extractText(cell)
                for _ in range(count):
                    row_values.append(txt)
            rows.append(row_values)
        return self._matrix_to_dicts(rows)

    def _matrix_to_dicts(self, values_iter) -> List[Dict[str, str]]:
        """Convierte una matriz de valores (primera fila encabezados) a lista de diccionarios."""
        rows = list(values_iter)
        if not rows:
            return []
        headers = [str(h).strip() if h is not None else "" for h in rows[0]]
        result = []
        for row in rows[1:]:
            if not any(c is not None and str(c).strip() != "" for c in row):
                continue
            row_dict = {}
            for i, header in enumerate(headers):
                if i < len(row):
                    val = row[i]
                    row_dict[header] = str(val).strip() if val is not None else ""
                else:
                    row_dict[header] = ""
            result.append(row_dict)
        return result

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
        row_errors = []

        for p_name in period_names:
            val = row.get(p_name, "").strip()
            if not val:
                continue
            try:
                amount = Decimal(val)
            except InvalidOperation:
                row_errors.append(f"Monto '{val}' no numérico en {p_name}.")
                continue
            if amount == 0:
                continue
            p_id = period_map[p_name]
            comb = (account_id, cc_id, p_id, unit_id or "", project_id or "")
            if comb in existing_lines or comb in row_combs_to_add:
                row_errors.append(f"Duplicado para {p_name}.")
            else:
                row_lines_to_add.append(
                    {
                        "row_index": i,
                        "account_id": account_id,
                        "cost_center_id": cc_id,
                        "period_id": p_id,
                        "business_unit_id": unit_id,
                        "project_id": project_id,
                        "amount": amount,
                        "description": row.get(_LABEL_DESCRIPCION),
                    }
                )
                row_combs_to_add.append(comb)
                row_total += amount

        return row_lines_to_add, row_total, row_errors

    def validate_import(self, budget_id: str, filename: str, file_content: bytes, user_id: str) -> BudgetImport:
        """Valida e inicializa un lote de importación en staging."""
        rows = self.parse_file(filename, file_content)
        budget = database.session.get(Budget, budget_id)
        if not budget:
            raise BudgetError("Presupuesto no encontrado.")

        if budget.status != "draft":
            raise BudgetError("Solo se pueden importar líneas a presupuestos en borrador.")

        import_batch = BudgetImport(
            budget_id=budget_id,
            filename=filename,
            status="failed",
            rows_read=len(rows),
            created_by=user_id,
        )
        database.session.add(import_batch)
        database.session.flush()

        errors = []
        validated_lines_count = 0

        # Cachés
        accounts_map = {
            a.code: a.id for a in database.session.query(Accounts).filter_by(entity=budget.company, group=False).all()
        }
        cc_map = {c.code: c.id for c in database.session.query(CostCenter).filter_by(entity=budget.company).all()}
        unit_map = {u.code: u.id for u in database.session.query(Unit).filter_by(entity=budget.company).all()}
        project_map = {p.code: p.id for p in database.session.query(Project).filter_by(entity=budget.company).all()}
        periods = database.session.query(AccountingPeriod).filter_by(fiscal_year_id=budget.fiscal_year_id).all()
        period_map = {p.name: p.id for p in periods}
        period_names = set(period_map.keys())

        # Validar columnas desconocidas
        allowed_headers = {
            "Cuenta",
            _LABEL_CENTRO_COSTO,
            _LABEL_UNIDAD_NEGOCIO,
            "Proyecto",
            _LABEL_DESCRIPCION,
            "Total",
        } | period_names
        if rows:
            first_row_headers = set(rows[0].keys())
            for header in first_row_headers:
                if header and header not in allowed_headers:
                    raise BudgetError(f"Columna desconocida detectada: '{header}'.")

        existing_lines = set()
        for bl in database.session.query(BudgetLine).filter_by(budget_id=budget_id).all():
            existing_lines.add((bl.account_id, bl.cost_center_id, bl.period_id, bl.business_unit_id or "", bl.project_id or ""))

        for i, row in enumerate(rows, start=2):
            row_errors = []
            account_id = accounts_map.get(row.get("Cuenta"))
            if not account_id:
                row_errors.append(f"Cuenta '{row.get('Cuenta')}' no válida.")

            cc_id = cc_map.get(row.get(_LABEL_CENTRO_COSTO))
            if not cc_id:
                row_errors.append(f"Centro de Costo '{row.get('Centro de Costo')}' no válido.")

            unit_id = unit_map.get(row.get(_LABEL_UNIDAD_NEGOCIO)) if row.get(_LABEL_UNIDAD_NEGOCIO) else None
            if row.get(_LABEL_UNIDAD_NEGOCIO) and not unit_id:
                row_errors.append(f"Unidad de Negocio '{row.get('Unidad de Negocio')}' no válida.")

            project_id = project_map.get(row.get("Proyecto")) if row.get("Proyecto") else None
            if row.get("Proyecto") and not project_id:
                row_errors.append(f"Proyecto '{row.get('Proyecto')}' no válido.")

            row_combs_to_add: List[Any] = []
            row_lines_to_add, row_total, period_errors = self._validate_row_periods(
                row, i, account_id, cc_id, unit_id, project_id, period_map, period_names, existing_lines, row_combs_to_add,
            )
            row_errors.extend(period_errors)

            total_val = row.get("Total", "").strip()
            if total_val:
                try:
                    if abs(Decimal(total_val) - row_total) > Decimal("0.01"):
                        row_errors.append(f"Total {total_val} no coincide con suma {row_total}.")
                except InvalidOperation:
                    row_errors.append(f"Total '{total_val}' no numérico.")

            if row_errors:
                errors.append(f"Fila {i}: " + " | ".join(row_errors))
            else:
                for comb in row_combs_to_add:
                    existing_lines.add(comb)
                for line_data in row_lines_to_add:
                    database.session.add(BudgetImportLine(import_id=import_batch.id, **line_data))
                    validated_lines_count += 1

        if errors:
            import_batch.status = "failed"
            import_batch.errors_count = len(errors)
            database.session.commit()
            raise BudgetError("\n".join(errors))

        import_batch.status = "validated"
        import_batch.rows_inserted = validated_lines_count
        database.session.commit()
        return import_batch

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
