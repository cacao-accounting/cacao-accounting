# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Los lectores aplican límites antes de expandir archivos tabulares."""

import csv
import struct
from io import StringIO
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

import openpyxl
import pytest
from odf.opendocument import OpenDocumentSpreadsheet
from odf.table import Table, TableCell, TableRow
from odf.text import P, S

from cacao_accounting.imports.readers import limits
from cacao_accounting.imports.readers import ods_reader
from cacao_accounting.imports.readers import xls_reader
from cacao_accounting.imports.readers.csv_reader import CSVReader
from cacao_accounting.imports.readers.csv_reader import _validate_shape
from cacao_accounting.imports.readers.ods_reader import ODSReader
from cacao_accounting.imports.readers.limits import ImportReadLimitError, ReadBudget, validate_archive_size
from cacao_accounting.imports.readers.xls_reader import XLSReader
from cacao_accounting.imports.readers.xlsx_reader import XLSXReader
from cacao_accounting.database import database
from cacao_accounting.imports.models import ImportBatch, ImportBatchError
from cacao_accounting.imports.services.import_service import ImportService


def _write_ods(path, header, cells, row_repeat="1"):
    """Escribe un ODS con atributos de repetición controlados por el test."""
    document = OpenDocumentSpreadsheet()
    sheet = Table(name="Import")
    header_row = TableRow()
    for value in header:
        cell = TableCell()
        if value:
            cell.addElement(P(text=value))
        header_row.addElement(cell)
    sheet.addElement(header_row)

    data_row = TableRow(numberrowsrepeated=row_repeat)
    for value, repeated in cells:
        cell = TableCell(numbercolumnsrepeated=str(repeated))
        if value:
            cell.addElement(P(text=value))
        data_row.addElement(cell)
    sheet.addElement(data_row)
    document.spreadsheet.addElement(sheet)
    document.save(str(path))


def test_read_budget_rejects_rows_columns_and_cells(monkeypatch):
    """La cuenta común impide superar cualquiera de sus tres dimensiones."""
    monkeypatch.setattr(limits, "MAX_IMPORT_ROWS", 1)
    monkeypatch.setattr(limits, "MAX_IMPORT_COLUMNS", 2)
    monkeypatch.setattr(limits, "MAX_IMPORT_CELLS", 3)

    budget = ReadBudget()
    budget.consume_header(2)
    budget.consume_row(1)
    with pytest.raises(ImportReadLimitError):
        budget.consume_row(1)

    with pytest.raises(ImportReadLimitError):
        ReadBudget().consume_header(3)

    budget = ReadBudget()
    budget.consume_header(2)
    with pytest.raises(ImportReadLimitError):
        budget.consume_row(2)


def test_csv_reader_stops_when_data_rows_exceed_limit(tmp_path, monkeypatch):
    """CSV no acumula todas las filas antes de verificar su máximo."""
    path = tmp_path / "rows.csv"
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["name"])
        writer.writerow(["Ana"])
        writer.writerow(["Luis"])
    monkeypatch.setattr(limits, "MAX_IMPORT_ROWS", 1)

    with pytest.raises(ImportReadLimitError):
        CSVReader().read(str(path))


def test_csv_reader_rejects_oversized_file_before_reading(tmp_path, monkeypatch):
    """El límite de archivo también se aplica al lector directo."""
    path = tmp_path / "oversized.csv"
    path.write_text("name\nAna\n", encoding="utf-8")
    monkeypatch.setattr(limits, "MAX_IMPORT_FILE_BYTES", 1)

    with pytest.raises(ImportReadLimitError):
        CSVReader().read(str(path))


def test_csv_reader_classifies_parser_field_limit_as_resource_limit(tmp_path):
    """Un campo sobre el límite interno del parser produce un error controlado."""
    path = tmp_path / "large_field.csv"
    path.write_text("value\n" + "x" * (csv.field_size_limit() + 1), encoding="utf-8")

    with pytest.raises(ImportReadLimitError):
        CSVReader().read(str(path))


