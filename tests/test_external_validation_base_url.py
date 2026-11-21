"""#2131: la URL base de validación externa se valida antes de persistir."""

from __future__ import annotations

import pytest

from cacao_accounting.printing import settings as printing_settings


@pytest.fixture
def validation_settings_app(app, monkeypatch):
    values: dict[str, str] = {}

    def fake_get(key: str):
        return values.get(key)

    def fake_set(key: str, value: str) -> None:
        values[key] = value

    committed = {"count": 0}

    def fake_commit() -> None:
        committed["count"] += 1

    monkeypatch.setattr(printing_settings, "_get_config_value", fake_get)
    monkeypatch.setattr(printing_settings, "_set_config_value", fake_set)
    monkeypatch.setattr(printing_settings.database.session, "commit", fake_commit)
    yield app, values, committed


def test_save_external_validation_settings_accepts_https_url(validation_settings_app):
    app, values, committed = validation_settings_app
    with app.app_context():
        printing_settings.save_external_validation_settings(True, "https://validar.ejemplo.test/base/")

    assert values[printing_settings.VALIDATION_ENABLED_KEY] == "true"
    assert values[printing_settings.VALIDATION_BASE_URL_KEY] == "https://validar.ejemplo.test/base"
    assert committed["count"] == 1


def test_save_external_validation_settings_rejects_unsafe_url(validation_settings_app):
    app, values, committed = validation_settings_app
    with app.app_context():
        with pytest.raises(ValueError):
            printing_settings.save_external_validation_settings(False, "javascript:alert(1)")

    assert values == {}
    assert committed["count"] == 0
