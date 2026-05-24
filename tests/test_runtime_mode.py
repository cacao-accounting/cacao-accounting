# SPDX-License-Identifier: Apache-2.0
"""Tests for centralized runtime mode detection."""

from __future__ import annotations

from flask import Flask

from cacao_accounting.runtime_mode import detect_desktop_mode, force_single_entity, is_desktop_mode, is_truthy


def test_is_truthy_accepts_expected_values() -> None:
    """Truthy parsing supports common env/config spellings."""
    truthy_values: tuple[str | bool | None, ...] = ("1", "true", "TRUE", "yes", "y", "on", True)
    falsy_values: tuple[str | bool | None, ...] = ("0", "false", "no", "", None, False)

    for value in truthy_values:
        assert is_truthy(value)

    for value in falsy_values:
        assert not is_truthy(value)


def test_detect_desktop_mode_from_snap_flatpak_or_env(monkeypatch) -> None:
    """Desktop mode is detected from packaging env vars or explicit env flag."""
    monkeypatch.delenv("SNAP_NAME", raising=False)
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.delenv("CACAO_ACCOUNTING_DESKTOP", raising=False)
    assert not detect_desktop_mode()

    monkeypatch.setenv("SNAP_NAME", "cacao-accounting")
    assert detect_desktop_mode()

    monkeypatch.delenv("SNAP_NAME", raising=False)
    monkeypatch.setenv("FLATPAK_ID", "com.cacao.Accounting")
    assert detect_desktop_mode()

    monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.setenv("CACAO_ACCOUNTING_DESKTOP", "true")
    assert detect_desktop_mode()


def test_force_single_entity_uses_desktop_or_explicit_env(monkeypatch) -> None:
    """Single-entity mode follows desktop mode or its own explicit flag."""
    monkeypatch.delenv("SNAP_NAME", raising=False)
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.delenv("CACAO_ACCOUNTING_DESKTOP", raising=False)
    monkeypatch.delenv("CACAO_ACCOUNTING_FORCE_SINGLE_ENTITY", raising=False)

    app = Flask(__name__)
    app.config["MODO_ESCRITORIO"] = False
    with app.app_context():
        assert not is_desktop_mode()
        assert not force_single_entity()

        monkeypatch.setenv("CACAO_ACCOUNTING_FORCE_SINGLE_ENTITY", "true")
        assert force_single_entity()

        app.config["MODO_ESCRITORIO"] = True
        monkeypatch.setenv("CACAO_ACCOUNTING_FORCE_SINGLE_ENTITY", "false")
        assert is_desktop_mode()
        assert force_single_entity()
