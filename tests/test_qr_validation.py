# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

import pytest
import builtins

from cacao_accounting.printing.validation import (
    calculate_validation_hash,
    generate_validation_token,
    get_canonical_payload,
    ValidationService,
)


def test_token_generation():
    token1 = generate_validation_token()
    token2 = generate_validation_token()
    assert len(token1) >= 32
    assert token1 != token2


def test_canonical_payload():
    data = {
        "company_code": "cacao",
        "company_id": "legacy",
        "document_type": "sales_invoice",
        "grand_total": 100.50,
        "internal_note": "secret",
    }
    payload = get_canonical_payload(data)
    assert "cacao" in payload
    assert "legacy" not in payload
    assert "sales_invoice" in payload
    assert "100.5" in payload
    assert "internal_note" not in payload
    assert "secret" not in payload


def test_validation_hash():
    payload = '{"company_code":"cacao"}'
    h1 = calculate_validation_hash(payload)
    h2 = calculate_validation_hash(payload)
    assert h1 == h2
    assert len(h1) == 64


def test_qr_data_uri():
    service = ValidationService()
    uri = service.get_qr_data_uri("https://example.com")
    assert uri.startswith("data:image/png;base64,")


def test_qr_dependency_missing_fails_explicitly(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "segno":
            raise ImportError("missing segno")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    service = ValidationService()

    with pytest.raises(RuntimeError, match="QR dependency missing"):
        service.get_qr_data_uri("https://example.com")
