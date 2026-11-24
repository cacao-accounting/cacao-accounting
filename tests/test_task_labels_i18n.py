# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1843: estado y prioridad de tareas se muestran traducidos.

La bandeja "Mis tareas" y el panel documental deben usar las mismas etiquetas
legibles que los filtros, sin exponer los códigos internos en inglés.
"""

from __future__ import annotations

import os
from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting.database import DocumentTask, SalesOrder, User, database

pytestmark = pytest.mark.skipif(
    os.environ.get("CACAO_ACCOUNTING_DESKTOP", "").strip().lower() in {"1", "true", "yes", "on"},
    reason="Las tareas colaborativas no aplican en modo escritorio.",
)


def test_bandeja_y_panel_muestran_estado_y_prioridad_traducidos(app, authenticated_client, entorno_contable):
    """La tarea high/in_progress se presenta como High/In progress en ambos lugares."""
    del entorno_contable
    sufijo = uuid4().hex[:6]
    with app.app_context():
        admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
        orden = SalesOrder(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            status="open",
            document_no=f"SO-TASK-{sufijo}",
            customer_name="Cliente tarea",
        )
        database.session.add(orden)
        database.session.flush()
        tarea = DocumentTask(
            document_type="sales_order",
            document_id=orden.id,
            document_no=orden.document_no,
            company="cacao",
            title=f"Tarea {sufijo}",
            assigned_by=admin.id,
            assigned_to=admin.id,
            status="in_progress",
            priority="high",
        )
        database.session.add(tarea)
        database.session.commit()
        orden_id = orden.id
        tarea_id = tarea.id

    try:
        client = authenticated_client("admin")
        bandeja = client.get("/tasks/my")
        assert bandeja.status_code == 200
        cuerpo_bandeja = bandeja.get_data(as_text=True)
        assert "<td>alta</td>" in cuerpo_bandeja
        assert "<td>en curso</td>" in cuerpo_bandeja
        assert "<td>high</td>" not in cuerpo_bandeja
        assert "<td>in_progress</td>" not in cuerpo_bandeja

        from types import SimpleNamespace

        from flask import render_template_string
        from flask_login import login_user

        with app.test_request_context("/"):
            admin = database.session.execute(database.select(User).filter_by(user="admin")).scalar_one()
            login_user(admin)
            cuerpo_detalle = render_template_string(
                "{% import 'macros.html' as m %}{{ m.document_collaboration_panel('sales_order', document) }}",
                document=SimpleNamespace(id=orden_id, company="cacao", document_no=f"SO-TASK-{sufijo}"),
            )
        assert "<td>alta</td>" in cuerpo_detalle
        assert "<td>en curso</td>" in cuerpo_detalle
        assert "<td>high</td>" not in cuerpo_detalle
        assert "<td>in_progress</td>" not in cuerpo_detalle
    finally:
        with app.app_context():
            database.session.execute(database.delete(DocumentTask).where(DocumentTask.id == tarea_id))
            database.session.execute(database.delete(SalesOrder).where(SalesOrder.id == orden_id))
            database.session.commit()
