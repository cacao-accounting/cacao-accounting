# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1733: la edición general de contadores externos conserva last_used."""

from cacao_accounting.database import ExternalCounter, ExternalCounterAuditLog, database


def _crear_contador(*, last_used: int = 10) -> str:
    """Crea un contador externo activo y devuelve su ID."""
    counter = ExternalCounter(company="cacao", name="Contador external", last_used=last_used, is_active=True)
    database.session.add(counter)
    database.session.commit()
    return counter.id


def _eliminar_contador(counter_id: str) -> None:
    """Retira el contador de prueba y sus registros asociados."""
    with database.session.begin_nested():
        counter = database.session.get(ExternalCounter, counter_id)
        if counter is not None:
            database.session.delete(counter)


def test_editar_contador_no_cambia_last_used_ni_registra_auditoria(app, authenticated_client):
    """El formulario general de edición conserva last_used fuera de su alcance (#1733)."""
    counter_id = _crear_contador()
    try:
        client = authenticated_client("admin")
        response = client.post(
            f"/accounting/external-counter/{counter_id}/edit",
            data={
                "company": "cacao",
                "nombre": "Contador external editado",
                "counter_type": "checkbook",
                "prefix": "CHK-",
                "last_used": "999",
                "padding": "5",
                "is_active": "true",
                "description": "",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        with app.app_context():
            counter = database.session.get(ExternalCounter, counter_id)
            assert counter is not None
            assert counter.name == "Contador external editado"
            assert counter.last_used == 10
            audit_rows = (
                database.session.execute(
                    database.select(ExternalCounterAuditLog).where(ExternalCounterAuditLog.external_counter_id == counter_id)
                )
                .scalars()
                .all()
            )
            assert audit_rows == []
    finally:
        with app.app_context():
            _eliminar_contador(counter_id)
            database.session.commit()


def test_ajuste_dedicado_registra_auditoria_y_cambia_last_used(app, authenticated_client):
    """El ajuste dedicado sigue registrando la traza y aplicando el cambio (#1733)."""
    counter_id = _crear_contador(last_used=10)
    try:
        client = authenticated_client("admin")
        response = client.post(
            f"/accounting/external-counter/{counter_id}/adjust",
            data={"new_last_used": "42", "reason": "Ajuste manual de prueba"},
            follow_redirects=True,
        )
        assert response.status_code == 200

        with app.app_context():
            counter = database.session.get(ExternalCounter, counter_id)
            assert counter is not None
            assert counter.last_used == 42
            audit_rows = (
                database.session.execute(
                    database.select(ExternalCounterAuditLog).where(ExternalCounterAuditLog.external_counter_id == counter_id)
                )
                .scalars()
                .all()
            )
            assert len(audit_rows) == 1
            assert audit_rows[0].previous_value == 10
            assert audit_rows[0].new_value == 42
            assert audit_rows[0].reason == "Ajuste manual de prueba"
    finally:
        with app.app_context():
            _eliminar_contador(counter_id)
            database.session.commit()
