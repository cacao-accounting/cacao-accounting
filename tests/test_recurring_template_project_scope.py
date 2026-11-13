# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Alcance de proyecto en plantillas de comprobantes recurrentes.

Escenario de negocio: una plantilla de ``cacao`` no puede referenciar el
proyecto ``A-SECRET`` de ``alpha``. El selector del navegador filtra, pero el
servicio debe rechazar el payload manipulado antes de persistir la línea.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad.recurring_journal_service import (
    RecurringJournalError,
    create_recurring_template,
)
from cacao_accounting.database import (
    Accounts,
    Book,
    Currency,
    Entity,
    Modules,
    Project,
    RecurringJournalItem,
    RecurringJournalTemplate,
    User,
    database,
)

FECHA = date(2026, 1, 1)


@pytest.fixture
def plantillas_recurrentes():
    """Dos compañías con proyectos homónimos y una cuenta en cacao."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
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
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J0002",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.flush()
        database.session.add(
            Book(
                entity="cacao",
                code="LOCAL",
                name="Principal",
                status="activo",
                currency="NIO",
                default=True,
                is_primary=True,
            )
        )
        database.session.add(
            Accounts(
                code="1000",
                name="Caja",
                entity="cacao",
                group=False,
                active=True,
                enabled=True,
                account_type="asset",
            )
        )
        database.session.add_all(
            [
                Project(entity="cacao", code="P-CACAO", name="Proyecto Cacao", enabled=True),
                Project(entity="alpha", code="P-ALPHA", name="Proyecto Alpha", enabled=True),
            ]
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _datos():
    return {
        "code": "REC-1",
        "company": "cacao",
        "name": "Plantilla mensual",
        "start_date": FECHA,
        "end_date": date(2026, 12, 31),
        "frequency": "monthly",
        "currency": "NIO",
    }


def _lineas(project: str):
    return [
        {
            "account_code": "1000",
            "debit": Decimal("100"),
            "credit": Decimal("0"),
            "description": "Cargo",
            "project": project,
        },
        {
            "account_code": "1000",
            "debit": Decimal("0"),
            "credit": Decimal("100"),
            "description": "Abono",
        },
    ]


def test_plantilla_rechaza_proyecto_de_otra_compania(plantillas_recurrentes):
    """El proyecto ajeno no se persiste en la línea de la plantilla."""
    application = plantillas_recurrentes
    with application.app_context():
        with pytest.raises(RecurringJournalError, match="no pertenece"):
            create_recurring_template(_datos(), _lineas("P-ALPHA"), "admin")
        assert database.session.execute(database.select(RecurringJournalTemplate)).scalars().all() == []


def test_plantilla_acepta_proyecto_de_su_compania(plantillas_recurrentes):
    """Control positivo: el proyecto de cacao se conserva en la línea."""
    application = plantillas_recurrentes
    with application.app_context():
        template = create_recurring_template(_datos(), _lineas("P-CACAO"), "admin")
        item = (
            database.session.execute(database.select(RecurringJournalItem).filter_by(template_id=template.id))
            .scalars()
            .first()
        )
        assert template.company == "cacao"
        assert item.project == "P-CACAO"
