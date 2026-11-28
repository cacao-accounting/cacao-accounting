# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""Company changes invalidate recurrent journal line selectors (#1632)."""

from pathlib import Path

TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "cacao_accounting"
    / "contabilidad"
    / "templates"
    / "contabilidad"
    / "recurring_journal_nuevo.html"
)


def test_recurring_journal_company_filters_clear_copied_values():
    """Account and dimension selectors observe the header company and clear their models."""
    source = TEMPLATE.read_text(encoding="utf-8")

    assert source.count('filterSources: ["#company"]') == 6
    assert "onClear: function() { line.account_code = ''; line.account_label = ''; }" in source
    assert "onClear: function() { modalLine.cost_center = ''; }" in source
    assert "onClear: function() { modalLine.unit = ''; }" in source
    assert "onClear: function() { modalLine.project = ''; }" in source
    assert "onClear: function() { modalLine.party_id = ''; }" in source
