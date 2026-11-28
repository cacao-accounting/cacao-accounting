# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2281: cada decisión actúa únicamente sobre la solicitud enviada."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Event, Lock
from time import monotonic
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text

from cacao_accounting import create_app
from cacao_accounting.approval_engine import ApprovalEngine
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    ApprovalAction,
    ApprovalMatrix,
    ApprovalRequest,
    CacaoConfig,
    Currency,
    Entity,
    Modules,
    PurchaseRequest,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

CLAVE = "aprobaciones-identidad-2026"


@pytest.fixture
def bandeja_identidad():
    """Cloud con una solicitud terminal y otra pendiente sobre el mismo documento."""
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
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="purchases", default=False, enabled=True),
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha SA",
                    tax_id="J-IDENTIDAD",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="aprobador",
                    user="aprobador",
                    name="Aprobador",
                    password=proteger_passwd(CLAVE),
                    active=True,
                ),
                UserCompanyAccess(user_id="aprobador", company_code="alpha"),
                CacaoConfig(key="approval_engine_enabled_alpha", value="1"),
            ]
        )
        database.session.flush()
        modulo = database.session.execute(database.select(Modules.id).filter_by(module="purchases")).scalar_one()
        rol = Roles(name="sales-approver-identity", note="Aprobador de compras")
        database.session.add(rol)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(
                    rol_id=rol.id,
                    module_id=modulo,
                    access=True,
                    view=True,
                    approve=True,
                    approval_rank=1,
                ),
                RolesUser(user_id="aprobador", role_id=rol.id, active=True),
                ApprovalMatrix(
                    company_id="alpha",
                    document_type="purchase_request",
                    role_id=rol.id,
                    min_amount=Decimal("0"),
                    max_amount=Decimal("100"),
                    approval_level=1,
                    enabled=True,
                ),
            ]
        )
        documento = PurchaseRequest(
            company="alpha",
            posting_date=date(2026, 11, 24),
            document_date=date(2026, 11, 24),
            document_no="SR-IDENTIDAD",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            total=Decimal("50"),
            base_total=Decimal("50"),
            grand_total=Decimal("50"),
        )
        database.session.add(documento)
        database.session.flush()
        database.session.add_all(
            [
                ApprovalRequest(
                    document_type="purchase_request",
                    document_id=documento.id,
                    company_id="alpha",
                    requested_by="aprobador",
                    current_level=2,
                    required_level=2,
                    status="Approved",
                ),
                ApprovalRequest(
                    document_type="cancel_purchase_request",
                    document_id=documento.id,
                    company_id="alpha",
                    requested_by="aprobador",
                    current_level=1,
                    required_level=2,
                    status="Pending Approval",
                ),
            ]
        )
        database.session.commit()
        ids = {row.document_type: row.id for row in database.session.execute(database.select(ApprovalRequest)).scalars().all()}
        yield application, documento.id, ids["purchase_request"], ids["cancel_purchase_request"]
        database.session.remove()
        database.engine.dispose()


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "aprobador"
        session["_fresh"] = True
    return client


def _enviar(application, request_id: str, action: str = "approve"):
    response = _cliente(application).post(
        "/me/pending-approvals",
        data={"request_id": request_id, "action": action, "comments": "Desde bandeja"},
        follow_redirects=True,
    )
    return response.get_data(as_text=True)


def _estado(application, request_id: str) -> tuple[str, int]:
    with application.app_context():
        req = database.session.get(ApprovalRequest, request_id)
        return str(req.status), int(req.current_level)


def _acciones(application, request_id: str) -> int:
    with application.app_context():
        return len(
            database.session.execute(database.select(ApprovalAction).filter_by(approval_request_id=request_id)).scalars().all()
        )


def _docstatus(application, documento_id: str) -> int:
    with application.app_context():
        documento = database.session.get(PurchaseRequest, documento_id)
        return int(documento.docstatus)


def test_solicitud_terminal_no_aprueba_la_siguiente(bandeja_identidad):
    """Un formulario viejo no puede aprobar la solicitud posterior del documento."""
    application, documento_id, terminal_id, pendiente_id = bandeja_identidad

    cuerpo = _enviar(application, terminal_id)

    assert "no está pendiente" in cuerpo
    assert _estado(application, pendiente_id) == ("Pending Approval", 1)
    assert _estado(application, terminal_id) == ("Approved", 2)
    assert _acciones(application, pendiente_id) == 0
    assert _acciones(application, terminal_id) == 0
    assert _docstatus(application, documento_id) == 0


