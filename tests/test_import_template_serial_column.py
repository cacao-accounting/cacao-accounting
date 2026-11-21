# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1061: el serial de artículo no colisiona con la serie de numeración.

La plantilla oficial debe poder reimportarse sin que la columna `serie` sea
rechazada como PROHIBITED_COLUMN.
"""

from __future__ import annotations

import pytest

from cacao_accounting.imports.adapters.transaction_documents import (
    TransactionDocumentAdapter,
    TransactionImportConfig,
)
from cacao_accounting.imports.column_labels import canonical_columns
from cacao_accounting.imports.services.import_service import ImportService


def _adapter() -> TransactionDocumentAdapter:
    """Build the generic transaction adapter."""
    return TransactionDocumentAdapter(
        TransactionImportConfig(
            entity_type="purchase_request",
            header_model=object,
            item_model=object,
            parent_field="purchase_request_id",
            include_batch_serial=True,
        )
    )


@pytest.mark.parametrize("language", ["es", "en"])
def test_official_template_headers_canonicalize_without_reserved_serie(language):
    """`serie`/`serial` map to numero_serie, not the reserved naming series."""
    adapter = _adapter()
    visible = adapter.localized_columns(language)
    canonical = canonical_columns(visible, adapter.columns)

    assert "numero_serie" in canonical
    assert "serie" not in canonical


@pytest.mark.parametrize("language", ["es", "en"])
def test_official_template_is_accepted_by_header_validation(language):
    """Reimporting the unchanged template produces no prohibited column."""
    adapter = _adapter()
    canonical = canonical_columns(adapter.localized_columns(language), adapter.columns)

    errors = ImportService()._collect_header_errors("batch-test", canonical, adapter)

    assert [error for error in errors if error.error_type == "PROHIBITED_COLUMN"] == []
