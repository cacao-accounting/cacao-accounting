"""Runtime mode helpers for desktop, cloud, and single-entity behavior."""

from __future__ import annotations

from os import environ

from flask import current_app, has_app_context


def is_truthy(value: str | bool | None) -> bool:
    """Return whether a runtime flag value should be treated as enabled."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def detect_desktop_mode() -> bool:
    """Detect desktop mode from packaging and environment flags."""
    if environ.get("SNAP_NAME"):
        return True
    if environ.get("FLATPAK_ID"):
        return True
    return is_truthy(environ.get("CACAO_ACCOUNTING_DESKTOP"))


def is_desktop_mode() -> bool:
    """Return whether the current app/request is running in desktop mode."""
    if has_app_context() and "MODO_ESCRITORIO" in current_app.config:
        return is_truthy(current_app.config.get("MODO_ESCRITORIO"))
    return detect_desktop_mode()


def force_single_entity() -> bool:
    """Return whether this installation is limited to one company."""
    return is_desktop_mode() or is_truthy(environ.get("CACAO_ACCOUNTING_FORCE_SINGLE_ENTITY"))


def is_cloud_mode() -> bool:
    """Return whether cloud-only collaboration features may be shown."""
    return not is_desktop_mode()
