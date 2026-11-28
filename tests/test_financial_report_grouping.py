# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La agrupación del detalle GL consolida cada grupo en un único bloque.

Escenario de negocio (issue #2189): ``_group_rows_by_field`` cerraba el
subtotal al cambiar el valor del grupo entre filas consecutivas. Como el
detalle se ordena por fecha y el agrupador es independiente, una secuencia
A, B, A producía dos encabezados de A y dividía su subtotal. Cada valor debe
tener un único bloque con todas sus filas y su suma completa.
"""

from __future__ import annotations

from decimal import Decimal

from cacao_accounting.reportes.helpers import _format_cell, _group_paginated_rows, _group_rows_by_field


def _interleaved_rows():
    source_rows = [
        {"account_code": "1101", "posting_date": "2026-05-01"},
        {"account_code": "2101", "posting_date": "2026-05-02"},
        {"account_code": "1101", "posting_date": "2026-05-03"},
    ]
    display_rows = [
        {"account_code": "1101", "debit": "10.00", "credit": "0.00"},
        {"account_code": "2101", "debit": "0.00", "credit": "7.00"},
        {"account_code": "1101", "debit": "5.00", "credit": "0.00"},
    ]
    return display_rows, source_rows


def test_agrupa_filas_intercaladas_en_un_unico_bloque(app):
    """A, B, A produce dos grupos: A con dos filas y B con una."""
    display_rows, source_rows = _interleaved_rows()

    with app.app_context():
        grouped = _group_rows_by_field(display_rows, source_rows, "account_code", "NIO")

    headers = [row for row in grouped if row.get("__row_type") == "group"]
    subtotals = [row for row in grouped if row.get("__row_type") == "group_subtotal"]
    group_members = [row["__tree_group"] for row in grouped if "__tree_group" in row]

    assert len(headers) == 2
    assert len(subtotals) == 2
    assert headers[0]["__group_title"].endswith(": 1101")
    assert headers[1]["__group_title"].endswith(": 2101")
    assert group_members == [0, 0, 1]


def test_subtotal_acumula_todas_las_filas_del_grupo(app):
    """El subtotal de A suma las dos filas aunque estuvieran separadas."""
    display_rows, source_rows = _interleaved_rows()

    with app.app_context():
        grouped = _group_rows_by_field(display_rows, source_rows, "account_code", "NIO")
        expected_debit = _format_cell("debit", Decimal("15"), "NIO")
        expected_credit = _format_cell("credit", Decimal("7"), "NIO")

    subtotals = [row for row in grouped if row.get("__row_type") == "group_subtotal"]

    assert subtotals[0]["debit"] == expected_debit
    assert subtotals[0]["credit"] == "0.00"
    assert subtotals[1]["debit"] == "0.00"
    assert subtotals[1]["credit"] == expected_credit


def test_conserva_el_orden_de_primera_aparicion_y_de_filas(app):
    """Los bloques respetan la primera aparición y las filas su orden relativo."""
    source_rows = [
        {"segment": "Sur", "posting_date": "2026-05-01"},
        {"segment": "Norte", "posting_date": "2026-05-02"},
        {"segment": "Sur", "posting_date": "2026-05-03"},
    ]
    display_rows = [
        {"account_code": "1", "debit": "1.00", "credit": "0.00"},
        {"account_code": "2", "debit": "2.00", "credit": "0.00"},
        {"account_code": "3", "debit": "3.00", "credit": "0.00"},
    ]

    with app.app_context():
        grouped = _group_rows_by_field(display_rows, source_rows, "segment", "NIO")

    titles = [row["__group_title"] for row in grouped if row.get("__row_type") == "group"]
    accounts = [row["account_code"] for row in grouped if "__tree_group" in row]

    assert [title.rsplit(": ", 1)[-1] for title in titles] == ["Sur", "Norte"]
    assert accounts == ["1", "3", "2"]


def test_subtotal_paginas_usa_cifras_reales_con_columnas_ocultas(app):
    """La última página muestra el subtotal íntegro aunque se oculte débito."""
    source = [
        {
            "account_code": "1101",
            "__group_position": 2,
            "__group_count": 2,
            "__group_debit": Decimal("2.0098"),
            "__group_credit": Decimal("0"),
        }
    ]
    with app.app_context():
        rows = _group_paginated_rows([{"account_code": "1101"}], source, "account_code", "NIO")
        expected = _format_cell("debit", Decimal("2.0098"), "NIO")
    assert rows[0]["__group_title"].endswith("(Continuación)")
    assert rows[-1]["debit"] == expected
