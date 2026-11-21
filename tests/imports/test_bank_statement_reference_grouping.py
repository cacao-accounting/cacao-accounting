# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1385: las referencias bancarias informan, no agrupan movimientos."""

from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter
from cacao_accounting.imports.services.import_service import ImportService


def test_bank_reference_does_not_group_distinct_rows_and_is_preserved():
    """Movimientos con referencia común siguen separados y guardan la referencia."""
    rows = [
        {"bank_account_id": "account-1", "posting_date": "2026-05-15", "reference": "same-ref", "deposit": "10"},
        {"bank_account_id": "account-1", "posting_date": "2026-05-15", "reference": "same-ref", "deposit": "5"},
    ]
    adapter = BankStatementAdapter()

    groups = ImportService()._group_by_reference(["reference"], rows, adapter)
    documents = [adapter.build_document(group, {"company_id": "cacao"})[0] for group in groups.values()]

    assert len(groups) == 2
    assert [document["reference_number"] for document in documents] == ["same-ref", "same-ref"]
    assert [document["deposit"] for document in documents] == [10, 5]
