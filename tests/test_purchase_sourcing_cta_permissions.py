# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2140: los CTAs del comparativo respetan los permisos del POST."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting.auth import proteger_passwd
from cacao_accounting.database import (
    Modules,
    PurchaseNegotiationRound,
    PurchaseQuotation,
    PurchaseQuotationAward,
    PurchaseRequest,
    PurchaseRequestComparison,
    PurchaseRequestComparisonOffer,
    Roles,
    RolesAccess,
    RolesUser,
    SupplierQuotation,
    User,
    UserCompanyAccess,
    database,
)

CTA_ADJUDICAR = "Adjudicar y finalizar comparativo"
CTA_RONDA = "Abrir ronda de negociación"


def _rfq(app) -> str:
    """Crea una solicitud de cotización aprobada en cacao."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        rfq = PurchaseQuotation(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"RFQ-C{suffix}",
        )
        database.session.add(rfq)
        database.session.commit()
        return rfq.id


def _award(app, rfq_id: str) -> None:
    """Finaliza el comparativo para que aparezca el CTA de órdenes."""
    with app.app_context():
        database.session.add(
            PurchaseQuotationAward(
                purchase_quotation_id=rfq_id,
                company="cacao",
                status="finalized",
            )
        )
        database.session.commit()


def _viewer(app) -> str:
    """Crea un usuario con solo consulta de Compras."""
    suffix = uuid4().hex[:6]
    user_id = f"purchase-viewer-{suffix}"
    with app.app_context():
        module_id = database.session.execute(database.select(Modules.id).filter_by(module="purchases")).scalar_one()
        role = Roles(name=f"purchase-viewer-{suffix}", note="Consulta de Compras")
        database.session.add(role)
        database.session.flush()
        user = User(
            id=user_id,
            user=user_id,
            name="Consulta de Compras",
            password=proteger_passwd("PurchaseViewer-2026!"),
            classification="user",
            active=True,
            company="cacao",
        )
        database.session.add(user)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=role.id, module_id=module_id, access=True, view=True),
                RolesUser(user_id=user_id, role_id=role.id, active=True),
                UserCompanyAccess(user_id=user_id, company_code="cacao"),
            ]
        )
        database.session.commit()
        return user_id, user.auth_version


def _operator(app, *, create: bool, approve: bool) -> tuple[str, int]:
    """Crea un usuario de Compras con creación y/o autorización explícitas."""
    suffix = uuid4().hex[:6]
    user_id = f"purchase-operator-{suffix}"
    with app.app_context():
        module_id = database.session.execute(database.select(Modules.id).filter_by(module="purchases")).scalar_one()
        role = Roles(name=f"purchase-operator-{suffix}", note="Operador de Compras")
        database.session.add(role)
        database.session.flush()
        user = User(
            id=user_id,
            user=user_id,
            name="Operador de Compras",
            password=proteger_passwd("PurchaseOperator-2026!"),
            classification="user",
            active=True,
            company="cacao",
        )
        database.session.add(user)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(
                    rol_id=role.id,
                    module_id=module_id,
                    access=True,
                    view=True,
                    create=create,
                    approve=approve,
                ),
                RolesUser(user_id=user_id, role_id=role.id, active=True),
                UserCompanyAccess(user_id=user_id, company_code="cacao"),
            ]
        )
        database.session.commit()
        return user_id, user.auth_version


def _round(app, rfq_id: str) -> None:
    """Abre una ronda para ejercitar el CTA de agregar oferta."""
    with app.app_context():
        database.session.add(
            PurchaseNegotiationRound(
                purchase_quotation_id=rfq_id,
                round_number=1,
                status="open",
            )
        )
        database.session.commit()


def _comparison(app) -> tuple[str, str]:
    """Crea una comparativa de solicitud con un RFQ participante."""
    suffix = uuid4().hex[:6]
    with app.app_context():
        request = PurchaseRequest(
            company="cacao",
            document_no=f"REQ-CTA-{suffix}",
            requested_by="admin",
            posting_date=date(2026, 5, 15),
            docstatus=1,
        )
        rfq = PurchaseQuotation(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"RFQ-CTA-{suffix}",
        )
        database.session.add_all([request, rfq])
        database.session.flush()
        comparison = PurchaseRequestComparison(
            company="cacao",
            purchase_request_id=request.id,
            document_no=f"CMP-CTA-{suffix}",
            posting_date=date(2026, 5, 15),
            status="draft",
        )
        quotation = SupplierQuotation(
            company="cacao",
            posting_date=date(2026, 5, 15),
            docstatus=1,
            document_no=f"SC-CTA-{suffix}",
            supplier_name=f"Proveedor CTA {suffix}",
            transaction_currency="NIO",
            purchase_quotation_id=rfq.id,
        )
        database.session.add_all([comparison, quotation])
        database.session.flush()
        database.session.add(
            PurchaseRequestComparisonOffer(
                comparison_id=comparison.id,
                supplier_quotation_id=quotation.id,
            )
        )
        database.session.commit()
        return comparison.id, rfq.id


def _client_for(app, user_id: str, auth_version: int):
    """Cliente autenticado con el usuario indicado."""
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True
    return client


def test_comparativo_oculta_ctas_sin_permisos(app, entorno_contable):
    """Un lector no ve acciones que el POST rechazaría con 403."""
    rfq_id = _rfq(app)
    user_id, auth_version = _viewer(app)
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True

    response = client.get(f"/buying/request-for-quotation/{rfq_id}/offers")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert CTA_ADJUDICAR not in html
    assert CTA_RONDA not in html
    assert "Colocar Órdenes de Compra" not in html


def test_comparativo_muestra_ctas_al_administrador(app, entorno_contable, authenticated_client):
    """El administrador conserva las acciones autorizadas."""
    rfq_id = _rfq(app)

    response = authenticated_client("admin").get(f"/buying/request-for-quotation/{rfq_id}/offers")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert CTA_ADJUDICAR in html
    assert CTA_RONDA in html


def test_viewer_con_award_finalizado_no_ve_cta_ni_puede_postear(app, entorno_contable):
    """Un lector no ve el CTA finalizado ni puede ejecutar su POST."""
    rfq_id = _rfq(app)
    _award(app, rfq_id)
    user_id, auth_version = _viewer(app)
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_auth_version"] = auth_version
        session["_fresh"] = True

    response = client.get(f"/buying/request-for-quotation/{rfq_id}/offers")
    post = client.post(f"/buying/request-for-quotation/{rfq_id}/place-purchase-orders")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Colocar Órdenes de Compra" not in html
    assert "Finalizado" in html
    assert post.status_code == 403


def test_creador_sin_autorizacion_ve_cta_de_ordenes(app, entorno_contable):
    """El CTA depende de crear, no de autorizar."""
    rfq_id = _rfq(app)
    _award(app, rfq_id)
    user_id, auth_version = _operator(app, create=True, approve=False)
    client = _client_for(app, user_id, auth_version)

    response = client.get(f"/buying/request-for-quotation/{rfq_id}/offers")
    post = client.post(f"/buying/request-for-quotation/{rfq_id}/place-purchase-orders")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Colocar Órdenes de Compra" in html
    assert CTA_RONDA not in html
    assert post.status_code == 302


def test_autorizador_sin_creacion_no_ve_cta_de_ordenes(app, entorno_contable):
    """Un autorizador sin crear no ve la CTA que el POST rechazaría."""
    rfq_id = _rfq(app)
    _award(app, rfq_id)
    user_id, auth_version = _operator(app, create=False, approve=True)
    client = _client_for(app, user_id, auth_version)

    response = client.get(f"/buying/request-for-quotation/{rfq_id}/offers")
    post = client.post(f"/buying/request-for-quotation/{rfq_id}/place-purchase-orders")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Colocar Órdenes de Compra" not in html
    assert CTA_RONDA not in html
    assert post.status_code == 403


def test_admin_con_award_finalizado_conserva_cta(app, entorno_contable, authenticated_client):
    """El administrador ve el CTA cuando el comparativo ya está finalizado."""
    rfq_id = _rfq(app)
    _award(app, rfq_id)

    response = authenticated_client("admin").get(f"/buying/request-for-quotation/{rfq_id}/offers")

    assert response.status_code == 200
    assert "Colocar Órdenes de Compra" in response.get_data(as_text=True)


@pytest.mark.parametrize(
    ("create", "approve", "visible"),
    [(True, False, False), (False, True, False), (True, True, True)],
)
def test_abrir_ronda_requiere_crear_y_autorizar(app, entorno_contable, create, approve, visible):
    """Abrir ronda solo se ofrece y ejecuta con ambos permisos."""
    rfq_id = _rfq(app)
    user_id, auth_version = _operator(app, create=create, approve=approve)
    client = _client_for(app, user_id, auth_version)

    response = client.get(f"/buying/request-for-quotation/{rfq_id}/offers")
    post = client.post(f"/buying/request-for-quotation/{rfq_id}/negotiation-round")

    assert response.status_code == 200
    assert (CTA_RONDA in response.get_data(as_text=True)) is visible
    if visible:
        assert post.status_code == 302
        with app.app_context():
            assert (
                database.session.execute(
                    database.select(PurchaseNegotiationRound).filter_by(purchase_quotation_id=rfq_id)
                ).scalar_one_or_none()
                is not None
            )
    else:
        assert post.status_code == 403
        with app.app_context():
            assert (
                database.session.execute(
                    database.select(PurchaseNegotiationRound).filter_by(purchase_quotation_id=rfq_id)
                ).scalar_one_or_none()
                is None
            )


@pytest.mark.parametrize(("create", "visible"), [(True, True), (False, False)])
def test_agregar_oferta_ronda_abierta_requiere_crear(app, entorno_contable, create, visible):
    """Agregar oferta a una ronda abierta solo se ofrece con permiso de crear."""
    rfq_id = _rfq(app)
    _round(app, rfq_id)
    user_id, auth_version = _operator(app, create=create, approve=False)
    client = _client_for(app, user_id, auth_version)

    response = client.get(f"/buying/request-for-quotation/{rfq_id}/offers")

    assert response.status_code == 200
    assert ("Agregar oferta a esta ronda" in response.get_data(as_text=True)) is visible


@pytest.mark.parametrize(
    ("create", "approve", "visible"),
    [(True, False, False), (False, True, False), (True, True, True)],
)
def test_comparativo_solicitud_abrir_ronda_requiere_ambos_permisos(app, entorno_contable, create, approve, visible):
    """La comparativa de solicitud alinea Abrir ronda con crear y autorizar."""
    comparison_id, rfq_id = _comparison(app)
    user_id, auth_version = _operator(app, create=create, approve=approve)
    client = _client_for(app, user_id, auth_version)

    response = client.get(f"/buying/request-for-quotation/comparison/{comparison_id}")
    post = client.post(
        f"/buying/request-for-quotation/comparison/{comparison_id}/negotiation-round",
        data={"rfq_id": rfq_id},
    )

    assert response.status_code == 200
    assert (CTA_RONDA in response.get_data(as_text=True)) is visible
    assert post.status_code == (302 if visible else 403)
    with app.app_context():
        ronda = database.session.execute(
            database.select(PurchaseNegotiationRound).filter_by(purchase_quotation_id=rfq_id)
        ).scalar_one_or_none()
        assert (ronda is not None) is visible


@pytest.mark.parametrize(("create", "visible"), [(True, True), (False, False)])
def test_comparativo_solicitud_agregar_oferta_requiere_crear(app, entorno_contable, create, visible):
    """La comparativa de solicitud oculta agregar oferta sin permiso de crear."""
    comparison_id, rfq_id = _comparison(app)
    _round(app, rfq_id)
    user_id, auth_version = _operator(app, create=create, approve=False)
    client = _client_for(app, user_id, auth_version)

    response = client.get(f"/buying/request-for-quotation/comparison/{comparison_id}")

    assert response.status_code == 200
    assert ("Agregar oferta a esta ronda" in response.get_data(as_text=True)) is visible