def test_csv_reader_reads_valid_and_empty_files(tmp_path):
    """El límite conserva la lectura normal y el contrato de CSV vacío."""
    empty_path = tmp_path / "empty.csv"
    empty_path.write_bytes(b"")
    assert CSVReader().read(str(empty_path)).rows == []

    path = tmp_path / "valid.csv"
    path.write_text("name\nAna\n", encoding="utf-8")
    result = CSVReader().read(str(path))
    assert result.columns == ["name"]
    assert result.rows == [["Ana"]]


def test_csv_shape_preflight_counts_delimiters_outside_quoted_fields(monkeypatch):
    """El preflight limita columnas sin contar separadores dentro de comillas."""
    monkeypatch.setattr(limits, "MAX_IMPORT_COLUMNS", 2)
    _validate_shape(StringIO('name,detail\nAna,"north,east"\n'), csv.get_dialect("excel"))

    with pytest.raises(ImportReadLimitError):
        _validate_shape(StringIO("a,b,c\n"), csv.get_dialect("excel"))


def test_xlsx_reader_checks_dimensions_before_streaming_rows(tmp_path, monkeypatch):
    """XLSX rechaza una hoja grande antes de materializar sus filas."""
    path = tmp_path / "large.xlsx"
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.append(["name"])
    worksheet.append(["Ana"])
    worksheet.append(["Luis"])
    workbook.save(path)
    monkeypatch.setattr(limits, "MAX_IMPORT_ROWS", 1)

    with pytest.raises(ImportReadLimitError):
        XLSXReader().read(str(path))


def test_xlsx_reader_checks_uncompressed_archive_size_before_openpyxl(tmp_path, monkeypatch):
    """Un ZIP comprimido que desborda su tamaño XML se rechaza previamente."""
    path = tmp_path / "archive.xlsx"
    workbook = openpyxl.Workbook()
    workbook.active.append(["name", "Ana"])
    workbook.save(path)
    monkeypatch.setattr(limits, "MAX_IMPORT_ARCHIVE_BYTES", 1)

    with pytest.raises(ImportReadLimitError):
        XLSXReader().read(str(path))


def test_archive_preflight_measures_actual_deflate_output(tmp_path, monkeypatch):
    """El límite ZIP no confía en un tamaño descomprimido central subdeclarado."""
    path = tmp_path / "understated.zip"
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("payload.xml", b"x" * 200)
    corrupted = bytearray(path.read_bytes())
    central_directory = corrupted.find(b"PK\x01\x02")
    struct.pack_into("<I", corrupted, central_directory + 24, 1)
    path.write_bytes(corrupted)
    monkeypatch.setattr(limits, "MAX_IMPORT_ARCHIVE_BYTES", 300)

    with pytest.raises(ImportReadLimitError):
        validate_archive_size(str(path))

    monkeypatch.setattr(limits, "MAX_IMPORT_ARCHIVE_BYTES", 100)
    with pytest.raises(ImportReadLimitError):
        validate_archive_size(str(path))


def test_archive_preflight_counts_stored_members_toward_shared_budget(tmp_path, monkeypatch):
    """El límite descomprimido se aplica al total de varios miembros almacenados."""
    path = tmp_path / "stored_members.zip"
    with ZipFile(path, "w", ZIP_STORED) as archive:
        archive.writestr("first.xml", b"a" * 8)
        archive.writestr("second.xml", b"b" * 8)
    monkeypatch.setattr(limits, "MAX_IMPORT_ARCHIVE_BYTES", 10)

    with pytest.raises(ImportReadLimitError):
        validate_archive_size(str(path))


def test_archive_preflight_rejects_missing_end_directory_record(tmp_path):
    """Un contenedor sin el registro final ZIP no se interpreta como vacío."""
    path = tmp_path / "missing_eocd.zip"
    path.write_bytes(b"not a zip archive")

    with pytest.raises(ImportReadLimitError):
        validate_archive_size(str(path))


def test_archive_preflight_rejects_invalid_central_directory_header(tmp_path):
    """Cada entrada central debe tener una cabecera válida antes de abrirla."""
    path = tmp_path / "invalid_central.zip"
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("payload.xml", b"data")
    corrupted = bytearray(path.read_bytes())
    central_directory = corrupted.find(b"PK\x01\x02")
    corrupted[central_directory : central_directory + 4] = b"BAD!"
    path.write_bytes(corrupted)

    with pytest.raises(ImportReadLimitError):
        validate_archive_size(str(path))


