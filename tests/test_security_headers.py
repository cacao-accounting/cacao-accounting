# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

import pytest
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
