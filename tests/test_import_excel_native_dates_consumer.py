# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1201/#1291: fechas nativas de Excel llegan normalizadas al consumidor.

Los lectores entregan el mismo día para XLS y XLSX; el flujo real de
importación valida y ejecuta un comprobante con celdas de fecha nativas.
"""

from datetime import date, datetime
from uuid import uuid4

import openpyxl
import xlrd
from xlrd.xldate import xldate_from_date_tuple
from sqlalchemy import select

from cacao_accounting.database import ComprobanteContable, User, database
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.readers import xls_reader
from cacao_accounting.imports.readers.xlsx_reader import XLSXReader
from cacao_accounting.imports.services.import_service import ImportService

ENCABEZADOS = ["document_ref", "fecha", "cuenta", "debito", "credito", "moneda", "tipo_cambio"]
FECHA = date(2026, 5, 15)


def _escribir_xlsx(ruta, referencia: str) -> None:
    """Escribe un XLSX real con celdas de fecha nativas en la columna fecha."""
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.append(ENCABEZADOS)
    worksheet.append([referencia, datetime(2026, 5, 15), "1101", "100", "0", "NIO", "1"])
    worksheet.append([referencia, datetime(2026, 5, 15), "4101", "0", "100", "NIO", "1"])
    for row in worksheet.iter_rows(min_row=2, min_col=2, max_col=2):
        for cell in row:
            cell.number_format = "yyyy-mm-dd"
    workbook.save(ruta)
    workbook.close()


class _LibroXlsFalso:
    """Libro XLS mínimo que expone una fecha nativa con el datemode indicado."""

    def __init__(self, datemode: int):
        self.datemode = datemode

    def sheet_by_index(self, _index: int):
        return _HojaXlsFalsa(self.datemode)

    def release_resources(self) -> None:
        pass


class _HojaXlsFalsa:
    """Hoja de dos columnas con la fecha serializada en el sistema del libro."""

    nrows = 2
    ncols = 2

    def __init__(self, datemode: int):
        self._filas = [
            ("fecha", "monto"),
            (xldate_from_date_tuple((2026, 5, 15), datemode), 100),
        ]

    def cell_value(self, row: int, col: int):
        return self._filas[row][col]

    def cell_type(self, row: int, col: int) -> int:
        if row == 0:
            return xlrd.XL_CELL_TEXT
        return xlrd.XL_CELL_DATE if col == 0 else xlrd.XL_CELL_NUMBER


def _crear_lote(app, ruta) -> str:
    """Crea el lote XLSX pendiente con libro y actor del escenario."""
    with app.app_context():
        actor = database.session.execute(select(User.id).filter_by(user="admin")).scalar_one()
        lote = ImportBatch(
            company_id="cacao",
            record_type="journal_entry",
            source_format="xlsx",
            source_filename=ruta.name,
            source_path=str(ruta),
            import_status=1,
            accounting_book_id="DEFAULT_BOOK",
            created_by=actor,
        )
        database.session.add(lote)
        database.session.commit()
        return lote.id


def test_xls_y_xlsx_entregan_la_misma_fecha(tmp_path, monkeypatch):
    """El mismo día se normaliza igual desde ambos lectores y sistemas Excel."""
    ruta_xlsx = tmp_path / "fecha.xlsx"
    _escribir_xlsx(ruta_xlsx, "XC-1201")
    xlsx = XLSXReader().read(str(ruta_xlsx))
    assert xlsx.rows[0][1] == "2026-05-15"

    ruta_xls = tmp_path / "fecha.xls"
    ruta_xls.write_bytes(b"biff-simulado")
    for datemode in (0, 1):
        monkeypatch.setattr(xls_reader, "_preflight_legacy_xls", lambda _path: True)
        monkeypatch.setattr(xls_reader.xlrd, "open_workbook", lambda *_a, _m=datemode, **_k: _LibroXlsFalso(_m))
        xls = xls_reader.XLSReader().read(str(ruta_xls))
        assert xls.rows[0][0] == "2026-05-15"


def test_importacion_xlsx_con_fecha_nativa_valida_y_ejecuta(entorno_contable_aislado, tmp_path):
    """Una fecha nativa XLSX no se rechaza y llega al comprobante ejecutado."""
    app = entorno_contable_aislado.app
    referencia = f"AS-1201-{uuid4().hex[:8]}"
    ruta = tmp_path / f"{referencia}.xlsx"
    _escribir_xlsx(ruta, referencia)
    lote_id = _crear_lote(app, ruta)

    with app.app_context():
        servicio = ImportService()
        assert servicio.validate(lote_id) is True
        lote = database.session.get(ImportBatch, lote_id)
        assert lote.import_status == 3
        errores = database.session.execute(select(ImportBatchError).filter_by(batch_id=lote_id)).scalars().all()
        assert not any("fecha" in (error.message or "").lower() for error in errores)

        assert servicio.execute(lote_id) is True
        database.session.expire_all()
        lote = database.session.get(ImportBatch, lote_id)
        assert lote.import_status == 5
        comprobante = database.session.execute(
            select(ComprobanteContable).where(ComprobanteContable.reference == referencia)
        ).scalar_one()
        assert comprobante.date == FECHA
