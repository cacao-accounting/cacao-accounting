# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La lista de recurrentes no anuncia una fecha que no calcula.

Escenario de negocio (issue #2156): la columna «Próxima Aplicación» leía
``next_application_date``, atributo inexistente en el modelo y nunca adjuntado
por la consulta. Siempre mostraba ``-``. Mientras no exista un contrato que
defina aplicaciones pendientes y reversas, la columna no debe presentarse.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Book,
    Currency,
    Entity,
    Modules,
    RecurringJournalTemplate,
    User,
    database,
)


def _crear_app():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add_all(
            [
                Modules(module="accounting", default=False, enabled=True),
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                    company="cacao",
                ),
            ]
        )
        database.session.flush()
        libro = Book(
            entity="cacao",
            code="DEFAULT_BOOK",
            name="Libro principal",
            status="activo",
            is_primary=True,
            currency="NIO",
        )
        database.session.add(libro)
        database.session.flush()
        database.session.add(
            RecurringJournalTemplate(
                code="REC-1",
                company="cacao",
                ledger_id=libro.id,
                name="Plantilla mensual",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 12, 31),
                frequency="monthly",
                status="approved",
            )
        )
        database.session.commit()
    return application


def test_la_lista_no_muestra_la_columna_sin_contrato():
    """La fila se conserva, pero no la columna con un valor siempre vacío."""
    application = _crear_app()
    try:
        client = application.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = "admin"
            session["_fresh"] = True

        respuesta = client.get("/accounting/journal/recurring")

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert "REC-1" in html
        assert "Próxima Aplicación" not in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