def test_archive_preflight_rejects_unsupported_compression(tmp_path):
    """Solo métodos de compresión con medición acotada se aceptan en hojas."""
    path = tmp_path / "unsupported_method.zip"
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("payload.xml", b"data")
    corrupted = bytearray(path.read_bytes())
    local_header = corrupted.find(b"PK\x03\x04")
    central_directory = corrupted.find(b"PK\x01\x02")
    struct.pack_into("<H", corrupted, local_header + 8, 99)
    struct.pack_into("<H", corrupted, central_directory + 10, 99)
    path.write_bytes(corrupted)

    with pytest.raises(ImportReadLimitError):
        validate_archive_size(str(path))


def test_xlsx_reader_streams_valid_rows_and_closes_workbook(tmp_path):
    """XLSX devuelve una tabla válida desde el lector en modo read-only."""
    path = tmp_path / "valid.xlsx"
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.append(["name", "group"])
    worksheet.append(["Ana", "A"])
    workbook.save(path)

    result = XLSXReader().read(str(path))

    assert result.columns == ["name", "group"]
    assert result.rows == [["Ana", "A"]]


def test_xlsx_reader_ignores_understated_worksheet_dimension(tmp_path):
    """La dimensión declarada no oculta celdas existentes en el XML de hoja."""
    path = tmp_path / "understated.xlsx"
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.append(["name", "group"])
    worksheet.append(["Ana", "A"])
    workbook.save(path)

    rewritten = tmp_path / "rewritten.xlsx"
    with ZipFile(path) as source, ZipFile(rewritten, "w", ZIP_DEFLATED) as target:
        for entry in source.infolist():
            content = source.read(entry.filename)
            if entry.filename == "xl/worksheets/sheet1.xml":
                content = content.replace(b'ref="A1:B2"', b'ref="A1"')
            target.writestr(entry, content)

    result = XLSXReader().read(str(rewritten))
    assert result.columns == ["name", "group"]
    assert result.rows == [["Ana", "A"]]


def test_xlsx_reader_returns_empty_workbook_and_closes_it(tmp_path):
    """XLSX mantiene el resultado vacío cuando no existe una fila de encabezado."""
    path = tmp_path / "empty.xlsx"
    openpyxl.Workbook().save(path)

    result = XLSXReader().read(str(path))

    assert result.columns == []
    assert result.rows == []


def test_xls_reader_checks_sheet_dimensions_before_copying_rows(tmp_path, monkeypatch):
    """XLS limita dimensiones antes de consultar valores de sus celdas."""
    path = tmp_path / "large.xls"
    path.write_bytes(b"xls")

    class Sheet:
        """Hoja mínima con dimensión excedida y lectura prohibida."""

        nrows = 3
        ncols = 1

        def cell_value(self, row, column):
            """Falla si el lector intenta copiar celdas antes del límite."""
            raise AssertionError("No se deben leer celdas fuera del límite")

    class Workbook:
        """Libro mínimo que expone una hoja y libera recursos."""

        released = False

        def sheet_by_index(self, index):
            """Devuelve la hoja de prueba."""
            return Sheet()

        def release_resources(self):
            """Registra la liberación del libro incluso si se rechaza."""
            self.released = True

    workbook = Workbook()
    monkeypatch.setattr(xls_reader.xlrd, "open_workbook", lambda file_path, on_demand: workbook)
    monkeypatch.setattr(xls_reader, "_validate_sheet_extent", lambda ignored_workbook: None)
    monkeypatch.setattr(xls_reader, "MAX_IMPORT_ROWS", 1)

    with pytest.raises(ImportReadLimitError):
        XLSReader().read(str(path))

    assert workbook.released


def test_xls_biff_preflight_rejects_large_coordinates_before_sheet_load(monkeypatch):
    """El escaneo BIFF detecta filas fuera de límite antes de xlrd.sheet_by_index."""
    number_record = struct.pack("<HHHHHd", 0x0203, 14, 2, 0, 0, 1.0)
    eof_record = struct.pack("<HH", 0x000A, 0)

    class Workbook:
        """Exposición mínima del flujo BIFF del primer libro."""

        mem = number_record + eof_record
        base = 0
        stream_len = len(mem)
        _sh_abs_posn = [0]

    monkeypatch.setattr(xls_reader, "MAX_IMPORT_ROWS", 1)
    with pytest.raises(ImportReadLimitError):
        xls_reader._validate_sheet_extent(Workbook())


