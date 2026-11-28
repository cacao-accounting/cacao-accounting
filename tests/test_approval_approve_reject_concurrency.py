# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William JosǸ Moreno Reyes

"""#2076: aprobación y rechazo concurrentes no revive una solicitud rechazada."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from time import monotonic
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text

from cacao_accounting import create_app
from cacao_accounting.approval_engine import ApprovalEngine
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    ApprovalAction,
    ApprovalRequest,
    Currency,
    Entity,
    User,
    UserCompanyAccess,
    database,
)

pytestmark = pytest.mark.database


def _confirmar_espera_por_lock(app, pid: int, timeout: float) -> str:
    """Confirma en pg_stat_activity que la sesión indicada espera por el lock."""
    limite = monotonic() + timeout
    with app.app_context():
        while monotonic() < limite:
            espera = (
                database.session.execute(
                    text("SELECT wait_event_type, wait_event FROM pg_stat_activity WHERE pid = :pid"),
                    {"pid": pid},
                )
                .mappings()
                .first()
            )
            if espera is not None and espera["wait_event_type"] == "Lock":
                return str(espera["wait_event"])
            database.session.remove()
    pytest.fail(f"La sesión {pid} no esperó por el lock en {timeout} s.")
    return ""


def test_aprobacion_y_rechazo_concurrentes_dejan_un_solo_estado(monkeypatch):
    """El perdedor observa el rechazo confirmado y no publica efectos."""
    configured_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if not configured_uri.startswith("postgresql"):
        pytest.skip("Este caso requiere SELECT FOR UPDATE de PostgreSQL.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")

    app = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": configured_uri,
            "SQLALCHEMY_ENGINE_OPTIONS": {"pool_size": 4, "max_overflow": 0},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    suffix = uuid4().hex[:7].upper()
    company_code = f"A{suffix}"
    currency_code = f"C{suffix}"
    document_id = f"DOC-{suffix}"
    user_name = f"admin-{suffix.lower()}"

    with app.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code=currency_code, name="Prueba", decimals=2, active=True, default=False),
                Entity(
                    code=company_code,
                    name="Compañía aprobación",
                    company_name="Compañía aprobación SA",
                    tax_id=f"T{suffix}",
                    currency=currency_code,
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        user = User(
            user=user_name,
            name="Administrador de pruebas",
            password=b"unused-test-password",
            classification="admin",
            active=True,
            company=company_code,
        )
        database.session.add(user)
        database.session.flush()
        database.session.add(UserCompanyAccess(user_id=user.id, company_code=company_code))
        database.session.add(
            ApprovalRequest(
                document_type="sales_invoice",
                document_id=document_id,
                company_id=company_code,
                requested_by=user.id,
                current_level=1,
                required_level=1,
                status="Pending Approval",
            )
        )
        database.session.commit()
        user_id = user.id
        database.session.remove()

    documento = SimpleNamespace(id=document_id, company=company_code, document_type="sales_invoice")
    aprobador = SimpleNamespace(id=user_id)
    regla = SimpleNamespace(id=None, role_id=None, max_amount=None, approval_level=1)
    monkeypatch.setattr(ApprovalEngine, "is_enabled", classmethod(lambda *_args, **_kwargs: True))
    monkeypatch.setattr(ApprovalEngine, "can_approve", staticmethod(lambda *_args, **_kwargs: True))
    monkeypatch.setattr(ApprovalEngine, "_get_user_rules", classmethod(lambda *_args, **_kwargs: [regla]))
    monkeypatch.setattr(ApprovalEngine, "_find_applicable_rule", staticmethod(lambda *_args, **_kwargs: regla))
    monkeypatch.setattr(ApprovalEngine, "_lock_document", classmethod(lambda *_args, **_kwargs: None))
    monkeypatch.setattr(ApprovalEngine, "_finalize_approval", classmethod(lambda *_args, **_kwargs: True))

    real_pending = ApprovalEngine._pending_request
    primera_bloqueada = Event()
    liberar_primera = Event()
    segunda_en_lock = Event()
    pid_segundo: list[int] = []
    contador = 0
    guarda = Lock()

    def pending_instrumentado(cls, document, *, lock=False):
        """Retiene la primera transacción y registra el PID de la segunda."""
        nonlocal contador
        with guarda:
            contador += 1
            orden = contador
        if orden == 1:
            resultado = real_pending(document, lock=lock)
            primera_bloqueada.set()
            assert liberar_primera.wait(timeout=25)
            return resultado
        if orden == 2:
            pid = database.session.execute(text("SELECT pg_backend_pid()")).scalar_one()
            pid_segundo.append(int(pid))
            segunda_en_lock.set()
        return real_pending(document, lock=lock)

    monkeypatch.setattr(ApprovalEngine, "_pending_request", classmethod(pending_instrumentado))

    def rechazar() -> str:
        with app.app_context():
            try:
                ApprovalEngine.reject(documento, aprobador, "Rechazo ganador")
                database.session.commit()
                return "rejected"
            except ValueError:
                database.session.rollback()
                return "error"
            finally:
                database.session.remove()

    def aprobar() -> str:
        with app.app_context():
            try:
                ApprovalEngine.approve(documento, aprobador, "Aprobación perdedora")
                database.session.commit()
                return "approved"
            except ValueError as exc:
                database.session.rollback()
                return f"rechazada: {exc}"
            finally:
                database.session.remove()

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(rechazar)
            assert primera_bloqueada.wait(timeout=15)
            second = workers.submit(aprobar)
            assert segunda_en_lock.wait(timeout=15)
            wait_event = _confirmar_espera_por_lock(app, pid_segundo[0], timeout=15)
            assert wait_event
            liberar_primera.set()
            assert first.result(timeout=25) == "rejected"
            assert "rechazada" in second.result(timeout=25)

        with app.app_context():
            solicitudes = (
                database.session.execute(database.select(ApprovalRequest).filter_by(document_id=document_id)).scalars().all()
            )
            assert len(solicitudes) == 1
            assert solicitudes[0].status == "Rejected"
            acciones = (
                database.session.execute(
                    database.select(ApprovalAction)
                    .join(ApprovalRequest, ApprovalAction.approval_request_id == ApprovalRequest.id)
                    .where(ApprovalRequest.document_id == document_id)
                )
                .scalars()
                .all()
            )
            assert len(acciones) == 1
            assert acciones[0].action == "reject"
            database.session.remove()
    finally:
        liberar_primera.set()
        segunda_en_lock.set()
        with app.app_context():
            ids = (
                database.session.execute(database.select(ApprovalRequest.id).filter_by(document_id=document_id))
                .scalars()
                .all()
            )
            database.session.execute(database.delete(ApprovalAction).where(ApprovalAction.approval_request_id.in_(ids)))
            database.session.execute(database.delete(ApprovalRequest).filter_by(document_id=document_id))
            database.session.execute(database.delete(UserCompanyAccess).where(UserCompanyAccess.user_id == user_id))
            database.session.execute(database.delete(User).where(User.id == user_id))
            database.session.execute(database.delete(Entity).where(Entity.code == company_code))
            database.session.execute(database.delete(Currency).where(Currency.code == currency_code))
            database.session.commit()
            database.session.remove()
            database.engine.dispose()
