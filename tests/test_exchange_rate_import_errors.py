# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1765: errores de decodificación de tasas se muestran como validación."""

from io import BytesIO

import pytest

from cacao_accounting.contabilidad.exchange_rate_import_service import ExchangeRateImportError, ExchangeRateImportService
from cacao_accounting.database import ExchangeRate, database


def test_csv_with_invalid_encoding_raises_import_domain_error():
    """El parser envuelve UnicodeDecodeError en el error esperado por la ruta."""
    with pytest.raises(ExchangeRateImportError, match="UTF-8"):
        ExchangeRateImportService().parse_file("rates.csv", b"\xff\xfe\x00")


def test_exchange_import_route_renders_invalid_encoding_without_writing(app, entorno_contable, authenticated_client):
    """Un CSV de otra codificación produce feedback visible y no escribe tasas."""
    with app.app_context():
        original_count = database.session.query(ExchangeRate).count()

    response = authenticated_client().post(
        "/accounting/exchange/import",
        data={"file": (BytesIO(b"\xff\xfe\x00"), "rates.csv")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert "El archivo CSV debe estar codificado en UTF-8." in response.get_data(as_text=True)
    with app.app_context():
        assert database.session.query(ExchangeRate).count() == original_count
