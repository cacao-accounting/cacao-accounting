# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes
"""Snippets reutilizables para el diseñador de formatos."""

COMMON_SNIPPETS = [
    {
        "name": "Company Header",
        "code": """
<div class="company-header">
    <img src="{{ company.logo_url }}" alt="Logo" style="height: 60px;">
    <h1>{{ company.name }}</h1>
    <p>Tax ID: {{ company.tax_id }}</p>
    <p>{{ company.address }}</p>
</div>
""",
    },
    {
        "name": "Audit Footer",
        "code": """
<div class="audit-footer" style="margin-top: 50px; font-size: 10px; color: #999;">
    <p>Printed by: {{ audit.printed_by }} on {{ audit.printed_at | datetime }}</p>
</div>
""",
    },
    {
        "name": "Validation QR",
        "code": """
{% if validation.enabled and validation.qr_data_uri %}
<div class="validation-block" style="margin-top: 20px; display: flex; align-items: center; gap: 10px;">
    <img src="{{ validation.qr_data_uri }}" style="width: 72px; height: 72px;">
    <div style="font-size: 10px;">
        <strong>Validate document</strong><br>
        Scan this QR code to verify authenticity.
    </div>
</div>
{% endif %}
""",
    },
]


def get_common_snippets() -> list[dict[str, str]]:
    """Return reusable snippets for the print designer."""
    return list(COMMON_SNIPPETS)
