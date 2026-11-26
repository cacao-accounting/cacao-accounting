# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William Jos? Moreno Reyes

"""Template downloads must be isolated per request/locale."""

from __future__ import annotations

from cacao_accounting.database import Modules, database


def _ensure_imports_module(app) -> None:
    with app.app_context():
        module = database.session.execute(database.select(Modules).filter_by(module="imports")).scalar_one_or_none()
        if module is None:
            module = Modules(module="imports", default=False, enabled=True)
            database.session.add(module)
        else:
            module.enabled = True
        database.session.commit()


def test_download_template_uses_request_locale_and_isolated_path(app, entorno_contable, authenticated_client, monkeypatch):
    _ensure_imports_module(app)
    client = authenticated_client("admin")

    import importlib

    routes = importlib.import_module("cacao_accounting.imports.routes")

    monkeypatch.setattr(routes, "get_locale", lambda: "es")
    es = client.get("/imports/template/customer?format=csv")
    monkeypatch.setattr(routes, "get_locale", lambda: "en")
    en = client.get("/imports/template/customer?format=csv")

    assert es.status_code == 200
    assert en.status_code == 200

    es_body = es.data.decode("utf-8-sig").strip()
    en_body = en.data.decode("utf-8-sig").strip()

    assert es_body.startswith("nombre,")
    assert en_body.startswith("name,")
    assert es_body != en_body
