# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jose Moreno Reyes
"""Settings helpers for external document validation."""

from __future__ import annotations

from flask import current_app

from cacao_accounting.database import CacaoConfig, database

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
        return value.rstrip("/")
    fallback = current_app.config.get("EXTERNAL_DOCUMENT_VALIDATION_BASE_URL") or DEFAULT_VALIDATION_BASE_URL
    return str(fallback or DEFAULT_VALIDATION_BASE_URL).rstrip("/")


def save_external_validation_settings(enabled: bool, base_url: str | None) -> None:
    """Persist external validation settings in CacaoConfig."""
    _set_config_value(VALIDATION_ENABLED_KEY, "true" if enabled else "false")
    _set_config_value(VALIDATION_BASE_URL_KEY, (base_url or DEFAULT_VALIDATION_BASE_URL).strip())
    database.session.commit()


def _get_config_value(key: str) -> str | None:
    record = database.session.execute(database.select(CacaoConfig).filter_by(key=key)).scalar_one_or_none()
    if record is None or not record.value:
        return None
    return str(record.value).strip()


def _set_config_value(key: str, value: str) -> None:
    record = database.session.execute(database.select(CacaoConfig).filter_by(key=key)).scalar_one_or_none()
    if record is None:
        database.session.add(CacaoConfig(key=key, value=value))
        return
    record.value = value
