# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Límites comunes de recursos para lectores tabulares."""

from pathlib import Path
import struct
from typing import BinaryIO
import zlib

from zipfile import ZIP_DEFLATED, ZIP_STORED

from cacao_accounting.i18n import _

MAX_IMPORT_FILE_BYTES = 25 * 1024 * 1024
MAX_IMPORT_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_IMPORT_ARCHIVE_ENTRIES = 4096
MAX_IMPORT_ROWS = 100_000
MAX_IMPORT_COLUMNS = 256
MAX_IMPORT_CELLS = 1_000_000
MAX_IMPORT_TEXT_CHARS = 64 * 1024 * 1024
MAX_IMPORT_SHEETS = 4096


class ImportReadLimitError(ValueError):
    """El archivo excede los límites de recursos de una importación."""

    def __init__(self) -> None:
        """Construye el error con su mensaje traducible."""
        super().__init__(_("El archivo excede los límites de recursos de importación."))


def validate_file_size(file_path: str) -> None:
    """Rechaza archivos de origen mayores al máximo permitido."""
    if Path(file_path).stat().st_size > MAX_IMPORT_FILE_BYTES:
        raise ImportReadLimitError()


def validate_archive_size(file_path: str) -> None:
    """Comprueba el tamaño real y el número de miembros antes de leer el libro."""
    validate_file_size(file_path)
    _preflight_zip(file_path)


def _preflight_zip(file_path: str) -> None:
    """Cuenta y mide miembros antes de que ZipFile materialice el directorio."""
    with open(file_path, "rb") as archive:
        archive.seek(0, 2)
        file_size = archive.tell()
        tail_size = min(file_size, 22 + 65_535)
        archive.seek(-tail_size, 2)
        tail = archive.read(tail_size)

    signature = b"PK\x05\x06"
    index = len(tail)
    while True:
        index = tail.rfind(signature, 0, index)
        if index < 0:
            raise ImportReadLimitError()
        if index + 22 <= len(tail):
            comment_length = struct.unpack_from("<H", tail, index + 20)[0]
            if index + 22 + comment_length == len(tail):
                disk_entries, entry_count, central_size, central_offset = struct.unpack_from("<HHII", tail, index + 8)
                if disk_entries != entry_count or entry_count == 0xFFFF:
                    raise ImportReadLimitError()
                absolute_central_start = file_size - tail_size + central_offset
                central_end = absolute_central_start + central_size
                eocd_start = file_size - tail_size + index
                if central_end != eocd_start:
                    raise ImportReadLimitError()
                with open(file_path, "rb") as central_archive:
                    return _count_central_entries(central_archive, absolute_central_start, central_end)


def _count_central_entries(archive: BinaryIO, start: int, end: int) -> None:
    """Valida cabeceras ZIP y mide la descompresión sin crear objetos por miembro."""
    count = 0
    total_size = 0
    position = start
    while position < end:
        archive.seek(position)
        header = archive.read(46)
        if len(header) != 46 or header[:4] != b"PK\x01\x02":
            raise ImportReadLimitError()
        filename_length, extra_length, comment_length = struct.unpack_from("<HHH", header, 28)
        method = struct.unpack_from("<H", header, 10)[0]
        compressed_size, declared_size = struct.unpack_from("<II", header, 20)
        local_offset = struct.unpack_from("<I", header, 42)[0]
        if compressed_size == 0xFFFFFFFF or declared_size == 0xFFFFFFFF or local_offset == 0xFFFFFFFF:
            raise ImportReadLimitError()
        position += 46 + filename_length + extra_length + comment_length
        if position > end:
            raise ImportReadLimitError()
        count += 1
        if count > MAX_IMPORT_ARCHIVE_ENTRIES or declared_size > MAX_IMPORT_ARCHIVE_BYTES:
            raise ImportReadLimitError()
        actual_size = _measure_member(archive, start, local_offset, method, compressed_size)
        if actual_size != declared_size:
            raise ImportReadLimitError()
        total_size += actual_size
        if total_size > MAX_IMPORT_ARCHIVE_BYTES:
            raise ImportReadLimitError()


def _measure_member(archive: BinaryIO, central_start: int, local_offset: int, method: int, compressed_size: int) -> int:
    """Mide bytes expandidos usando el tamaño comprimido del miembro."""
    archive.seek(local_offset)
    local_header = archive.read(30)
    if len(local_header) != 30 or local_header[:4] != b"PK\x03\x04":
        raise ImportReadLimitError()
    if struct.unpack_from("<H", local_header, 8)[0] != method:
        raise ImportReadLimitError()
    name_size, extra_size = struct.unpack_from("<HH", local_header, 26)
    data_start = local_offset + 30 + name_size + extra_size
    data_end = data_start + compressed_size
    if data_end > central_start:
        raise ImportReadLimitError()
    if method == ZIP_STORED:
        return compressed_size
    if method != ZIP_DEFLATED:
        raise ImportReadLimitError()
    archive.seek(data_start)
    decompressor = zlib.decompressobj(-15)
    expanded = 0
    remaining = compressed_size
    while remaining:
        chunk = archive.read(min(64 * 1024, remaining))
        if not chunk:
            raise ImportReadLimitError()
        remaining -= len(chunk)
        expanded += _decompress_chunk(decompressor, chunk, MAX_IMPORT_ARCHIVE_BYTES - expanded)
    if not decompressor.eof:
        raise ImportReadLimitError()
    return expanded


def _decompress_chunk(decompressor, chunk: bytes, remaining: int) -> int:
    """Expand one block with a one-byte margin to detect overflow immediately."""
    try:
        expanded = decompressor.decompress(chunk, remaining + 1)
    except zlib.error as exc:
        raise ImportReadLimitError() from exc
    if len(expanded) > remaining:
        raise ImportReadLimitError()
    if decompressor.unconsumed_tail:
        raise ImportReadLimitError()
    return len(expanded)


class ReadBudget:
    """Cuenta filas, columnas y celdas antes de conservarlas en la tabla."""

    def __init__(self) -> None:
        """Inicia los contadores sin filas ni celdas consumidas."""
        self.rows = 0
        self.cells = 0

    def consume_header(self, columns: int) -> None:
        """Registra y limita la fila de encabezados."""
        self._check_columns(columns)
        self._consume_cells(columns)

    def consume_row(self, columns: int) -> None:
        """Registra y limita una fila de datos."""
        self.consume_repeated_rows(columns, 1)

    def consume_repeated_rows(self, columns: int, count: int) -> None:
        """Registra filas repetidas sin materializarlas primero."""
        self._check_columns(columns)
        if count < 1 or self.rows + count > MAX_IMPORT_ROWS:
            raise ImportReadLimitError()
        self.rows += count
        self._consume_cells(columns * count)

    @staticmethod
    def _check_columns(columns: int) -> None:
        """Rechaza una fila que declara demasiadas columnas."""
        if columns > MAX_IMPORT_COLUMNS:
            raise ImportReadLimitError()

    def check_columns(self, columns: int) -> None:
        """Valida el ancho sin incrementar la cuenta de celdas."""
        self._check_columns(columns)

    def _consume_cells(self, cells: int) -> None:
        """Actualiza el total de celdas sin superar el límite compartido."""
        self.cells += cells
        if self.cells > MAX_IMPORT_CELLS:
            raise ImportReadLimitError()
