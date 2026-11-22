# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Company-dependent selectors in party settings clear incompatible values (#1632)."""

from pathlib import Path

TEMPLATE = Path(__file__).resolve().parents[1] / "cacao_accounting" / "templates" / "party_company_settings_form.html"


def test_party_settings_wire_each_dependent_selector_to_the_company_input():
    """All account and tax selectors observe the row's unique company input."""
    source = TEMPLATE.read_text(encoding="utf-8")

    assert ":id=\"'party-company-' + index\"" in source
    assert source.count('filterSources: ["#party-company-" + index]') == 4
    assert 'row.company = "";' in source
    assert 'row[{{ account_field|tojson }}] = "";' in source
    assert 'row.default_price_list_id = "";' in source
    assert 'row.default_tax_rule_id = "";' in source
    assert 'row.tax_template_id = "";' in source
