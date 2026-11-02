# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes
"""Integridad estructural de evidencia contable en Desktop y Cloud (issues #1706, #759, #923, #925, #1002).

Las protecciones estructurales (ledgers, vínculos del flujo documental y
bitácoras de auditoría) deben ser equivalentes en ambos modos: proteger
únicamente Cloud deja expuesta la misma evidencia por la ruta Desktop.

La batería opta explícitamente al enforcement mediante
``INTERNAL_CONTROLS_ENFORCE=True``, replicando el comportamiento en
producción de cada modo.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text

from cacao_accounting import create_app
from cacao_accounting.audit_chain import verify_audit_trail_chain
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    ApprovalAction,
    ApprovalRequest,
    AuditTrail,
    DocumentRelation,
    GLEntry,
    StockLedgerEntry,
    User,
    database,
)


@pytest.fixture(params=["desktop", "cloud"])
def app_garantizado(request):
    """App de prueba con control interno activo, en el modo indicado."""
    settings = dict(
        configuracion,
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_ENGINE_OPTIONS={"connect_args": {"check_same_thread": False}},
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        WTF_CSRF_ENABLED=False,
        SECRET_KEY="integridad-guardas",
        TESTING=True,
        INTERNAL_CONTROLS_ENFORCE=True,
        MODO_ESCRITORIO=request.param == "desktop",
    )
    application = create_app(settings)
    with application.app_context():
        database.create_all()
        database.session.add(User(user="integridad", name="Integridad", password=b"x", active=True))
        database.session.commit()
    yield application


def _liga_documental(status: str = "active") -> DocumentRelation:
    return DocumentRelation(
        source_type="sales_invoice",
        source_id="FA-1",
        target_type="delivery_note",
        target_id="EN-1",
        company=None,
        qty=Decimal("2"),
        relation_type="item_delivery",
        status=status,
    )


# ---------------------------------------------------------------------------
# Audit trail (issue #1002)
# ---------------------------------------------------------------------------


def test_audit_trail_no_se_edita_ni_se_borra_por_orm(app_garantizado):
    """El evento de auditoría conservado no puede modificarse ni truncarse por ORM."""
    with app_garantizado.app_context():
        database.session.add(
            AuditTrail(document_type="sales_invoice", document_id="FA-1", action="created", comment="original")
        )
        database.session.commit()
        evento = database.session.scalars(database.select(AuditTrail).where(AuditTrail.document_id == "FA-1")).one()

        evento.comment = "reescrito"
        with pytest.raises(ValueError):
            database.session.commit()
        database.session.rollback()
        evento = database.session.scalars(database.select(AuditTrail).where(AuditTrail.document_id == "FA-1")).one()
        assert evento.comment == "original"
        database.session.delete(evento)
        with pytest.raises(ValueError):
            database.session.commit()
        database.session.rollback()
        assert database.session.scalars(database.select(AuditTrail).where(AuditTrail.document_id == "FA-1")).one() is not None
        assert verify_audit_trail_chain() == []


def test_audit_trail_no_se_edita_ni_se_borra_por_sql_directo(app_garantizado):
    """UPDATE y DELETE textuales o Core sobre auditoría quedan rechazados."""
    with app_garantizado.app_context():
        database.session.add(AuditTrail(document_type="delivery_note", document_id="EN-2", action="created"))
        database.session.commit()
        with pytest.raises(ValueError):
            database.session.execute(
                database.update(AuditTrail.__table__)
                .where(AuditTrail.__table__.c.document_id == "EN-2")
                .values(comment="reescrito")
            )
        database.session.rollback()
        with pytest.raises(ValueError):
            database.session.execute(text("UPDATE audit_trail SET comment = 'reescrito' WHERE document_id = 'EN-2'"))
        database.session.rollback()
        with pytest.raises(ValueError):
            database.session.execute(text("DELETE FROM audit_trail"))
        database.session.rollback()
        assert database.session.scalars(database.select(AuditTrail).where(AuditTrail.document_id == "EN-2")).one() is not None
        assert verify_audit_trail_chain() == []


def test_approval_action_e_audit_log_no_se_borrar(app_garantizado):
    """Las acciones de aprobación y el log de auditoría heredan la protección."""
    with app_garantizado.app_context():
        usuario = database.session.scalars(database.select(User)).one()
        solicitud = ApprovalRequest(
            document_type="sales_invoice",
            document_id="FA-ACC",
            company_id="cacao",
            requested_by=usuario.id,
        )
        database.session.add(solicitud)
        database.session.flush()
        accion = ApprovalAction(approval_request_id=solicitud.id, approved_by=usuario.id, action="approve", level=1)
        database.session.add(accion)
        database.session.commit()
        accion_id = accion.id

        with pytest.raises(ValueError):
            database.session.delete(accion)
            database.session.commit()
        database.session.rollback()
        assert database.session.get(ApprovalAction, accion_id) is not None


# ---------------------------------------------------------------------------
# Ledgers y monotonicidad de is_cancelled (issues #759 y #925)
# ---------------------------------------------------------------------------


def _entrada_gl(desbalance: int = 1) -> GLEntry:
    return GLEntry(
        company="cacao",
        posting_date=date(2026, 5, 1),
        voucher_type="Journal Entry",
        voucher_id="AS-GL-1",
        account_code="1101",
        debit=Decimal("100"),
        credit=Decimal(0),
    )


def test_gl_no_se_reactiva_ni_se_borra_por_orm_ni_por_core(app_garantizado):
    """is_cancelled es monotónico y la línea del ledger no se elimina por ninguna ruta."""
    with app_garantizado.app_context():
        entrada = _entrada_gl()
        database.session.add(entrada)
        database.session.commit()
        entrada_id = entrada.id
        entrada.is_cancelled = True
        database.session.commit()

        entrada.is_cancelled = False
        with pytest.raises(ValueError):
            database.session.commit()
        database.session.rollback()

        with pytest.raises(ValueError):
            database.session.execute(
                database.update(GLEntry.__table__)
                .where(GLEntry.__table__.c.id == entrada_id)
                .values(is_cancelled=False, debit=Decimal("777"))
            )
        database.session.rollback()

        with pytest.raises(ValueError):
            database.session.execute(
                database.update(GLEntry.__table__).where(GLEntry.__table__.c.id == entrada_id).values(is_cancelled=False)
            )
        database.session.rollback()

        with pytest.raises(ValueError):
            database.session.execute(database.delete(GLEntry.__table__).where(GLEntry.__table__.c.id == entrada_id))
        database.session.rollback()

        with pytest.raises(ValueError):
            database.session.execute(text("DELETE FROM gl_entry"))
        database.session.rollback()

        persistida = database.session.get(GLEntry, entrada_id)
        assert persistida is not None
        assert persistida.debit == Decimal("100")
        assert database.session.execute(database.select(GLEntry.is_cancelled).where(GLEntry.id == entrada_id)).scalar_one()


def test_cancelacion_legitima_de_ledger_continua_operando(app_garantizado):
    """El flujo autorizado False -> True sigue funcionando en ambos modos."""
    with app_garantizado.app_context():
        entrada = _entrada_gl()
        database.session.add(entrada)
        database.session.commit()
        entrada.is_cancelled = True
        database.session.commit()
        assert database.session.execute(database.select(GLEntry.is_cancelled).where(GLEntry.id == entrada.id)).scalar_one()


def test_stock_ledger_no_se_reescribe_ni_se_borra_en_cualquier_modo(app_garantizado):
    """El kardex permanece inmutable en Desktop y Cloud (issue #759)."""
    with app_garantizado.app_context():
        entrada = StockLedgerEntry(
            posting_date=date(2026, 5, 12),
            item_code="IT-INT",
            warehouse="BOD-INT",
            company="cacao",
            qty_change=Decimal("5"),
            voucher_type="stock",
            voucher_id="ST-INT-1",
        )
        database.session.add(entrada)
        database.session.commit()
        entrada_id = entrada.id

        entrada.qty_change = Decimal("8")
        with pytest.raises(ValueError):
            database.session.commit()
        database.session.rollback()

        with pytest.raises(ValueError):
            database.session.execute(
                database.update(StockLedgerEntry.__table__)
                .where(StockLedgerEntry.__table__.c.id == entrada_id)
                .values(qty_change=Decimal("9"))
            )
        database.session.rollback()

        with pytest.raises(ValueError):
            database.session.execute(
                database.delete(StockLedgerEntry.__table__).where(StockLedgerEntry.__table__.c.id == entrada_id)
            )
        database.session.rollback()
        persistida = database.session.get(StockLedgerEntry, entrada_id)
        assert persistida.qty_change == Decimal("5")


# ---------------------------------------------------------------------------
# Evidencia del flujo documental (issue #923)
# ---------------------------------------------------------------------------


def test_document_relation_no_se_reescribe_ni_se_borra(app_garantizado):
    """Vínculos documentales: reescritura, borrado y SQL directo quedan rechazados."""
    with app_garantizado.app_context():
        database.session.add(_liga_documental())
        database.session.commit()
        liga = database.session.scalars(database.select(DocumentRelation)).one()
        liga_id = liga.id

        liga.qty = Decimal("200")
        with pytest.raises(ValueError):
            database.session.commit()
        database.session.rollback()

        with pytest.raises(ValueError):
            database.session.execute(
                database.update(DocumentRelation.__table__)
                .where(DocumentRelation.__table__.c.id == liga_id)
                .values(source_id="FA-OTRA")
            )
        database.session.rollback()

        with pytest.raises(ValueError):
            database.session.execute(
                database.delete(DocumentRelation.__table__).where(DocumentRelation.__table__.c.id == liga_id)
            )
        database.session.rollback()

        with pytest.raises(ValueError):
            database.session.execute(text("UPDATE document_relation SET qty = 300 WHERE id = '%s'" % liga_id))
        database.session.rollback()

        persistida = database.session.get(DocumentRelation, liga_id)
        assert persistida.qty == Decimal("2")
        assert persistida.source_id == "FA-1"


def test_document_relation_transiciones_requieren_servicio_autorizado(app_garantizado):
    """Las transiciones de estado solo operan dentro del scope del servicio."""
    from cacao_accounting.internal_control_service import flow_evidence_transition

    with app_garantizado.app_context():
        database.session.add(_liga_documental())
        database.session.commit()
        liga = database.session.scalars(database.select(DocumentRelation)).one()

        liga.status = "reverted"
        with pytest.raises(ValueError):
            database.session.commit()
        database.session.rollback()

        with flow_evidence_transition(liga):
            liga.status = "reverted"
            liga.reversal_reason = "target_cancelled"
            database.session.commit()
        assert database.session.get(DocumentRelation, liga.id).status == "reverted"

        liga = database.session.get(DocumentRelation, liga.id)
        with flow_evidence_transition(liga):
            liga.status = "active"
            liga.reversal_reason = None
            with pytest.raises(ValueError):
                database.session.commit()
            database.session.rollback()
        assert database.session.get(DocumentRelation, liga.id).status == "reverted"


def test_desktop_y_cloud_protegen_la_misma_evidencia(app_garantizado):
    """La referencia de un vínculo confirmado no puede cambiarse en ningún modo."""
    with app_garantizado.app_context():
        database.session.add(_liga_documental())
        database.session.commit()
        liga = database.session.scalars(database.select(DocumentRelation)).one()
        liga.target_id = "EN-FALSA"
        with pytest.raises(ValueError):
            database.session.commit()
        database.session.rollback()


def test_insert_core_en_tablas_estructurales_queda_rechazado(app_garantizado):
    """Core INSERT y mutaciones de tablas polimórficas de evidencia quedan bloqueadas."""
    from cacao_accounting.database import LandedCostAllocation, UOM

    with app_garantizado.app_context():
        with pytest.raises(ValueError):
            database.session.execute(
                database.insert(DocumentRelation.__table__).values(
                    source_type="sales_invoice",
                    source_id="FA-CORE",
                    target_type="delivery_note",
                    target_id="EN-CORE",
                    qty=1,
                    relation_type="item_delivery",
                )
            )
        with pytest.raises(ValueError):
            database.session.execute(database.delete(LandedCostAllocation.__table__))
        database.session.rollback()
        if not app_garantizado.config["MODO_ESCRITORIO"]:
            with pytest.raises(ValueError):
                database.session.execute(text("UPDATE approval_request SET status = 'manipulado'"))
            database.session.rollback()
        database.session.add(UOM(code="INT-KG", name="Kilogramo"))
        database.session.commit()
        unidad = database.session.scalars(database.select(UOM).where(UOM.code == "INT-KG")).one_or_none()
        assert unidad is not None
        database.session.execute(database.insert(UOM.__table__).values(code="INT-L", name="Litro", is_active=True))
        database.session.execute(
            database.update(UOM.__table__).where(UOM.__table__.c.code == "INT-L").values(name="Litro actualizado")
        )
        database.session.commit()
        assert database.session.scalars(database.select(UOM).where(UOM.code == "INT-L")).one().name == "Litro actualizado"


def test_sin_contexto_de_aplicacion_no_participa_la_salvaguarda_estructural(app_garantizado):
    """La responsabilidad fuera de la aplicacion es del administrador de infraestructura.

    El guard estructural pertenece a las interfaces y servicios de Cacao. Una
    sesión SQL abierta sin contexto Flask (herramientas de administración,
    scripts de mantenimiento) no participa en el sistema y no se le exige
    inmutabilidad: esa protección es de la infraestructura (#1706, alcance).
    """
    with app_garantizado.app_context():
        database.create_all()
        entrada = _entrada_gl()
        database.session.add(entrada)
        database.session.commit()
        engine = database.engine
        database.session.remove()
    from sqlalchemy.orm import Session

    sesion_pura = Session(bind=engine)
    try:
        sesion_pura.execute(
            database.update(GLEntry.__table__).where(GLEntry.__table__.c.voucher_id == "AS-GL-1").values(is_cancelled=False)
        )
        sesion_pura.commit()
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"La mutación fuera de la app no debía pasar por el guard estructural: {exc}")
    finally:
        sesion_pura.close()


def test_suite_generica_de_prueba_queda_exenta_de_la_salvaguarda_estructural():
    """Las corridas genéricas (TESTING sin opt-in) mantienen siembra y limpieza desbloqueadas."""
    settings = dict(
        configuracion,
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_ENGINE_OPTIONS={"connect_args": {"check_same_thread": False}},
        WTF_CSRF_ENABLED=False,
        SECRET_KEY="exencion-genericas",
        TESTING=True,
        MODO_ESCRITORIO=False,
    )
    application = create_app(settings)
    with application.app_context():
        database.create_all()
        database.session.add(_liga_documental())
        database.session.commit()
        liga = database.session.scalars(database.select(DocumentRelation)).one()
        liga.qty = Decimal("200")
        database.session.commit()
        assert database.session.get(DocumentRelation, liga.id).qty == Decimal("200")