def test_xls_biff_preflight_fails_closed_without_sheet_metadata():
    """La ausencia de datos para preflight no permite cargar una hoja sin límites."""
    with pytest.raises(ImportReadLimitError):
        xls_reader._validate_sheet_extent(object())


def test_xls_legacy_biff_preflight_runs_before_xlrd_opens_sheet(tmp_path, monkeypatch):
    """BIFF2 se limita antes de que xlrd cargue eager su única hoja."""
    path = tmp_path / "legacy.xls"
    bof = struct.pack("<HHHH", 0x0009, 4, 0x0000, 0x0010)
    integer_data = struct.pack("<HH3sH", 2, 0, b"\0\0\0", 7)
    integer = struct.pack("<HH", 0x0002, len(integer_data)) + integer_data
    eof = struct.pack("<HH", 0x000A, 0)
    path.write_bytes(bof + integer + eof)

    def forbidden_open(*args, **kwargs):
        """Asegura que el rechazo sucede antes de entrar a xlrd."""
        raise AssertionError("xlrd no debe abrir la hoja fuera de límites")

    monkeypatch.setattr(xls_reader.xlrd, "open_workbook", forbidden_open)
    monkeypatch.setattr(xls_reader, "MAX_IMPORT_ROWS", 1)

    with pytest.raises(ImportReadLimitError):
        XLSReader().read(str(path))


def test_xls_biff4w_preflight_checks_eager_sheet_substreams(tmp_path, monkeypatch):
    """BIFF4W valida substreams durante el preflight previo a xlrd."""
    path = tmp_path / "legacy_4w.xls"
    global_bof = struct.pack("<HHHH", 0x0409, 4, 0x0400, 0x0100)
    sheet_bof = struct.pack("<HHHH", 0x0409, 4, 0x0400, 0x0010)
    integer_data = struct.pack("<HH3sH", 2, 0, b"\0\0\0", 7)
    integer = struct.pack("<HH", 0x0002, len(integer_data)) + integer_data
    eof = struct.pack("<HH", 0x000A, 0)
    sheet_stream = sheet_bof + integer + eof
    sheet_header_data = struct.pack("<i", len(sheet_stream)) + b"\x01S"
    sheet_header = struct.pack("<HH", 0x008F, len(sheet_header_data)) + sheet_header_data
    global_record = struct.pack("<HH", 0x0001, 0)
    path.write_bytes(global_bof + global_record + sheet_header + sheet_stream + eof)
    monkeypatch.setattr(xls_reader, "MAX_IMPORT_ROWS", 1)

    with pytest.raises(ImportReadLimitError):
        XLSReader().read(str(path))


def test_xls_biff4w_preflight_limits_rows_across_eager_sheets(monkeypatch):
    """Hojas BIFF4W eager comparten el presupuesto de filas del libro."""
    sheet_bof = struct.pack("<HHHH", 0x0409, 4, 0x0400, 0x0010)
    integer_data = struct.pack("<HH3sH", 1, 0, b"\0\0\0", 7)
    integer = struct.pack("<HH", 0x0002, len(integer_data)) + integer_data
    eof = struct.pack("<HH", 0x000A, 0)
    sheet_stream = sheet_bof + integer + eof
    sheet_header_data = struct.pack("<i", len(sheet_stream)) + b"\x01S"
    sheet_header = struct.pack("<HH", 0x008F, len(sheet_header_data)) + sheet_header_data
    stream = sheet_header + sheet_stream + sheet_header + sheet_stream + eof
    monkeypatch.setattr(xls_reader, "MAX_IMPORT_ROWS", 1)

    with pytest.raises(ImportReadLimitError):
        xls_reader._preflight_biff4w(stream, 0, len(stream))


