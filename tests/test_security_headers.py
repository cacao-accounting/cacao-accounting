# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

from cacao_accounting import create_app


def test_session_cookie_configurations():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "testsecretkey",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        }
    )
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"


def test_session_cookie_secure_can_be_disabled_for_http_development(monkeypatch):
    """Allow the local HTTP server to retain the session/CSRF cookie."""
    monkeypatch.setenv("CACAO_SESSION_COOKIE_SECURE", "False")
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "testsecretkey",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
        }
    )

    assert app.config["SESSION_COOKIE_SECURE"] is False


def test_csrf_ssl_strict_can_be_disabled_for_reverse_proxy_development(monkeypatch):
    """Allow a development proxy to terminate HTTPS before Flask receives it."""
    monkeypatch.setenv("CACAO_CSRF_SSL_STRICT", "False")
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "testsecretkey",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
        }
    )

    assert app.config["WTF_CSRF_SSL_STRICT"] is False


def test_http_security_headers():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "testsecretkey",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        }
    )

    with app.test_client() as client:
        response = client.get("/")

        # Verify Content-Security-Policy
        csp = response.headers.get("Content-Security-Policy")
        assert csp is not None
        assert "default-src 'self'" in csp
        assert "https://cdn.jsdelivr.net" in csp
        assert "frame-ancestors 'none'" in csp

        # Verify X-Frame-Options
        assert response.headers.get("X-Frame-Options") == "DENY"

        # Verify X-Content-Type-Options
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

        # Verify Strict-Transport-Security
        assert response.headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains"

        # Verify Permissions-Policy
        assert response.headers.get("Permissions-Policy") == "geolocation=(), microphone=(), camera=()"

        # Verify Referrer-Policy
        assert response.headers.get("Referrer-Policy") == "same-origin"
