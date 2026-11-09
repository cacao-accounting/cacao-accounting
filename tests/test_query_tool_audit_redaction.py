# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La auditoría de query tools redacta secretos dentro de listas.

Escenario de negocio (issue #2178): ``serialize_parameters`` solo recorría
diccionarios; una lista de filtros conservaba ``api_key``, ``password`` o
``token`` en claro dentro de ``AuditTrail.after_json``.
"""

from __future__ import annotations

from decimal import Decimal

from cacao_accounting.database import AuditTrail, database
from cacao_accounting.query_tools.audit import log_query_tool_event, serialize_parameters
from cacao_accounting.query_tools.context import QueryContext


def test_serializa_y_redacta_diccionarios_dentro_de_listas():
    """La redacción alcanza listas, anidamientos y conserva tipos especiales."""
    resultado = serialize_parameters(
        {
            "filters": [{"api_key": "list-secret", "nested": {"password": "deep-secret"}}],
            "tokens": ({"token": "tuple-secret"},),
            "amount": Decimal("12.50"),
        }
    )

    assert resultado["filters"][0]["api_key"] == "***"
    assert resultado["filters"][0]["nested"]["password"] == "***"
    assert resultado["tokens"][0]["token"] == "***"
    assert resultado["amount"] == "12.50"
    assert "list-secret" not in str(resultado)
    assert "deep-secret" not in str(resultado)
    assert "tuple-secret" not in str(resultado)


def test_el_evento_persistido_no_contiene_el_secreto(app):
    """El after_json de auditoría no filtra el secreto de una lista."""
    tool_name = "redaction-probe"
    with app.app_context():
        log_query_tool_event(
            action="query_tool.executed",
            context=QueryContext(user_id="audit"),
            tool_name=tool_name,
            parameters={"filters": [{"api_key": "list-secret"}]},
        )
        database.session.commit()

        entrada = (
            database.session.execute(database.select(AuditTrail).filter_by(document_id=tool_name, document_type="query_tool"))
            .scalars()
            .first()
        )

        assert entrada is not None
        assert "list-secret" not in entrada.after_json
        assert "***" in entrada.after_json
