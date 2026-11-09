# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Listas de caja comparten estado vacío y paginación por endpoint.

Escenario de negocio (issues #2041 y #2042): ``pago_lista.html`` dejaba el
cuerpo vacío sin mensaje y paginaba siempre hacia ``payment/list``. Las notas
de débito/crédito y las transferencias perdían su ruta especializada al pasar
a la página siguiente.
"""

from __future__ import annotations

import re
from datetime import date

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Entity, Modules, PaymentEntry, User, database

RUTAS_VACIAS = (
    "/cash_management/payment/list",
    "/cash_management/transfer/list",
    "/cash_management/payment/debit-note/list",
    "/cash_management/payment/credit-note/list",
)

PAGINACION = (
    ("/cash_management/transfer/list", "internal_transfer", "/cash_management/transfer/list"),
    ("/cash_management/payment/debit-note/list", "debit_note", "/cash_management/payment/debit-note/list"),
    ("/cash_management/payment/credit-note/list", "credit_note", "/cash_management/payment/credit-note/list"),
)


def _crear_app(payment_type: str | None = None, cantidad: int = 0):
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
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="cash", default=False, enabled=True),
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
                ),
            ]
        )
        if payment_type:
            for indice in range(cantidad):
                database.session.add(
                    PaymentEntry(
                        company="cacao",
                        payment_type=payment_type,
                        posting_date=date.today(),
                        docstatus=0,
                        document_no=f"{payment_type}-{indice}",
                    )
                )
        database.session.commit()
    return application


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def _cerrar(application) -> None:
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_las_listas_vacias_muestran_estado_y_paginacion_coherente():
    """Las cuatro rutas informan la ausencia de filas."""
    application = _crear_app()
    try:
        client = _cliente(application)
        for ruta in RUTAS_VACIAS:
            respuesta = client.get(ruta)
            html = respuesta.get_data(as_text=True)
            assert respuesta.status_code == 200
            assert "No se encontraron documentos para los filtros seleccionados." in html
            assert "Página 1 de 0" not in html
    finally:
        _cerrar(application)


def test_la_paginacion_conserva_el_endpoint_especializado():
    """El enlace Siguiente regresa a la lista de origen, no a pagos."""
    for ruta, payment_type, endpoint in PAGINACION:
        application = _crear_app(payment_type=payment_type, cantidad=11)
        try:
            client = _cliente(application)
            html = client.get(ruta).get_data(as_text=True)

            siguiente = re.search(r'href="([^"]+)"[^>]*>\s*Siguiente', html)
            assert siguiente is not None, ruta
            assert siguiente.group(1).startswith(endpoint), (ruta, siguiente.group(1))
        finally:
            _cerrar(application)
