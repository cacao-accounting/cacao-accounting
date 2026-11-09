# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Una regla fiscal inválida conserva los valores enviados.

Escenario de negocio (issue #2017): al fallar la validación, el formulario se
re-renderizaba con la fila persistida o con defaults; el resto de la propuesta
enviada desaparecía y en edición se mostraban los valores anteriores.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Modules,
    TaxRule,
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
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="admin", default=False, enabled=True),
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
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def _formulario(nombre: str) -> dict[str, str]:
    return {
        "name": nombre,
        "company": "cacao",
        "concept": "iva",
        "applies_to": "sales",
        "level": "transaction",
        "tax_type": "tax",
        "calculation_method": "percentage",
        "rate": "15",
        "amount": "0",
        "base_mode": "goods",
        "sequence": "10",
        "accounting_treatment": "separate_tax_account",
        "recognition_event": "invoice",
        "account_id": "NO-EXIST",
        "currency": "NIO",
        "country": "NI",
        "allocation_method": "by_amount",
        "affects_inventory": "on",
        "affects_document_total": "on",
        "is_active": "on",
    }


def test_el_alta_invalida_conserva_la_propuesta():
    """El nombre, país y demás campos enviados vuelven a mostrarse."""
    application = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post("/settings/tax-rules", data=_formulario("Propuesta fiscal"))

        assert respuesta.status_code == 200
        html = respuesta.get_data(as_text=True)
        assert "Propuesta fiscal" in html
        assert 'value="NI"' in html
        assert "La cuenta contable de la regla fiscal no existe." in html
        with application.app_context():
            assert database.session.execute(database.select(TaxRule)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_la_edicion_invalida_muestra_lo_enviado_y_no_muta_la_fila():
    """La edición rechazada conserva la propuesta, no los valores persistidos."""
    application = _crear_app()
    try:
        with application.app_context():
            regla = TaxRule(
                company="cacao",
                name="Original",
                concept="iva",
                applies_to="sales",
                level="transaction",
                tax_type="tax",
                calculation_method="percentage",
                rate=15,
                base_mode="goods",
                sequence=10,
                accounting_treatment="separate_tax_account",
                recognition_event="invoice",
                is_active=True,
            )
            database.session.add(regla)
            database.session.commit()
            rule_id = regla.id

        client = _cliente(application)
        respuesta = client.post(f"/settings/tax-rules/{rule_id}/edit", data=_formulario("Cambio propuesto"))

        assert respuesta.status_code == 200
        assert "Cambio propuesto" in respuesta.get_data(as_text=True)
        with application.app_context():
            registro = database.session.get(TaxRule, rule_id)
            assert registro.name == "Original"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
