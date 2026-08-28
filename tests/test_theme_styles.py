"""Regression tests for the visual theme contract."""

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_login_remains_light_when_the_saved_theme_is_dark() -> None:
    """The sign-in screen must not inherit the application dark theme."""
    template = (PROJECT_ROOT / "cacao_accounting" / "auth" / "templates" / "login.html").read_text(encoding="utf-8")
    stylesheet = (PROJECT_ROOT / "cacao_accounting" / "static" / "css" / "signin.css").read_text(encoding="utf-8")

    assert '<body class="login-page">' in template
    assert 'html[data-theme="dark"] .login-page' in stylesheet
    assert "background: #faf6f1 !important;" in stylesheet
    assert "background: #ffffff !important;" in stylesheet


def test_final_theme_uses_neutral_surfaces_and_cacao_accents() -> None:
    """The visual system uses neutral surfaces and reserves Cacao for accents."""
    stylesheet = (PROJECT_ROOT / "cacao_accounting" / "static" / "css" / "cacaoaccounting.css").read_text(encoding="utf-8")
    final_tokens = stylesheet.rsplit("/* Visual system v5:", maxsplit=1)[1]

    assert "--ca-bg: #F5F6F8;" in final_tokens
    assert "--ca-sidebar-bg: #FAFAF9;" in final_tokens
    assert "--ca-navbar-bg: #FFFFFF;" in final_tokens
    assert "--ca-p600: #5F7D46;" in final_tokens
    assert "--ca-sidebar-active-border: #5F7D46;" in final_tokens
    assert "--ca-bg: #111315;" in final_tokens
    assert "--ca-surface: #1C1F22;" in final_tokens
    assert "--ca-sidebar-active-border: #B8693E;" in final_tokens


def test_workspace_styles_prioritize_operations_and_keep_status_badges() -> None:
    """Module workspaces promote operations while preserving semantic badges."""
    macro = (PROJECT_ROOT / "cacao_accounting" / "templates" / "macros.html").read_text(encoding="utf-8")
    stylesheet = (PROJECT_ROOT / "cacao_accounting" / "static" / "css" / "cacaoaccounting.css").read_text(encoding="utf-8")

    assert "ca-module-state" in macro
    assert "bi-check-circle-fill" in macro
    assert "ca-module-state__label" in macro
    assert "ca-approval-count" in macro
    assert ".ca-module-card--primary" in stylesheet
    assert "grid-column: 1 / -1;" in stylesheet
    assert "--ca-status-info: #2563EB;" in stylesheet
    assert ".ca-module-state.ca-status-pending-approval" in stylesheet


def test_navigation_uses_complete_theme_wordmarks() -> None:
    """The navigation selects complete wordmarks instead of styling a shared logo."""
    macro = (PROJECT_ROOT / "cacao_accounting" / "templates" / "macros.html").read_text(encoding="utf-8")
    stylesheet = (PROJECT_ROOT / "cacao_accounting" / "static" / "css" / "cacaoaccounting.css").read_text(encoding="utf-8")
    dark_wordmark = (PROJECT_ROOT / "cacao_accounting" / "static" / "media" / "brand-dark.svg").read_text(encoding="utf-8")

    assert "media/brand-dark.svg" in macro
    assert "data-light-src" in macro
    assert "data-dark-src" in macro
    assert "brandLogo.src" in macro
    navbar = macro.split('<header class="ca-navbar">', maxsplit=1)[1].split("</header>", maxsplit=1)[0]
    assert navbar.count("<img") == 1
    assert "fill:#E8D6BE" in dark_wordmark
    assert "<image href=" not in dark_wordmark
    assert "padding: 2px 5px;" not in stylesheet
    assert "Compatibility with already-cached pages" in stylesheet


def test_module_status_badge_keeps_normal_access_and_exceptions() -> None:
    """Module state badges remain visible and accessible for every state."""
    environment = Environment(loader=FileSystemLoader(PROJECT_ROOT / "cacao_accounting" / "templates"))
    badge = environment.get_template("macros.html").module.module_status_badge

    rendered_ok = badge(SimpleNamespace(status="ok", css_class="ca-status-ok", title="Operativo", label="Todo ok"))
    assert 'data-status="ok"' in rendered_ok
    assert "bi-check-circle-fill" in rendered_ok
    assert "ca-module-state__label" not in rendered_ok
    rendered_pending = badge(
        SimpleNamespace(
            status="pending_approval",
            css_class="ca-status-pending-approval",
            title="2 registros pendientes de aprobación",
            label="Pendiente de aprobar",
        )
    )
    assert "bi-clock-history" in rendered_pending
    assert "Pendiente de aprobar" in rendered_pending
    assert "ca-module-state__label" in rendered_pending
    rendered = badge(
        SimpleNamespace(status="no_access", css_class="ca-status-no-access", title="Sin acceso", label="Sin acceso")
    )
    assert 'data-status="no_access"' in rendered
    assert "bi-lock-fill" in rendered
    assert "Sin acceso" in rendered