def test_xls_biff4w_preflight_limits_header_only_sheets(monkeypatch):
    """Hojas eager vacías o con encabezado cuentan para el límite de hojas."""
    sheet_bof = struct.pack("<HHHH", 0x0409, 4, 0x0400, 0x0010)
    integer_data = struct.pack("<HH3sH", 0, 0, b"\0\0\0", 7)
    integer = struct.pack("<HH", 0x0002, len(integer_data)) + integer_data
    eof = struct.pack("<HH", 0x000A, 0)
    sheet_stream = sheet_bof + integer + eof
    sheet_header_data = struct.pack("<i", len(sheet_stream)) + b"\x01S"
    sheet_header = struct.pack("<HH", 0x008F, len(sheet_header_data)) + sheet_header_data
    stream = sheet_header + sheet_stream + sheet_header + sheet_stream + eof
    monkeypatch.setattr(xls_reader, "MAX_IMPORT_SHEETS", 1)

    with pytest.raises(ImportReadLimitError):
        xls_reader._preflight_biff4w(stream, 0, len(stream))


def test_xls_legacy_preflight_skips_modern_biff(tmp_path):
    """Los formatos modernos se revisan después de la carga diferida de xlrd."""
    path = tmp_path / "modern.xls"
    path.write_bytes(struct.pack("<HHHH", 0x0809, 4, 0x0600, 0x0005))

    xls_reader._preflight_legacy_xls(str(path))


def test_xls_workbook_stream_uses_ole_workbook_entry(monkeypatch):
    """El preflight localiza el stream Workbook dentro de un OLE compuesto."""

    class CompoundDocument:
        """Documento OLE mínimo con un stream Workbook."""

        def __init__(self, source, logfile):
            pass

        def locate_named_stream(self, name):
            if name == "Workbook":
                return b"stream", 10, 6
            return None, 0, 0

    monkeypatch.setattr(xls_reader.compdoc, "CompDoc", CompoundDocument)
    assert xls_reader._workbook_stream(xls_reader.compdoc.SIGNATURE + b"data") == (b"stream", 10, 6)


def test_xls_workbook_stream_reports_missing_ole_entry(monkeypatch):
    """Un contenedor OLE sin Workbook ni Book se rechaza como archivo inválido."""

    class CompoundDocument:
        """Documento OLE mínimo sin streams de libro."""

        def __init__(self, source, logfile):
            pass

        def locate_named_stream(self, name):
            return None, 0, 0

    monkeypatch.setattr(xls_reader.compdoc, "CompDoc", CompoundDocument)
    with pytest.raises(xls_reader.xlrd.XLRDError):
        xls_reader._workbook_stream(xls_reader.compdoc.SIGNATURE + b"data")


def test_xls_preflight_rejects_truncated_biff_stream():
    """Un BIFF que termina antes del EOF no llega a xlrd sin validar."""
    with pytest.raises(ImportReadLimitError):
        xls_reader._scan_biff_extent(b"\x09\x08", 0, 2)


@pytest.mark.parametrize(
    "record",
    [
        struct.pack("<HHHH", 0x0201, 6, 0, 20),
        struct.pack("<HHHHHH", 0x00BE, 8, 0, 0, 0, 20),
    ],
)
def test_xls_biff_preflight_limits_formatted_blank_cells(monkeypatch, record):
    """Celdas vacías formateadas también cuentan al estimar la matriz BIFF."""
    eof = struct.pack("<HH", 0x000A, 0)

    class Workbook:
        """Exposición mínima de registros BIFF con una celda vacía extrema."""

        mem = record + eof
        base = 0
        stream_len = len(mem)
        _sh_abs_posn = [0]

    monkeypatch.setattr(xls_reader, "MAX_IMPORT_COLUMNS", 10)
    with pytest.raises(ImportReadLimitError):
        xls_reader._validate_sheet_extent(Workbook())


