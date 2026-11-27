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


@pytest.mark.parametrize(
    "base_url",
    [
        "javascript:alert(1)",
        "https://validar.ejemplo.test/?q=1",
        "https://validar.ejemplo.test/#qr",
        "https://validar.ejemplo.test/?",
        "https://validar.ejemplo.test/#",
        "https://validar.ejemplo.test/?#",
    ],
)
def test_save_external_validation_settings_rejects_unsafe_url(validation_settings_app, base_url):
    app, values, committed = validation_settings_app
    with app.app_context():
        with pytest.raises(ValueError):
            printing_settings.save_external_validation_settings(False, base_url)

    assert values == {}
    assert committed["count"] == 0


def test_external_validation_base_url_falls_back_for_stored_query_or_fragment(validation_settings_app, monkeypatch):
    app, _values, _committed = validation_settings_app
    monkeypatch.setattr(
        printing_settings,
        "_get_config_value",
        lambda key: ("https://validar.ejemplo.test/?q=1#qr" if key == printing_settings.VALIDATION_BASE_URL_KEY else None),
    )
    with app.app_context():
        assert printing_settings.external_validation_base_url() == printing_settings.DEFAULT_VALIDATION_BASE_URL
