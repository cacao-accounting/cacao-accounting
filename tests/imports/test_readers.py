# SPDX-License-Identifier: Apache-2.0

"""Tests for import readers module."""

from __future__ import annotations

import os
import tempfile

import pytest

from cacao_accounting.imports.readers.base import BaseReader, NormalizedTable
from cacao_accounting.imports.readers.csv_reader import CSVReader
from cacao_accounting.imports.readers.ods_reader import ODSReader
from cacao_accounting.imports.readers.xls_reader import XLSReader


class TestNormalizedTable:
    def test_normalized_table_default_values(self):
        table = NormalizedTable()
        assert table.columns == []
        assert table.rows == []
        assert table.source_format == ""

    def test_normalized_table_with_data(self):
        table = NormalizedTable(
            columns=["col1", "col2"],
            rows=[["a", "b"], ["c", "d"]],
            source_format="csv",
        )
        assert len(table.columns) == 2
        assert len(table.rows) == 2
        assert table.source_format == "csv"


class TestBaseReader:
    def test_base_reader_read_not_implemented(self):
        reader = BaseReader()
        with pytest.raises(NotImplementedError):
            reader.read("any_path")


class TestCSVReader:
    def test_csv_reader_read_simple_csv(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("name,age,city\n")
            f.write("John,30,Managua\n")
            f.write("Jane,25,León\n")
            temp_path = f.name

        try:
            reader = CSVReader()
            table = reader.read(temp_path)
            assert table.source_format == "csv"
            assert table.columns == ["name", "age", "city"]
            assert len(table.rows) == 2
            assert table.rows[0] == ["John", "30", "Managua"]
        finally:
            os.unlink(temp_path)

    def test_csv_reader_read_csv_with_semicolon_delimiter(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("name;age;city\n")
            f.write("John;30;Managua\n")
            temp_path = f.name

        try:
            reader = CSVReader()
            table = reader.read(temp_path)
            assert table.columns == ["name", "age", "city"]
            assert table.rows[0] == ["John", "30", "Managua"]
        finally:
            os.unlink(temp_path)

    def test_csv_reader_read_empty_csv(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            temp_path = f.name

        try:
            reader = CSVReader()
            table = reader.read(temp_path)
            assert table.columns == []
            assert table.rows == []
        finally:
            os.unlink(temp_path)

    def test_csv_reader_read_csv_with_only_headers(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("col1,col2,col3\n")
            temp_path = f.name

        try:
            reader = CSVReader()
            table = reader.read(temp_path)
            assert table.columns == ["col1", "col2", "col3"]
            assert table.rows == []
        finally:
            os.unlink(temp_path)

    def test_csv_reader_with_special_characters(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("name,city\n")
            f.write("María,Managua\n")
            f.write("José,León\n")
            temp_path = f.name

        try:
            reader = CSVReader()
            table = reader.read(temp_path)
            assert "María" in table.rows[0]
            assert "José" in table.rows[1]
        finally:
            os.unlink(temp_path)


class TestODSReader:
    def test_ods_reader_compute_valid_columns(self):
        reader = ODSReader()
        columns = ["col1", "", "col3", ""]
        rows = [["a", "b", "c", "d"]]

        valid_cols, col_indices = reader._compute_valid_columns(columns, rows)
        assert valid_cols == ["col1", "col3"]
        assert col_indices == [0, 2]

    def test_ods_reader_compute_valid_columns_all_empty(self):
        reader = ODSReader()
        columns = ["", "", ""]
        rows = [["a", "b", "c"]]

        valid_cols, col_indices = reader._compute_valid_columns(columns, rows)
        assert valid_cols == []
        assert col_indices == []

    def test_ods_reader_empty_rows_returns_empty_table(self):
        reader = ODSReader()
        columns = []
        rows = []

        valid_cols, col_indices = reader._compute_valid_columns(columns, rows)
        assert valid_cols == []
        assert col_indices == []


class TestXLSReader:
    def test_xls_reader_read_simple_xls(self):
        try:
            import xlwt
        except ImportError:
            pytest.skip("xlwt not available")

        wb = xlwt.Workbook()
        ws = wb.add_sheet("Sheet1")
        ws.write(0, 0, "Name")
        ws.write(0, 1, "Age")
        ws.write(1, 0, "John")
        ws.write(1, 1, 30)

        with tempfile.NamedTemporaryFile(suffix=".xls", delete=False) as f:
            temp_path = f.name
            wb.save(temp_path)

        try:
            reader = XLSReader()
            table = reader.read(temp_path)
            assert table.source_format == "xls"
            assert table.columns == ["Name", "Age"]
            assert len(table.rows) == 1
        finally:
            os.unlink(temp_path)

    def test_xls_reader_read_empty_xls(self):
        try:
            import xlwt
        except ImportError:
            pytest.skip("xlwt not available")

        wb = xlwt.Workbook()
        wb.add_sheet("Sheet1")

        with tempfile.NamedTemporaryFile(suffix=".xls", delete=False) as f:
            temp_path = f.name
            wb.save(temp_path)

        try:
            reader = XLSReader()
            table = reader.read(temp_path)
            assert table.source_format == "xls"
            assert table.columns == []
            assert table.rows == []
        finally:
            os.unlink(temp_path)


class TestReaderSubclasses:
    def test_csv_reader_inherits_from_base_reader(self):
        reader = CSVReader()
        assert isinstance(reader, BaseReader)

    def test_ods_reader_inherits_from_base_reader(self):
        reader = ODSReader()
        assert isinstance(reader, BaseReader)

    def test_xls_reader_inherits_from_base_reader(self):
        reader = XLSReader()
        assert isinstance(reader, BaseReader)