def test_xls_biff_preflight_accounts_for_ranges_and_skips_embedded_streams(monkeypatch):
    """El preflight limita matrices densas y omite registros de gráficos embebidos."""
    bof = struct.pack("<HHHH", 0x0809, 4, 0x0600, 0x0010)
    number = struct.pack("<HHHHHd", 0x0203, 14, 1, 0, 0, 1.0)
    mulrk_data = struct.pack("<HHHIH", 2, 0, 0, 0, 0)
    mulrk = struct.pack("<HH", 0x00BD, len(mulrk_data)) + mulrk_data
    merged_data = struct.pack("<HHHHH", 1, 0, 2, 0, 2)
    merged = struct.pack("<HH", 0x00E5, len(merged_data)) + merged_data
    chart_bof = struct.pack("<HHHH", 0x0809, 4, 0x0600, 0x0020)
    huge_chart_cell = struct.pack("<HHHHHd", 0x0203, 14, 50_000, 200, 0, 1.0)
    eof = struct.pack("<HH", 0x000A, 0)
    stream = bof + number + mulrk + merged + chart_bof + huge_chart_cell + eof + number + eof

    class Workbook:
        """Exposición mínima del flujo BIFF con un substream embebido."""

        mem = stream
        base = 0
        stream_len = len(mem)
        _sh_abs_posn = [0]

    xls_reader._validate_sheet_extent(Workbook())

    monkeypatch.setattr(xls_reader, "MAX_IMPORT_CELLS", 5)
    with pytest.raises(ImportReadLimitError):
        xls_reader._validate_sheet_extent(Workbook())


def test_xls_reader_reads_rows_incrementally_and_releases_workbook(tmp_path, monkeypatch):
    """XLS copia filas dentro del límite y libera el libro cargado on-demand."""
    path = tmp_path / "valid.xls"
    path.write_bytes(b"xls")

    class Sheet:
        """Hoja de dos columnas y una fila de datos."""

        nrows = 2
        ncols = 2
        values = {(0, 0): "name", (0, 1): "group", (1, 0): "Ana", (1, 1): "A"}

        def cell_value(self, row, column):
            """Devuelve la celda solicitada."""
            return self.values[(row, column)]

    class Workbook:
        """Libro mínimo que confirma la liberación de recursos."""

        released = False

        def sheet_by_index(self, index):
            """Devuelve la hoja de prueba."""
            return Sheet()

        def release_resources(self):
            """Marca el cierre de recursos del libro."""
            self.released = True

    workbook = Workbook()

    def open_workbook(file_path, on_demand):
        """Imita la carga diferida de xlrd sin requerir un generador XLS."""
        assert on_demand
        return workbook

    monkeypatch.setattr(xls_reader.xlrd, "open_workbook", open_workbook)
    monkeypatch.setattr(xls_reader, "_validate_sheet_extent", lambda ignored_workbook: None)

    result = XLSReader().read(str(path))

    assert result.columns == ["name", "group"]
    assert result.rows == [["Ana", "A"]]
    assert workbook.released


def test_ods_rejects_repeated_cells_before_expanding_them(tmp_path, monkeypatch):
    """Una repetición ODS excesiva falla antes de crear la lista expandida."""
    path = tmp_path / "repeated_columns.ods"
    _write_ods(path, ["name"], [("Ana", 100_000)])
    monkeypatch.setattr(limits, "MAX_IMPORT_COLUMNS", 8)

    with pytest.raises(ImportReadLimitError):
        ODSReader().read(str(path))


@pytest.mark.parametrize("repeat", [0, -1])
def test_ods_rejects_nonpositive_cell_repetitions(tmp_path, repeat):
    """Repeticiones inválidas no desplazan silenciosamente las columnas siguientes."""
    path = tmp_path / f"invalid_repeat_{repeat}.ods"
    _write_ods(path, ["name", "group"], [("Ana", repeat), ("A", 1)])

    with pytest.raises(ImportReadLimitError):
        ODSReader().read(str(path))


@pytest.mark.parametrize("repeat", [0, -1])
def test_ods_rejects_nonpositive_row_repetitions(tmp_path, repeat):
    """Repeticiones de fila cero o negativas se rechazan antes de procesar la fila."""
    path = tmp_path / f"invalid_row_repeat_{repeat}.ods"
    _write_ods(path, ["name"], [("Ana", 1)], row_repeat=str(repeat))

    with pytest.raises(ImportReadLimitError):
        ODSReader().read(str(path))


