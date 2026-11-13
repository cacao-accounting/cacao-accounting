# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Confinamiento del cierre operativo y del cierre de año fiscal.

Escenario de negocio (issue #1024): el año fiscal cerrado administrativamente
bloquea toda operación salvo el asiento de cierre de año fiscal, y el
período cerrado admite únicamente comprobantes de cierre operativo.
``allow_closing`` no debe desbloquear el año completo.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database

AÑO_CERRADO = date.today().year - 1


@pytest.fixture
def empresa_con_año_cerrado():
    """Aplicación con un año fiscal cerrado, período cerrado y período habilitado abierto."""
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
        from cacao_accounting.database import AccountingPeriod, Currency, Entity, FiscalYear

        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Entity(
                    code="cacao",
                    name="Cacao Accounting",
                    company_name="Cacao Accounting SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                FiscalYear(
                    entity="cacao",
                    name=f"AF{AÑO_CERRADO}",
                    year_start_date=date(AÑO_CERRADO, 1, 1),
                    year_end_date=date(AÑO_CERRADO, 12, 31),
                    is_closed=True,
                    financial_closed=False,
                ),
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                AccountingPeriod(
                    entity="cacao",
                    name=f"{AÑO_CERRADO}-12",
                    start=date(AÑO_CERRADO, 12, 1),
                    end=date(AÑO_CERRADO, 12, 31),
                    is_closed=True,
                    enabled=True,
                    status="open",
                ),
                AccountingPeriod(
                    entity="cacao",
                    name=f"{date.today().year}-01",
                    start=date(date.today().year, 1, 1),
                    end=date(date.today().year, 12, 31),
                    is_closed=False,
                    enabled=True,
                    status="open",
                ),
                AccountingPeriod(
                    entity="cacao",
                    name="PERIODO-CERRADO-AÑO-ABIERTO",
                    start=date(date.today().year, date.today().month, 1) - timedelta(days=5),
                    end=date(date.today().year, date.today().month, 1) - timedelta(days=1),
                    is_closed=True,
                    enabled=True,
                    status="closed",
                ),
            ]
        )
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_año_fiscal_cerrado_bloquea_movimientos_normales(empresa_con_año_cerrado):
    """Un documento operativo no publica dentro del año fiscal cerrado."""
    application = empresa_con_año_cerrado
    with application.app_context():
        from cacao_accounting.document_identifiers import IdentifierConfigurationError, validate_accounting_period

        with pytest.raises(IdentifierConfigurationError):
            validate_accounting_period("cacao", date(AÑO_CERRADO, 7, 15))


def test_allow_closing_no_desbloquea_el_año_fiscal_cerrado(empresa_con_año_cerrado):
    """Regresión del issue: allow_closing ya no entra al año fiscal sellado."""
    application = empresa_con_año_cerrado
    with application.app_context():
        from cacao_accounting.document_identifiers import IdentifierConfigurationError, validate_accounting_period

        with pytest.raises(IdentifierConfigurationError):
            validate_accounting_period("cacao", date(AÑO_CERRADO, 7, 15), allow_closing=True)


def test_el_asiento_de_cierre_de_año_numeracion_dentro_del_año_sellado(empresa_con_año_cerrado):
    """Solo el servicio de cierre (allow_fiscal_year_closing) publica en el año cerrado."""
    application = empresa_con_año_cerrado
    with application.app_context():
        from cacao_accounting.document_identifiers import validate_accounting_period

        validate_accounting_period("cacao", date(AÑO_CERRADO, 7, 15), allow_fiscal_year_closing=True)


def test_periodo_cerrado_admite_solo_comprobantes_de_cierre(empresa_con_año_cerrado):
    """El comportamiento histórico del cierre operativo de período se conserva.

    Dentro de un año fiscal abierto, un período cerrado queda bloqueado para
    operaciones normales y admite únicamente comprobantes de cierre.
    """
    application = empresa_con_año_cerrado
    with application.app_context():
        from cacao_accounting.document_identifiers import IdentifierConfigurationError, validate_accounting_period

        fecha_periodo_cerrado = date(date.today().year, date.today().month, 1) - timedelta(days=3)
        # Año abierto administrativamente: el período cerrado bloquea operaciones normales...
        assert validate_accounting_period("cacao", fecha_periodo_cerrado, allow_closing=True) is None
        with pytest.raises(IdentifierConfigurationError):
            validate_accounting_period("cacao", fecha_periodo_cerrado)
        # ...y dentro del año cerrado, incluso el cierre operativo queda bloqueado
        # salvo el asiento de cierre de año.
        with pytest.raises(IdentifierConfigurationError):
            validate_accounting_period("cacao", date(AÑO_CERRADO, 12, 15), allow_closing=True)


def test_numeracion_del_comprobante_de_cierre_de_año_ocurre_dentro_del_año_sellado(empresa_con_año_cerrado):
    """El voucher de cierre se numera en el año cerrado vía su bandera exclusiva."""
    application = empresa_con_año_cerrado
    with application.app_context():
        from cacao_accounting.contabilidad.journal_service import _assign_identifier_if_needed
        from cacao_accounting.database import ComprobanteContable

        journal = ComprobanteContable(
            entity="cacao",
            date=date(AÑO_CERRADO, 12, 31),
            is_closing=True,
            is_fiscal_year_closing=True,
        )
        database.session.add(journal)
        database.session.flush()
        _assign_identifier_if_needed(journal, naming_series_id=None)
        assert journal.document_no, "El asiento de cierre debe numerarse dentro del año fiscal que cierra."


def test_comprobante_manual_no_se_numerar_en_año_fiscal_cerrado(empresa_con_año_cerrado):
    """Un comprobante manual retroactivo queda fuera del año sellado."""
    application = empresa_con_año_cerrado
    with application.app_context():
        from cacao_accounting.contabilidad.journal_service import _assign_identifier_if_needed
        from cacao_accounting.database import ComprobanteContable

        journal = ComprobanteContable(entity="cacao", date=date(AÑO_CERRADO, 7, 1), is_closing=False)
        database.session.add(journal)
        database.session.flush()
        _assign_identifier_if_needed(journal, naming_series_id=None)
        assert not journal.document_no, "El comprobante manual no debe numerar en el año fiscal cerrado."
