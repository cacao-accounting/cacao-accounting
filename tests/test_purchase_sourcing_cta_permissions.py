# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#2140: los CTAs del comparativo respetan los permisos del POST."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from cacao_accounting.auth import proteger_passwd
from cacao_accounting.database import (
    Modules,
    PurchaseQuotation,
    PurchaseQuotationAward,
    Roles,
    RolesAccess,
    RolesUser,
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
    assert "Colocar Órdenes de Compra" not in response.get_data(as_text=True)
    assert post.status_code == 403


def test_admin_con_award_finalizado_conserva_cta(app, entorno_contable, authenticated_client):
    """El administrador ve el CTA cuando el comparativo ya está finalizado."""
    rfq_id = _rfq(app)
    _award(app, rfq_id)

    response = authenticated_client("admin").get(f"/buying/request-for-quotation/{rfq_id}/offers")

    assert response.status_code == 200
    assert "Colocar Órdenes de Compra" in response.get_data(as_text=True)
