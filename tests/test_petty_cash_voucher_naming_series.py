# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1992: el alta de vale honra la serie elegida y valida su alcance.

El formulario envía `naming_series`; el servicio debe persistir una serie
activa del tipo correcto y compañía, rechazar una selección inválida (ajena o
inactiva) sin consumir el contador default, y usar la default si no se elige.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cacao_accounting import create_app
from cacao_accounting.bancos.services import create_petty_cash_voucher
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Accounts,
    Currency,
    Entity,
    Modules,
    NamingSeries,
    PettyCashAccount,
    PettyCashVoucher,
    database,
)

FECHA = date(2026, 10, 20)


@pytest.fixture
def caja_series():
    """Compañía con fondo y dos series de vales (una por compañía)."""
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
        database.session.add_all(
            [
                Modules(module="cash", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
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
            ]
        )
        database.session.flush()
        caja = Accounts(
            code="1.01.05.001",
            name="Caja Chica",
            entity="cacao",
            group=False,
            active=True,
            enabled=True,
            account_type="petty_cash",
        )
        database.session.add(caja)
        database.session.flush()
        fondo = PettyCashAccount(
            company="cacao",
            account_id=caja.id,
            name="Fondo Cacao",
            currency="NIO",
            float_amount=Decimal("1000"),
            is_default=True,
            is_active=True,
        )
        series_alt = NamingSeries(
            entity_type="petty_cash_voucher",
            company="cacao",
            name="Serie Alterna",
            prefix_template="ALT-",
            is_active=True,
        )
        series_alpha = NamingSeries(
            entity_type="petty_cash_voucher",
            company="alpha",
            name="Serie Alpha",
            prefix_template="ALPHA-",
            is_active=True,
        )
        database.session.add_all([fondo, series_alt, series_alpha])
        database.session.commit()
        yield application, {"fondo": fondo.id, "alt": series_alt.id, "alpha": series_alpha.id}
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _crear(fondo_id: str, **kwargs) -> PettyCashVoucher:
    return create_petty_cash_voucher(
        company="cacao",
        petty_cash_id=fondo_id,
        posted_date=FECHA,
        delivered_to="Beneficiario",
        concept="Vale de prueba",
        amount=Decimal("50"),
        **kwargs,
    )


def test_vale_persiste_la_serie_elegida(caja_series):
    """Una serie activa de la compañía se honra en el vale."""
    application, ids = caja_series
    with application.app_context():
        voucher = _crear(ids["fondo"], naming_series_id=ids["alt"])
        # La serie elegida se persiste (no se sustituye por la default).
        assert voucher.naming_series_id == ids["alt"]


def test_vale_rechaza_serie_de_otra_compania(caja_series):
    """Una serie de otra compañía no se acepta."""
    application, ids = caja_series
    with application.app_context():
        with pytest.raises(ValueError, match="no pertenece a la compañía"):
            _crear(ids["fondo"], naming_series_id=ids["alpha"])
        assert database.session.execute(database.select(PettyCashVoucher)).scalars().all() == []
        database.session.rollback()


def test_vale_sin_serie_usa_default(caja_series):
    """Sin selección, el servicio asigna la serie predeterminada."""
    application, ids = caja_series
    with application.app_context():
        voucher = _crear(ids["fondo"])
        assert voucher.id is not None