def test_solicitud_rechazada_no_hereda_el_exito_historico(bandeja_identidad):
    """La búsqueda de una aprobación antigua no comunica éxito sobre un rechazo."""
    application, documento_id, terminal_id, pendiente_id = bandeja_identidad
    with application.app_context():
        pendiente = database.session.get(ApprovalRequest, pendiente_id)
        pendiente.status = "Rejected"
        pendiente.document_type = "purchase_request"
        database.session.commit()

    cuerpo = _enviar(application, pendiente_id)

    assert "no está pendiente" in cuerpo
    assert _estado(application, pendiente_id) == ("Rejected", 1)
    assert _estado(application, terminal_id) == ("Approved", 2)
    assert _acciones(application, pendiente_id) == 0
    assert _acciones(application, terminal_id) == 0
    assert _docstatus(application, documento_id) == 0


def test_solicitud_pendiente_seleccionada_avanza_su_nivel(bandeja_identidad):
    """La solicitud válida avanza aunque exista una aprobación histórica anterior."""
    application, documento_id, terminal_id, pendiente_id = bandeja_identidad

    cuerpo = _enviar(application, pendiente_id)

    assert "no cumple" not in cuerpo
    assert _estado(application, pendiente_id) == ("Pending Approval", 2)
    assert _estado(application, terminal_id) == ("Approved", 2)
    assert _acciones(application, pendiente_id) == 1
    assert _docstatus(application, documento_id) == 0


def test_el_motor_rechaza_una_solicitud_de_otro_documento(bandeja_identidad):
    """La identidad del documento se valida junto con la de la solicitud."""
    application, documento_id, terminal_id, _pendiente_id = bandeja_identidad
    with application.app_context():
        otro = PurchaseRequest(
            company="alpha",
            posting_date=date(2026, 11, 24),
            document_no="SR-OTRO",
            transaction_currency="NIO",
            base_currency="NIO",
            exchange_rate=Decimal("1"),
            grand_total=Decimal("20"),
        )
        database.session.add(otro)
        database.session.flush()
        ajena = ApprovalRequest(
            document_type="purchase_request",
            document_id=otro.id,
            company_id="alpha",
            requested_by="aprobador",
            required_level=2,
            status="Pending Approval",
        )
        database.session.add(ajena)
        database.session.commit()
        ajena_id = ajena.id
        propio = database.session.get(PurchaseRequest, documento_id)
        aprobador = database.session.get(User, "aprobador")
        solicitud = database.session.get(ApprovalRequest, terminal_id)
        solicitud.status = "Pending Approval"
        database.session.commit()

        with pytest.raises(ValueError, match="no está pendiente"):
            ApprovalEngine.approve(propio, aprobador, request=ajena)

    assert _estado(application, ajena_id) == ("Pending Approval", 1)


def _confirmar_espera_por_lock(application, pid: int, timeout: float) -> str:
    """Confirma en pg_stat_activity que la segunda sesión espera el lock."""
    limite = monotonic() + timeout
    with application.app_context():
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


