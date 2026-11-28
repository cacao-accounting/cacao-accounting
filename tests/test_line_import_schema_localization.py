# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Localization of the line-import schema API (#1666)."""

from __future__ import annotations

from cacao_accounting.database import User, database


def test_journal_schema_localizes_labels_without_changing_import_aliases(app, entorno_contable, authenticated_client):
    """English labels are localized while stable keys and aliases remain unchanged."""
    with app.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        previous_language = admin.language
        admin.language = "en"
        database.session.commit()

    try:
        response = authenticated_client("admin").get("/api/line-import/schema?doctype=journal_entry")

        assert response.status_code == 200
        schema = response.get_json()
        columns = {column["key"]: column for column in schema["columns"]}
        assert schema["label"] == "Accounting Entry"
        assert columns["account"]["label"] == "Account"
        assert columns["debit"]["label"] == "Debit"
        assert columns["party_type"]["label"] == "Party type"
        assert "cuenta contable" in columns["account"]["aliases"]
        assert "account_code" in columns["account"]["aliases"]
    finally:
        with app.app_context():
            admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
            admin.language = previous_language
            database.session.commit()