def test_ods_does_not_import_whitespace_between_cells(tmp_path):
    """El texto XML posterior a una celda no contamina el valor de la siguiente."""
    path = tmp_path / "pretty_printed.ods"
    _write_ods(path, ["name", "group"], [("Ana", 1), ("A", 1)])
    rewritten = tmp_path / "whitespace.ods"
    marker = b"</table:table-cell><table:table-cell"
    with ZipFile(path) as source, ZipFile(rewritten, "w", ZIP_DEFLATED) as target:
        for entry in source.infolist():
            content = source.read(entry.filename)
            if entry.filename == "content.xml":
                assert marker in content
                content = content.replace(marker, b"</table:table-cell>   <table:table-cell")
            target.writestr(entry, content)

    result = ODSReader().read(str(rewritten))
    assert result.columns == ["name", "group"]
    assert result.rows == [["Ana", "A"]]


def test_ods_rejects_space_expansion_before_allocating_text(tmp_path, monkeypatch):
    """Los espacios ODS también consumen el presupuesto de texto expandido."""
    path = tmp_path / "repeated_spaces.ods"
    document = OpenDocumentSpreadsheet()
    sheet = Table(name="Import")
    header = TableRow()
    header_cell = TableCell()
    header_cell.addElement(P(text="name"))
    header.addElement(header_cell)
    data = TableRow()
    value_cell = TableCell()
    paragraph = P()
    paragraph.addElement(S(c="5"))
    value_cell.addElement(paragraph)
    data.addElement(value_cell)
    sheet.addElement(header)
    sheet.addElement(data)
    document.spreadsheet.addElement(sheet)
    document.save(str(path))
    monkeypatch.setattr(ods_reader, "MAX_IMPORT_TEXT_CHARS", 4)

    with pytest.raises(ImportReadLimitError):
        ODSReader().read(str(path))


def test_preview_reports_resource_limit_without_failing_detail_view(app, tmp_path):
    """La vista previa muestra el límite y conserva una respuesta renderizable."""
    with app.app_context():
        path = tmp_path / "repeated_columns.ods"
        _write_ods(path, ["name"], [("Ana", 100_000)])
        batch = ImportBatch(
            company_id="cacao",
            record_type="customer",
            source_format="ods",
            source_path=str(path),
            import_status=1,
        )
        database.session.add(batch)
        database.session.commit()

        preview = ImportService().preview(batch.id)

        assert preview["columns"] == []
        assert preview["total_documents"] == 0
        assert [(error.error_type, error.message) for error in preview["errors"]] == [
            ("RESOURCE_LIMIT", "El archivo excede los límites de recursos de importación.")
        ]

        database.session.delete(batch)
        database.session.commit()


def test_validation_records_resource_limit_separately_from_system_error(app, tmp_path, monkeypatch):
    """La validación clasifica los límites de lectura como error recuperable del archivo."""
    with app.app_context():
        path = tmp_path / "repeated_columns.ods"
        _write_ods(path, ["name"], [("Ana", 2)])
        batch = ImportBatch(
            company_id="cacao",
            record_type="customer",
            source_format="ods",
            source_path=str(path),
            import_status=1,
        )
        database.session.add(batch)
        database.session.commit()
        database.session.add(
            ImportBatchError(batch_id=batch.id, error_type="MISSING_COLUMN", field_name="name", message="Obsoleto")
        )
        database.session.commit()
        monkeypatch.setattr(limits, "MAX_IMPORT_COLUMNS", 1)

        assert ImportService().validate(batch.id)

        errors = ImportBatchError.query.filter_by(batch_id=batch.id).all()
        assert batch.import_status == 7
        assert batch.started_at is None
        assert [(error.error_type, error.message) for error in errors] == [
            ("RESOURCE_LIMIT", "El archivo excede los límites de recursos de importación.")
        ]
        preview = ImportService().preview(batch.id)
        assert [error.error_type for error in preview["errors"]] == ["RESOURCE_LIMIT"]
        ImportBatchError.query.filter_by(batch_id=batch.id).delete()
        database.session.delete(batch)
        database.session.commit()


