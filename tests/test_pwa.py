# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

import json
from cacao_accounting import create_app

def test_pwa_manifest_and_sw():
    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "testsecretkey",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "WTF_CSRF_ENABLED": False,
        }
    )
    client = app.test_client()

    # Test Manifest availability and structure
    res_manifest = client.get("/static/manifest.json")
    assert res_manifest.status_code == 200
    manifest_data = json.loads(res_manifest.data.decode("utf-8"))
    assert manifest_data["name"] == "Cacao Accounting"
    assert manifest_data["short_name"] == "Cacao"
    assert manifest_data["start_url"] == "/"
    assert manifest_data["display"] == "standalone"
    assert manifest_data["theme_color"] == "#2E7D32"

    icon_sizes = [icon["sizes"] for icon in manifest_data.get("icons", [])]
    assert "192x192" in icon_sizes
    assert "512x512" in icon_sizes

    # Test Service Worker endpoint
    res_sw = client.get("/sw.js")
    assert res_sw.status_code == 200
    assert "application/javascript" in res_sw.content_type
    assert res_sw.headers.get("Service-Worker-Allowed") == "/"
    assert b"cacao-accounting-v1" in res_sw.data

    # Test Content Security Policy headers include manifest-src and worker-src
    res_ping = client.get("/ping")
    csp = res_ping.headers.get("Content-Security-Policy", "")
    assert "manifest-src 'self'" in csp
    assert "worker-src 'self'" in csp
