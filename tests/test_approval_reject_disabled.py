# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Rechazar una solicitud vigente funciona aunque el motor se deshabilite.

Escenario de negocio (issue #2008): si el motor se desactivaba con solicitudes
abiertas, ``reject`` retornaba sin transición y la ruta reportaba éxito; la
solicitud seguía Pending Approval y sin ApprovalAction.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.approval_engine import ApprovalEngine
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    ApprovalAction,
    ApprovalRequest,
    Entity,
    Modules,
    SalesInvoice,
    User,
    database,
)

FECHA = date(2026, 10, 15)


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
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        documento = SalesInvoice(
            company="cacao",
            posting_date=FECHA,
            docstatus=0,
            document_no="INV-APPROVAL",
            transaction_currency="NIO",
            grand_total=100,
        )
        database.session.add_all(
            [
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                Modules(module="sales", default=False, enabled=True),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                documento,
            ]
        )
        database.session.flush()
        database.session.add(
            ApprovalRequest(
                document_type="sales_invoice",
                document_id=documento.id,
                company_id="cacao",
                requested_by="admin",
                current_level=1,
                required_level=1,
                status="Pending Approval",
            )
        )
        database.session.commit()
        return application, documento.id


def test_rechaza_una_solicitud_pendiente_con_motor_deshabilitado():
    """La solicitud transiciona y registra la acción sin importar el flag."""
    application, invoice_id = _crear_app()
    try:
        with application.app_context():
            documento = database.session.get(SalesInvoice, invoice_id)
            admin = database.session.get(User, "admin")
            assert not ApprovalEngine.is_enabled("cacao")

            ApprovalEngine.reject(documento, admin, "Motivo de rechazo")
            database.session.commit()

            solicitud = database.session.execute(database.select(ApprovalRequest)).scalar_one()
            assert solicitud.status == "Rejected"
            accion = database.session.execute(database.select(ApprovalAction)).scalar_one()
            assert accion.action == "reject"
            assert accion.approved_by == "admin"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_sin_solicitud_y_motor_deshabilitado_no_hace_nada():
    """El no-op se conserva cuando no hay una solicitud vigente."""
    application, invoice_id = _crear_app()
    try:
        with application.app_context():
            database.session.delete(database.session.execute(database.select(ApprovalRequest)).scalar_one())
            database.session.commit()
            documento = database.session.get(SalesInvoice, invoice_id)
            admin = database.session.get(User, "admin")

            ApprovalEngine.reject(documento, admin, "sin solicitud")

            assert database.session.execute(database.select(ApprovalAction)).scalars().all() == []
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