def test_execution_records_resource_limit_separately_from_fatal_error(app, tmp_path, monkeypatch):
    """La ejecución clasifica un cambio de archivo que excede recursos."""
    with app.app_context():
        path = tmp_path / "repeated_columns.ods"
        _write_ods(path, ["name"], [("Ana", 2)])
        batch = ImportBatch(
            company_id="cacao",
            record_type="customer",
            source_format="ods",
            source_path=str(path),
            import_status=3,
        )
        database.session.add(batch)
        database.session.commit()
        monkeypatch.setattr(limits, "MAX_IMPORT_COLUMNS", 1)

        assert ImportService().execute(batch.id)

        errors = ImportBatchError.query.filter_by(batch_id=batch.id).all()
        assert batch.import_status == 7
        assert batch.started_at is None
        assert [error.error_type for error in errors] == ["RESOURCE_LIMIT"]
        ImportBatchError.query.filter_by(batch_id=batch.id).delete()
        database.session.delete(batch)
        database.session.commit()


def test_ods_rejects_repeated_rows_before_expanding_them(tmp_path, monkeypatch):
    """Una repetición de filas excedida se detecta antes de duplicar referencias."""
    path = tmp_path / "repeated_rows.ods"
    _write_ods(path, ["name"], [("Ana", 1)], row_repeat="100000")
    monkeypatch.setattr(limits, "MAX_IMPORT_ROWS", 2)

    with pytest.raises(ImportReadLimitError):
        ODSReader().read(str(path))


def test_ods_reads_typed_values_and_empty_sheet(tmp_path):
    """ODS conserva valores numéricos, fecha, booleano y hoja sin filas."""
    path = tmp_path / "typed.ods"
    document = OpenDocumentSpreadsheet()
    sheet = Table(name="Typed")
    header = TableRow()
    for name in ("amount", "date", "active", "string", "currency", "percentage", "time"):
        cell = TableCell()
        cell.addElement(P(text=name))
        header.addElement(cell)
    data = TableRow()
    for attributes in (
        {"valuetype": "float", "value": "12.5"},
        {"valuetype": "date", "datevalue": "2026-11-14"},
        {"valuetype": "boolean", "booleanvalue": "true"},
        {"valuetype": "string", "stringvalue": "Active"},
        {"valuetype": "currency", "value": "25.00", "currency": "USD"},
        {"valuetype": "percentage", "value": "0.25"},
        {"valuetype": "time", "timevalue": "PT1H"},
    ):
        data.addElement(TableCell(**attributes))
    sheet.addElement(header)
    sheet.addElement(data)
    document.spreadsheet.addElement(sheet)
    document.save(str(path))

    result = ODSReader().read(str(path))
    assert result.columns == ["amount", "date", "active", "string", "currency", "percentage", "time"]
    assert result.rows == [["12.5", "2026-11-14", "true", "Active", "25.00", "0.25", "PT1H"]]

    empty_path = tmp_path / "empty.ods"
    empty_document = OpenDocumentSpreadsheet()
    empty_document.spreadsheet.addElement(Table(name="Empty"))
    empty_document.save(str(empty_path))
    empty_result = ODSReader().read(str(empty_path))
    assert empty_result.columns == []
    assert empty_result.rows == []


def test_ods_rejects_a_repeated_header_row(tmp_path):
    """Una fila de encabezados repetida no se expande como esquema ambiguo."""
    path = tmp_path / "repeated_header.ods"
    document = OpenDocumentSpreadsheet()
    sheet = Table(name="Repeated header")
    row = TableRow(numberrowsrepeated="2")
    cell = TableCell()
    cell.addElement(P(text="name"))
    row.addElement(cell)
    sheet.addElement(row)
    document.spreadsheet.addElement(sheet)
    document.save(str(path))

    with pytest.raises(ImportReadLimitError):
        ODSReader().read(str(path))


def test_archive_reader_rejects_too_many_zip_entries(tmp_path, monkeypatch):
    """El preflight también limita la cantidad de miembros del contenedor."""
    path = tmp_path / "many_entries.xlsx"
    workbook = openpyxl.Workbook()
    workbook.save(path)
    monkeypatch.setattr(limits, "MAX_IMPORT_ARCHIVE_ENTRIES", 1)

    def forbidden_zipfile(*args, **kwargs):
        """Comprueba que el conteo se hace antes de crear el lector ZIP."""
        raise AssertionError("ZipFile no debe abrirse antes de limitar las entradas")

    monkeypatch.setattr(limits, "ZipFile", forbidden_zipfile, raising=False)

    with pytest.raises(ImportReadLimitError):
        XLSXReader().read(str(path))
