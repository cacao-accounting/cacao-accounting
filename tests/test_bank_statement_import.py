# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Importación de extractos bancarios: interpretación de importes.

Escenario de negocio (issue #1030): un extracto con notación de miles
europea (``1.000``) no debe persistir importes mil veces menores, y la
notación americana sin decimales (``1,000``) no debe abortar la
importación mientras su par europeo entra corrupta. Los importes
ambiguos se rechazan de forma simétrica y explícita; las formas
inequívocas (``1.234,56``, ``1,234.56``) se interpretan.
"""

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import database

FECHA_EXTRACTO = "2026-10-15"


@pytest.fixture
def extracto_bancario():
    """Aplicación con una cuenta bancaria lista para importar extractos."""
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
        from cacao_accounting.database import Bank, BankAccount, Currency, Entity

        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add(
            Entity(
                code="cacao",
                name="Cacao",
                company_name="Cacao SA",
                tax_id="J0001",
                currency="NIO",
                enabled=True,
                status="default",
            )
        )
        database.session.flush()

        banco = Bank(name="Banco Nacional de Desarrollo", swift_code="BNDENI2N", is_active=True)
        database.session.add(banco)
        database.session.flush()
        cuenta = BankAccount(
            company="cacao",
            bank_id=banco.id,
            account_name="Cuenta Corriente Principal",
            account_no="XXXX-0102",
            is_active=True,
        )
        database.session.add(cuenta)
        database.session.commit()
    yield application
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _fila(application, deposito: str | None = None, retiro: str | None = None) -> dict:
    from cacao_accounting.database import BankAccount

    with application.app_context():
        cuenta = database.session.query(BankAccount).first()
    return {
        "bank_account_id": cuenta.id,
        "posting_date": FECHA_EXTRACTO,
        "reference_number": "BD-1030",
        "description": "Movimiento de extracto",
        "deposit": deposito,
        "withdrawal": retiro,
    }


def _validar(application, fila) -> list[str]:
    with application.app_context():
        from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter

        return BankStatementAdapter().validate_row(fila)


def _monto_documento(application, fila) -> float:
    with application.app_context():
        from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter

        transaccion = BankStatementAdapter().build_document([fila], context={})[0]
    return float(transaccion["deposit"] if transaccion["deposit"] else transaccion["withdrawal"])


def test_notacion_europea_de_miles_se_rechaza_en_lugar_de_corromperse(extracto_bancario):
    """El hallazgo del issue: '1.000' no persiste un importe 1000x menor."""
    application = extracto_bancario
    errores = _validar(application, _fila(application, deposito="1.000"))
    assert any("Separador de miles ambiguo" in error for error in errores)


def test_notacion_americana_de_miles_se_rechaza_igual_que_la_europea(extracto_bancario):
    """La simetría pedida en el issue: '1,000' es tan ambiguo como '1.000'."""
    application = extracto_bancario
    errores = _validar(application, _fila(application, retiro="1,000"))
    assert any("Separador de miles ambiguo" in error for error in errores)


def test_notacion_de_miles_con_multiples_separadores_se_rechaza(extracto_bancario):
    """Tanto '1.234.567' como '1,234,567' son ambiguos sin convención declarada."""
    application = extracto_bancario
    assert any("ambiguo" in error for error in _validar(application, _fila(application, deposito="1.234.567")))
    assert any("ambiguo" in error for error in _validar(application, _fila(application, retiro="1,234,567")))


def test_importes_inequivocos_se_interpretan_correctamente(extracto_bancario):
    """Las formas no ambiguas de ambas convenciones se identifican sin error."""
    application = extracto_bancario
    for importe in ("1.234,56", "1,234.56"):
        assert _validar(application, _fila(application, deposito=importe)) == []
        assert _monto_documento(application, _fila(application, deposito=importe)) == 1234.56
    assert _monto_documento(application, _fila(application, retiro="999.99")) == 999.99


def test_importes_sin_separadores_y_decimales_normales_se_aceptan(extracto_bancario):
    """Montos planos y decimales no ambiguos de cualquier convención siguen funcionando."""
    application = extracto_bancario
    assert _monto_documento(application, _fila(application, deposito="1000")) == 1000
    assert _monto_documento(application, _fila(application, deposito="1234.57")) == 1234.57
    assert _monto_documento(application, _fila(application, deposito="12,34")) == 12.34
    assert _monto_documento(application, _fila(application, deposito="123.4567")) == 123.4567


def test_extracto_rechaza_filas_sin_lados_y_con_doble_lado(extracto_bancario):
    """Reglas de negocio del extracto independientes de la notación."""
    application = extracto_bancario
    sin_lados = _validar(application, _fila(application))
    assert any("depósito o un retiro" in error for error in sin_lados)
    doble = _validar(application, _fila(application, deposito="10", retiro="10"))
    assert any("simultáneamente" in error for error in doble)


def test_extracto_rechaza_importes_negativos_en_ambas_columnas(extracto_bancario):
    """Un depósito o retiro negativo no se descarta en silencio."""
    application = extracto_bancario
    for fila in (_fila(application, deposito="-10"), _fila(application, retiro="-10")):
        errores = _validar(application, fila)
        assert any("no puede ser negativo" in error for error in errores)


def test_documento_bancario_rechaza_negativos_sin_validacion_previa(extracto_bancario):
    """La construcción directa del documento tampoco admite importes negativos."""
    application = extracto_bancario
    with application.app_context():
        from cacao_accounting.imports.adapters.bank_statement import BankStatementAdapter

        adapter = BankStatementAdapter()
        with pytest.raises(ValueError, match="negativo"):
            adapter.build_document([_fila(application, deposito="-10")], context={})
        with pytest.raises(ValueError, match="negativo"):
            adapter.build_document([_fila(application, retiro="-10")], context={})
