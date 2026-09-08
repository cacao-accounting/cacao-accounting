# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Servicio para la importación masiva de tasas de cambio desde hojas de cálculo."""

import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

from sqlalchemy.exc import IntegrityError

from cacao_accounting.database import Currency, ExchangeRate, database


from cacao_accounting.i18n import _


class ExchangeRateImportError(Exception):
    """Errores de importación de tasas de cambio."""


_EXPECTED_HEADERS = {"Moneda Base", "Moneda Destino", "Fecha", "Tipo de Cambio"}
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%d-%m-%Y",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
    "%d/%m/%Y",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%m/%d/%Y",
    "%m/%d/%Y %H:%M:%S",
)


class ExchangeRateImportService:
    """Importa tasas de cambio en lote desde archivos CSV, XLSX, XLS u ODS."""

    def parse_file(self, filename: str, file_content: bytes) -> List[Dict[str, str]]:
        """Parsea un archivo según su extensión."""
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
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
                raise ExchangeRateImportError(_("Formato de archivo no soportado. Use CSV, XLSX, XLS u ODS."))

    def import_rates(self, filename: str, file_content: bytes) -> Dict[str, Any]:
        """Valida e importa tasas de cambio desde un archivo.

        Devuelve un resumen con inserted, skipped y errors.
        """
        rows = self.parse_file(filename, file_content)
        if not rows:
            raise ExchangeRateImportError(_("El archivo está vacío o no contiene datos."))

        self._validate_headers(rows[0])
        active_currencies = self._load_active_currencies()

        inserted = 0
        skipped = 0
        errors: List[str] = []

        for i, row in enumerate(rows, start=2):
            row_errors: List[str] = []
            origin, dest, rate_date, rate = self._validate_row(i, row, active_currencies, row_errors)

            if row_errors:
                errors.append(f"Fila {i}: {' | '.join(row_errors)}")
                continue

            existing = database.session.query(ExchangeRate).filter_by(origin=origin, destination=dest, date=rate_date).first()
            if existing:
                skipped += 1
                continue

            database.session.add(ExchangeRate(origin=origin, destination=dest, rate=rate, date=rate_date))
            try:
                database.session.flush()
                inserted += 1
            except IntegrityError:
                database.session.rollback()
                skipped += 1

        if errors and inserted == 0:
            database.session.rollback()
            raise ExchangeRateImportError("No se insertó ninguna tasa. Errores:\n" + "\n".join(errors))

        database.session.commit()
        return {"inserted": inserted, "skipped": skipped, "errors": errors}

    def _validate_headers(self, first_row: Dict[str, str]) -> None:
        """Valida que las columnas esperadas estén presentes."""
        headers = set(first_row.keys())
        missing = _EXPECTED_HEADERS - headers
        if missing:
            raise ExchangeRateImportError(f"Columnas faltantes: {', '.join(sorted(missing))}.")

    def _load_active_currencies(self) -> set:
        """Carga los códigos de monedas activas."""
        return {c[0].code for c in database.session.execute(database.select(Currency).filter(Currency.active.is_(True))).all()}

    def _validate_row(
        self, row_idx: int, row: Dict[str, Any], active_currencies: set, errors: List[str]
    ) -> tuple[str | None, str | None, Any, Any]:
        """Valida una fila y devuelve (origin, dest, date, rate) o None en cada posición si hay error."""
        origin = str(row.get("Moneda Base", "")).strip().upper()
        dest = str(row.get("Moneda Destino", "")).strip().upper()
        raw_date = str(row.get("Fecha", "")).strip()
        raw_rate = str(row.get("Tipo de Cambio", "")).strip()

        if not origin:
            errors.append("Moneda Base vacía.")
        elif origin not in active_currencies:
            errors.append(f"Moneda Base '{origin}' no existe o no está activa.")

        if not dest:
            errors.append("Moneda Destino vacía.")
        elif dest not in active_currencies:
            errors.append(f"Moneda Destino '{dest}' no existe o no está activa.")

        if origin and dest and origin == dest:
            errors.append("Moneda Base y Destino deben ser diferentes.")

        rate_date = None
        if not raw_date:
            errors.append("Fecha vacía.")
        else:
            rate_date = self._parse_date(raw_date)
            if rate_date is None:
                errors.append(f"Fecha '{raw_date}' no válida. Use formato DD-MM-YYYY.")

        rate = None
        if not raw_rate:
            errors.append("Tipo de Cambio vacío.")
        else:
            try:
                rate = Decimal(raw_rate)
                if rate <= 0:
                    errors.append("Tipo de Cambio debe ser mayor a cero.")
            except InvalidOperation:
                errors.append(f"Tipo de Cambio '{raw_rate}' no es numérico.")

        if errors:
            return None, None, None, None
        return origin, dest, rate_date, rate

    @staticmethod
    def _parse_date(raw: str) -> Any:
        """Intenta parsear una fecha con varios formatos conocidos.

        Maneja strings y objetos date/datetime (openpyxl puede devolver
        celdas de fecha como objetos datetime directamente).
        """
        if isinstance(raw, datetime):
            return raw.date()
        if isinstance(raw, date):
            return raw
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        return None

    def _parse_csv(self, file_content: bytes) -> List[Dict[str, str]]:
        """Parsea un archivo CSV."""
        text = io.StringIO(file_content.decode("utf-8-sig"))
        reader = csv.DictReader(text)
        return [row for row in reader if self._row_has_content(row)]

    def _parse_xlsx(self, file_content: bytes) -> List[Dict[str, str]]:
        """Parsea un archivo XLSX."""
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(file_content), data_only=True)
        ws = wb.active
        return self._matrix_to_dicts(ws.values)

    def _parse_xls(self, file_content: bytes) -> List[Dict[str, str]]:
        """Parsea un archivo XLS."""
        import xlrd

        wb = xlrd.open_workbook(file_contents=file_content)
        ws = wb.sheet_by_index(0)
        values = [ws.row_values(rx) for rx in range(ws.nrows)]
        return self._matrix_to_dicts(values)

    def _parse_ods(self, file_content: bytes) -> List[Dict[str, str]]:
        """Parsea un archivo ODS."""
        from odf.opendocument import load
        from odf.table import Table, TableRow, TableCell
        from odf.teletype import extractText

        doc = load(io.BytesIO(file_content))
        tables = doc.getElementsByType(Table)
        if not tables:
            return []
        rows = []
        for row in tables[0].getElementsByType(TableRow):
            row_values: list[str] = []
            for cell in row.getElementsByType(TableCell):
                repeat_attr = cell.getAttributeNS("urn:oasis:names:tc:opendocument:xmlns:table:1.0", "number-columns-repeated")
                if not repeat_attr:
                    repeat_attr = cell.getAttribute("numbercolumnsrepeated")
                try:
                    repeat = int(repeat_attr) if repeat_attr else 1
                except (ValueError, TypeError):
                    repeat = 1
                text = extractText(cell)
                row_values.extend([text] * repeat)
            rows.append(row_values)
        return self._matrix_to_dicts(rows)

    def _matrix_to_dicts(self, values_iter) -> List[Dict[str, Any]]:
        """Convierte una matriz (primera fila = encabezados) a lista de diccionarios.

        Preserva objetos date/datetime para que el parser de fechas los maneje
        directamente en lugar de convertirlos a string.
        """
        rows = list(values_iter)
        if not rows:
            return []
        headers = [str(h).strip() if h is not None else "" for h in rows[0]]
        result = []
        for row in rows[1:]:
            if not self._row_has_content_raw(row):
                continue
            row_dict: Dict[str, Any] = {}
            for i, header in enumerate(headers):
                val = row[i] if i < len(row) and row[i] is not None else ""
                if isinstance(val, (date, datetime)):
                    row_dict[header] = val
                else:
                    row_dict[header] = str(val).strip()
            result.append(row_dict)
        return result

    @staticmethod
    def _row_has_content(row: Dict[str, Any]) -> bool:
        return any(str(v).strip() != "" for v in row.values())

    @staticmethod
    def _row_has_content_raw(row: list) -> bool:
        return any(cell is not None and str(cell).strip() != "" for cell in row)
