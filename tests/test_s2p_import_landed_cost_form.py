"""Regresiones de renderizado para el formulario de costos de importación."""

from collections import Counter
from html.parser import HTMLParser
import json


class _FormFieldParser(HTMLParser):
    """Count rendered form field IDs and submitted names."""

    def __init__(self) -> None:
        super().__init__()
        self.ids: Counter[str] = Counter()
        self.names: Counter[str] = Counter()
        self.transaction_config: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Track IDs and names from rendered form controls."""
        if tag not in {"input", "select", "textarea"}:
            attributes = dict(attrs)
            expression = attributes.get("x-data") or ""
            if expression.startswith("transactionForm(") and expression.endswith(")"):
                self.transaction_config = json.loads(expression[len("transactionForm(") : -1])
            return
        attributes = dict(attrs)
        if field_id := attributes.get("id"):
            self.ids[field_id] += 1
        if field_name := attributes.get("name"):
            self.names[field_name] += 1


def test_import_landed_cost_form_renders_company_and_date_once(client, reference_users):
    """The shared header owns company/date fields without duplicate controls."""
    with client.session_transaction() as session:
        session["_user_id"] = str(reference_users["admin"].id)
        session["_fresh"] = True

    response = client.get("/buying/import-landed-cost/new?company=alpha&posting_date=2026-10-31")

    assert response.status_code == 200
    parser = _FormFieldParser()
    parser.feed(response.get_data(as_text=True))

    for field in ("company", "posting_date"):
        assert parser.ids[field] == 1
        assert parser.names[field] == 1

    assert parser.transaction_config is not None
    assert parser.transaction_config["initialHeader"] == {"company": "alpha", "posting_date": "2026-10-31"}


def test_import_landed_cost_form_preserves_fields_after_invalid_post(client, reference_users):
    """An invalid allocation method returns the submitted company and date to the form."""
    with client.session_transaction() as session:
        session["_user_id"] = str(reference_users["admin"].id)
        session["_fresh"] = True

    response = client.post(
        "/buying/import-landed-cost/new",
        data={"company": "alpha", "posting_date": "2026-10-31", "allocation_method": "invalid"},
    )

    assert response.status_code == 200
    parser = _FormFieldParser()
    parser.feed(response.get_data(as_text=True))
    assert parser.transaction_config is not None
    assert parser.transaction_config["initialHeader"] == {"company": "alpha", "posting_date": "2026-10-31"}


def test_import_landed_cost_invalid_post_prefers_submitted_values_over_query(client, reference_users):
    """An invalid POST re-renders the submitted values, not stale URL filters."""
    with client.session_transaction() as session:
        session["_user_id"] = str(reference_users["admin"].id)
        session["_fresh"] = True

    response = client.post(
        "/buying/import-landed-cost/new?company=alpha&posting_date=2026-10-30",
        data={"company": "cacao", "posting_date": "2026-10-31", "allocation_method": "invalid"},
    )

    assert response.status_code == 200
    parser = _FormFieldParser()
    parser.feed(response.get_data(as_text=True))
    assert parser.transaction_config is not None
    assert parser.transaction_config["initialHeader"] == {"company": "cacao", "posting_date": "2026-10-31"}