@pytest.mark.database
def test_dos_decisiones_sobre_la_misma_solicitud_serializan_el_resultado(monkeypatch):
    """#2281: en PostgreSQL el rechazo gana y la aprobación ve la fila ya terminal."""
    configured_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if not configured_uri.startswith("postgresql"):
        pytest.skip("Este caso requiere SELECT FOR UPDATE de PostgreSQL.")
    if os.environ.get("CHECK_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        pytest.skip("Los motores externos requieren CHECK_DATABASE=true.")

    application = create_app(
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
    sufijo = uuid4().hex[:7].upper()
    compania = f"A{sufijo}"
    moneda = f"C{sufijo}"
    documento_id = f"DOC-{sufijo}"
    usuario_nombre = f"aprobador-{sufijo.lower()}"

    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code=moneda, name="Prueba", decimals=2, active=True, default=False),
                Entity(
                    code=compania,
                    name="Compañía aprobación",
                    company_name="Compañía aprobación SA",
                    tax_id=f"T{sufijo}",
                    currency=moneda,
                    enabled=True,
                    status="default",
                ),
            ]
        )
        database.session.flush()
        usuario = User(
            user=usuario_nombre,
            name="Aprobador de pruebas",
            password=b"unused-test-password",
            classification="admin",
            active=True,
            company=compania,
        )
        database.session.add(usuario)
        database.session.flush()
        database.session.add(UserCompanyAccess(user_id=usuario.id, company_code=compania))
        database.session.add(
            ApprovalRequest(
                document_type="purchase_request",
                document_id=documento_id,
                company_id=compania,
                requested_by=usuario.id,
                current_level=1,
                required_level=1,
                status="Pending Approval",
            )
        )
        database.session.commit()
        usuario_id = usuario.id
        solicitud_id = database.session.execute(
            database.select(ApprovalRequest.id).filter_by(document_id=documento_id)
        ).scalar_one()
        database.session.remove()

    documento = SimpleNamespace(id=documento_id, company=compania, document_type="purchase_request")
    aprobador = SimpleNamespace(id=usuario_id)
    regla = SimpleNamespace(id=None, role_id=None, max_amount=None, approval_level=1)
    monkeypatch.setattr(ApprovalEngine, "is_enabled", classmethod(lambda *_args, **_kwargs: True))
    monkeypatch.setattr(ApprovalEngine, "can_approve", classmethod(lambda *_args, **_kwargs: True))
    monkeypatch.setattr(ApprovalEngine, "_get_user_rules", classmethod(lambda *_args, **_kwargs: [regla]))
    monkeypatch.setattr(ApprovalEngine, "_find_applicable_rule", staticmethod(lambda *_args, **_kwargs: regla))
    monkeypatch.setattr(ApprovalEngine, "_finalize_approval", classmethod(lambda *_args, **_kwargs: True))

    real_request_for_action = ApprovalEngine._request_for_action
    primera_bloqueada = Event()
    liberar_primera = Event()
    segunda_en_lock = Event()
    pid_segundo: list[int] = []
    contador = 0
    guarda = Lock()

    def solicitud_instrumentada(cls, document, submitted):
        """Retiene la primera transacción y registra el PID de la segunda."""
        nonlocal contador
        with guarda:
            contador += 1
            orden = contador
        if orden == 1:
            resultado = real_request_for_action(document, submitted)
            primera_bloqueada.set()
            assert liberar_primera.wait(timeout=60)
            return resultado
        if orden == 2:
            pid_segundo.append(int(database.session.execute(text("SELECT pg_backend_pid()")).scalar_one()))
            segunda_en_lock.set()
        return real_request_for_action(document, submitted)

    monkeypatch.setattr(ApprovalEngine, "_request_for_action", classmethod(solicitud_instrumentada))

    def rechazar() -> str:
        with application.app_context():
            try:
                solicitud = database.session.get(ApprovalRequest, solicitud_id)
                ApprovalEngine.reject(documento, aprobador, "Rechazo ganador", request=solicitud)
                database.session.commit()
                return "rejected"
            except ValueError:
                database.session.rollback()
                return "error"
            except Exception as exc:  # pragma: no cover - diagnóstico de motor externo
                database.session.rollback()
                return f"error inesperado: {type(exc).__name__}: {exc}"
            finally:
                database.session.remove()

    def aprobar() -> str:
        with application.app_context():
            try:
                solicitud = database.session.get(ApprovalRequest, solicitud_id)
                ApprovalEngine.approve(documento, aprobador, "Aprobación perdedora", request=solicitud)
                database.session.commit()
                return "approved"
            except ValueError:
                database.session.rollback()
                return "error"
            except Exception as exc:  # pragma: no cover - diagnóstico de motor externo
                database.session.rollback()
                return f"error inesperado: {type(exc).__name__}: {exc}"
            finally:
                database.session.remove()

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(rechazar)
            if not primera_bloqueada.wait(timeout=45):
                pytest.fail(f"La primera decisión no tomó el lock: {first.result(timeout=60)}")
            second = workers.submit(aprobar)
            if not segunda_en_lock.wait(timeout=45):
                pytest.fail(f"La segunda decisión no tomó el lock: {second.result(timeout=60)}")
            assert _confirmar_espera_por_lock(application, pid_segundo[0], timeout=45)
            liberar_primera.set()
            assert first.result(timeout=60) == "rejected"
            assert second.result(timeout=60) == "error"

        with application.app_context():
            solicitud = database.session.get(ApprovalRequest, solicitud_id)
            assert solicitud.status == "Rejected"
            acciones = (
                database.session.execute(database.select(ApprovalAction).filter_by(approval_request_id=solicitud_id))
                .scalars()
                .all()
            )
            assert len(acciones) == 1
            assert acciones[0].action == "reject"
            database.session.remove()
    finally:
        liberar_primera.set()
        segunda_en_lock.set()
        with application.app_context():
            database.session.execute(database.delete(ApprovalAction).where(ApprovalAction.approval_request_id == solicitud_id))
            database.session.execute(database.delete(ApprovalRequest).where(ApprovalRequest.id == solicitud_id))
            database.session.execute(database.delete(UserCompanyAccess).where(UserCompanyAccess.user_id == usuario_id))
            database.session.execute(database.delete(User).where(User.id == usuario_id))
            database.session.execute(database.delete(Entity).where(Entity.code == compania))
            database.session.execute(database.delete(Currency).where(Currency.code == moneda))
            database.session.commit()
            database.session.remove()
            database.engine.dispose()
