# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Settings helpers for external document validation."""

from __future__ import annotations

from urllib.parse import urlsplit

from flask import current_app

from cacao_accounting.database import CacaoConfig, database
from cacao_accounting.i18n import _

VALIDATION_ENABLED_KEY = "external_document_validation_enabled"
VALIDATION_BASE_URL_KEY = "external_document_validation_base_url"
DEFAULT_VALIDATION_BASE_URL = "https://cacaocontent.com"


def external_validation_enabled() -> bool:
    """Return whether public document validation is enabled."""
    value = _get_config_value(VALIDATION_ENABLED_KEY)
    if value is None:
        return bool(current_app.config.get("EXTERNAL_DOCUMENT_VALIDATION_ENABLED", True))
    return value.lower() == "true"


def external_validation_base_url() -> str:
    """Return the configured public validation base URL."""
    value = _get_config_value(VALIDATION_BASE_URL_KEY)
    if value:
        try:
            return _normalize_validation_base_url(value)
        except ValueError:
            return DEFAULT_VALIDATION_BASE_URL.rstrip("/")
    fallback = current_app.config.get("EXTERNAL_DOCUMENT_VALIDATION_BASE_URL") or DEFAULT_VALIDATION_BASE_URL
    try:
        return _normalize_validation_base_url(str(fallback or DEFAULT_VALIDATION_BASE_URL))
    except ValueError:
        return DEFAULT_VALIDATION_BASE_URL.rstrip("/")


def _normalize_validation_base_url(base_url: str | None) -> str:
    """Valida y normaliza la URL base pública para códigos de validación."""
    candidate = (base_url or "").strip()
    if not candidate:
        return DEFAULT_VALIDATION_BASE_URL.rstrip("/")

    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(_("La URL base de validación externa debe usar http o https."))
    if parsed.username or parsed.password:
        raise ValueError(_("La URL base de validaci?n externa no debe incluir credenciales."))
    if parsed.query or parsed.fragment:
        raise ValueError(_("La URL base de validaci?n externa no debe incluir query ni fragmento."))

    return candidate.rstrip("/")


def save_external_validation_settings(enabled: bool, base_url: str | None) -> None:
    """Persist external validation settings in CacaoConfig."""
    normalized_base_url = _normalize_validation_base_url(base_url)
    _set_config_value(VALIDATION_ENABLED_KEY, "true" if enabled else "false")
    _set_config_value(VALIDATION_BASE_URL_KEY, normalized_base_url)
    database.session.commit()


def _get_config_value(key: str) -> str | None:
    record = database.session.execute(database.select(CacaoConfig).filter_by(key=key)).scalar_one_or_none()
    if record is None or not record.value:
        return None
    return str(record.value).strip()


def _set_config_value(key: str, value: str) -> None:
    from cacao_accounting.config_values import set_config_value

    set_config_value(key, value)
