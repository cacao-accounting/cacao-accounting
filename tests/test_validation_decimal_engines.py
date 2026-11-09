# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La huella decimal se mantiene estable en el motor real de DATABASE_URL.

Complemento de #2019: el CI de bases ejecuta este archivo con
``CHECK_DATABASE=true`` contra PostgreSQL y MySQL, verificando que la
coerción de escala del motor no altere el SHA256 del mismo importe.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting.printing.validation import (
    ValidationService,
    calculate_validation_hash,
    get_canonical_payload,
)

pytestmark = pytest.mark.database

FECHA = date(2026, 10, 15)


@pytest.fixture(scope="module")
def motor_real():
    """App apuntando a DATABASE_URL con esquema creado."""
    from cacao_accounting import create_app
    from cacao_accounting.config import configuracion
    from cacao_accounting.database import database

    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
        }
    )
    with application.app_context():
        database.create_all()
        yield application
        database.session.remove()
        database.engine.dispose()


def _hash(servicio, factura) -> str:
    return calculate_validation_hash(get_canonical_payload(servicio.extract_document_data(factura)))


def test_persistir_y_releer_conserva_la_huella(motor_real):
    """El mismo importe conserva payload y SHA256 tras la coerción del motor."""
    from cacao_accounting.database import Currency, Entity, SalesInvoice, database

    with motor_real.app_context():
        sufijo = "DECENG"
        moneda = Currency(code="TST", name="Moneda de prueba", decimals=2, active=True)
        entidad = Entity(
            code=sufijo,
            name="Entidad de prueba",
            company_name="Entidad de prueba",
            tax_id="J-TEST",
            currency="TST",
            enabled=True,
            status="activo",
        )
        database.session.add_all([moneda, entidad])
        database.session.flush()
        factura = SalesInvoice(
            company=sufijo,
            posting_date=FECHA,
            docstatus=1,
            document_no=f"{sufijo}-1",
            transaction_currency="TST",
            grand_total=Decimal("125.50"),
        )
        database.session.add(factura)
        database.session.commit()
        factura_id = factura.id

        servicio = ValidationService()
        antes = _hash(servicio, factura)

        database.session.expire_all()
        recargada = database.session.get(SalesInvoice, factura_id)
        assert recargada is not None
        despues = _hash(servicio, recargada)

        assert despues == antes
        assert get_canonical_payload(servicio.extract_document_data(recargada)) == get_canonical_payload(
            servicio.extract_document_data(factura)
        )

        database.session.delete(recargada)
        database.session.flush()
        database.session.delete(entidad)
        database.session.commit()

        # La moneda referenciada por la entidad debe borrarse en un segundo
        # commit: con FK RESTRICT el motor real no garantiza el orden si
        # ambos DELETE viajan en el mismo flush.
        database.session.delete(moneda)
        database.session.commit()
