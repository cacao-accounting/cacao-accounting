# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La autorización de abastecimiento respeta la vigencia de asignaciones de rol."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.compras.purchase_sourcing_service import (
    PurchaseSourcingError,
    close_purchase_quotation_comparison,
    _validate_award_authorization,
    create_purchase_quotation_award,
    is_purchase_manager,
    is_purchase_sourcing_authorizer,
    open_negotiation_round,
    _flush_award,
)
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    Currency,
    Entity,
    Item,
    Modules,
    Party,
    PurchaseQuotation,
    PurchaseQuotationAward,
    PurchaseQuotationAwardItem,
    PurchaseQuotationItem,
    PurchaseNegotiationRound,
    Roles,
    RolesUser,
    SupplierQuotation,
    SupplierQuotationItem,
    UOM,
    User,
    database,
)


@pytest.fixture
def purchase_roles(tmp_path: Path):
    """Provide active, revoked, legacy, and admin users with persisted assignments."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'purchase_roles.db'}",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
            "WTF_CSRF_ENABLED": False,
        }
    )
    users = {
        "active": User(id="active", user="active", name="Activo", password=b"x", active=True),
        "revoked": User(id="revoked", user="revoked", name="Revocado", password=b"x", active=True),
        "legacy": User(id="legacy", user="legacy", name="Histórico", password=b"x", active=True),
        "admin": User(
            id="admin",
            user="admin",
            name="Administrador",
            password=b"x",
            active=True,
            classification="admin",
        ),
    }
    with application.app_context():
        database.create_all()
        database.session.add_all([*users.values(), Roles(name="Gerente de Compras", note="Gerente de Compras")])
        database.session.flush()
        manager_role = database.session.execute(database.select(Roles).filter_by(name="Gerente de Compras")).scalar_one()
        database.session.add_all(
            [
                RolesUser(user_id=users["active"].id, role_id=manager_role.id, active=True),
                RolesUser(user_id=users["revoked"].id, role_id=manager_role.id, active=False),
                RolesUser(user_id=users["legacy"].id, role_id=manager_role.id, active=False),
            ]
        )
        user_ids = {key: user.id for key, user in users.items()}
        database.session.commit()
    yield application, user_ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


@pytest.mark.parametrize(
    ("assignment", "expected"),
    [("active", True), ("revoked", False), ("legacy", False)],
)
def test_purchase_manager_checks_assignment_state(purchase_roles, assignment, expected):
    """Only an explicit active assignment authorizes; NULL is no longer valid."""
    application, users = purchase_roles
    with application.app_context():
        assert is_purchase_manager(users[assignment]) is expected
        assert is_purchase_sourcing_authorizer(users[assignment]) is expected


@pytest.mark.parametrize(("assignment", "authorized"), [("active", True), ("revoked", False), ("legacy", False)])
def test_only_current_or_legacy_manager_can_authorize_single_offer(purchase_roles, assignment, authorized):
    """The role state controls the insufficient-offer exception used by award flows."""
    application, users = purchase_roles
    with application.app_context():
        if authorized:
            _validate_award_authorization([], minimum_offers=1, user_id=users[assignment], reason="Excepción aprobada")
            return

        with pytest.raises(PurchaseSourcingError, match="Se requieren al menos"):
            _validate_award_authorization([], minimum_offers=1, user_id=users[assignment], reason="Excepción aprobada")


def test_administrador_conserva_autorización_de_excepciones(purchase_roles):
    """The admin classification remains an independent authorization path."""
    application, users = purchase_roles
    with application.app_context():
        assert not is_purchase_manager(users["admin"])
        assert is_purchase_sourcing_authorizer(users["admin"])
        _validate_award_authorization([], minimum_offers=1, user_id=users["admin"], reason="Excepción aprobada")


@pytest.mark.parametrize("reason", ["   ", "\t\n ", " \u00a0 ", ""])
@pytest.mark.parametrize("assignment", ["active", "admin"])
def test_justificacion_sin_contenido_no_autoriza_oferta_unica(purchase_roles, assignment, reason):
    """A blank justification never enables the insufficient-offer exception."""
    application, users = purchase_roles
    with application.app_context():
        with pytest.raises(PurchaseSourcingError, match="justificación"):
            _validate_award_authorization([], minimum_offers=2, user_id=users[assignment], reason=reason)


@pytest.fixture
def sourcing_award(tmp_path: Path):
    """Provide an RFQ with a cheap and an expensive supplier offer."""
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'sourcing_award.db'}",
            "SQLALCHEMY_ENGINE_OPTIONS": {"poolclass": StaticPool},
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "TESTING": True,
            "MODO_ESCRITORIO": True,
            "WTF_CSRF_ENABLED": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="purchases", default=True, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
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
                UOM(code="UND", name="Unidad"),
            ]
        )
        database.session.flush()
        cheap_supplier = Party(code="PROV-CHEAP", name="Proveedor Económico", is_supplier=True)
        expensive_supplier = Party(code="PROV-COSTLY", name="Proveedor Costoso", is_supplier=True)
        database.session.add_all(
            [
                cheap_supplier,
                expensive_supplier,
                Item(code="ART-1", name="Artículo", item_type="goods", is_stock_item=True, default_uom="UND"),
            ]
        )
        database.session.flush()
        rfq = PurchaseQuotation(
            company="cacao",
            posting_date=date(2026, 11, 19),
            docstatus=1,
            document_no="RFQ-1422",
            transaction_currency="NIO",
        )
        database.session.add(rfq)
        database.session.flush()
        rfq_item = PurchaseQuotationItem(
            purchase_quotation_id=rfq.id,
            item_code="ART-1",
            qty=Decimal("5"),
            uom="UND",
            qty_in_base_uom=Decimal("5"),
        )
        database.session.add(rfq_item)
        database.session.flush()
        offers = {}
        for supplier, document_no, rate in (
            (cheap_supplier, "SQ-CHEAP", "10"),
            (expensive_supplier, "SQ-COSTLY", "15"),
        ):
            quotation = SupplierQuotation(
                company="cacao",
                posting_date=date(2026, 11, 19),
                docstatus=1,
                document_no=document_no,
                supplier_id=supplier.id,
                purchase_quotation_id=rfq.id,
                transaction_currency="NIO",
            )
            database.session.add(quotation)
            database.session.flush()
            database.session.add(
                SupplierQuotationItem(
                    supplier_quotation_id=quotation.id,
                    item_code="ART-1",
                    qty=Decimal("5"),
                    uom="UND",
                    qty_in_base_uom=Decimal("5"),
                    rate=Decimal(rate),
                )
            )
            offers[document_no] = quotation.id
        database.session.commit()
        ids = {"rfq": rfq.id, "rfq_item": rfq_item.id, **offers}
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


@pytest.mark.parametrize("reason", ["   ", "\t\n "])
def test_adjudicacion_rechaza_justificacion_vacia_en_oferta_no_recomendada(sourcing_award, reason):
    """Selecting a costlier offer still requires a substantive justification."""
    application, ids = sourcing_award
    with application.app_context():
        rfq = database.session.get(PurchaseQuotation, ids["rfq"])
        with pytest.raises(PurchaseSourcingError, match="no recomendada"):
            create_purchase_quotation_award(rfq, {ids["rfq_item"]: ids["SQ-COSTLY"]}, "admin", reason)
        assert database.session.execute(database.select(PurchaseQuotationAward)).scalars().all() == []


def test_adjudicacion_persiste_justificacion_normalizada(sourcing_award):
    """A valid justification is stored trimmed and authorizes the override."""
    application, ids = sourcing_award
    with application.app_context():
        rfq = database.session.get(PurchaseQuotation, ids["rfq"])
        award = create_purchase_quotation_award(
            rfq,
            {ids["rfq_item"]: ids["SQ-COSTLY"]},
            "admin",
            "  Oferta urgente por desabastecimiento  \n",
        )
        database.session.commit()
        assert award.authorization_reason == "Oferta urgente por desabastecimiento"
        assert award.authorized_by == "admin"
        award_item = database.session.execute(
            database.select(PurchaseQuotationAwardItem).filter_by(award_id=award.id)
        ).scalar_one()
        assert award_item.manual_override is True
        assert award_item.override_reason == "Oferta urgente por desabastecimiento"


def test_adjudicacion_descarta_justificacion_vacia_sin_excepcion(sourcing_award):
    """A blank reason is not persisted when no exception is required."""
    application, ids = sourcing_award
    with application.app_context():
        rfq = database.session.get(PurchaseQuotation, ids["rfq"])
        award = create_purchase_quotation_award(rfq, {ids["rfq_item"]: ids["SQ-CHEAP"]}, "admin", "   ")
        assert award.authorization_reason is None
        assert award.authorized_by is None


def _close_rfq_manually(application, ids) -> None:
    """Create a persisted manual close for the RFQ in the sourcing fixture."""
    with application.app_context():
        rfq = database.session.get(PurchaseQuotation, ids["rfq"])
        close_purchase_quotation_comparison(rfq, "admin", "Cierre aprobado por falta de ofertas adecuadas")
        database.session.commit()


def _login_as_admin(client, application) -> None:
    """Authenticate the fixture administrator in a test client session."""
    with application.app_context():
        user = database.session.get(User, "admin")
        auth_version = user.auth_version
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_auth_version"] = auth_version
        session["_fresh"] = True


def test_manual_close_blocks_service_round_and_award_creation(sourcing_award):
    """A manual close is terminal for service calls as well as for the UI."""
    application, ids = sourcing_award
    _close_rfq_manually(application, ids)

    with application.app_context():
        rfq = database.session.get(PurchaseQuotation, ids["rfq"])
        with pytest.raises(PurchaseSourcingError, match="comparativo cerrado"):
            open_negotiation_round(rfq.id, "admin")
        with pytest.raises(PurchaseSourcingError, match="comparativo cerrado"):
            create_purchase_quotation_award(rfq, {ids["rfq_item"]: ids["SQ-CHEAP"]}, "admin")

        assert database.session.execute(database.select(PurchaseNegotiationRound)).scalars().all() == []
        awards = database.session.execute(database.select(PurchaseQuotationAward)).scalars().all()
        assert len(awards) == 1
        assert awards[0].status == "closed"


def test_repeated_manual_close_preserves_the_single_close_record(sourcing_award):
    """Repeating a close cannot add or rewrite its append-only award evidence."""
    application, ids = sourcing_award
    _close_rfq_manually(application, ids)

    with application.app_context():
        rfq = database.session.get(PurchaseQuotation, ids["rfq"])
        with pytest.raises(PurchaseSourcingError, match="comparativo cerrado"):
            close_purchase_quotation_comparison(rfq, "admin", "Segundo intento")

        awards = database.session.execute(database.select(PurchaseQuotationAward)).scalars().all()
        assert len(awards) == 1
        assert awards[0].status == "closed"
        assert awards[0].authorization_reason == "Cierre aprobado por falta de ofertas adecuadas"


def test_award_unique_collision_is_translated_to_closed_domain_error(sourcing_award):
    """The database uniqueness guard remains a controlled domain rejection."""
    application, ids = sourcing_award
    _close_rfq_manually(application, ids)

    with application.app_context():
        collision = PurchaseQuotationAward(
            purchase_quotation_id=ids["rfq"],
            company="cacao",
            status="finalized",
        )
        with pytest.raises(PurchaseSourcingError, match="adjudicación o cierre registrado") as error:
            _flush_award(collision)

        awards = database.session.execute(database.select(PurchaseQuotationAward)).scalars().all()
        assert len(awards) == 1
        assert awards[0].status == "closed"
        assert isinstance(error.value.__cause__, IntegrityError)
        # The savepoint leaves the outer transaction available for caller rollback/commit.
        assert database.session.is_active


def test_unrelated_integrity_error_is_not_translated_as_award_collision(sourcing_award):
    """A different database invariant must remain visible to its caller."""
    application, ids = sourcing_award

    with application.app_context():
        invalid_award = PurchaseQuotationAward(
            purchase_quotation_id=ids["rfq"],
            company=None,
            status="finalized",
        )
        with pytest.raises(IntegrityError) as error:
            _flush_award(invalid_award)

        assert "purchase_quotation_award.company" in str(error.value.orig)
        assert database.session.is_active


@pytest.mark.parametrize(
    ("path_suffix", "form_data"),
    [
        ("negotiation-round", {}),
        ("award", {"award_item_{item_id}": "{quotation_id}"}),
    ],
)
def test_manual_close_blocks_round_and_award_post_routes(sourcing_award, path_suffix, form_data):
    """Both POST entry points report the manual close and preserve one award."""
    application, ids = sourcing_award
    _close_rfq_manually(application, ids)
    client = application.test_client()
    _login_as_admin(client, application)
    form = {
        key.format(item_id=ids["rfq_item"], quotation_id=ids["SQ-CHEAP"]): value.format(
            item_id=ids["rfq_item"], quotation_id=ids["SQ-CHEAP"]
        )
        for key, value in form_data.items()
    }

    response = client.post(f"/buying/request-for-quotation/{ids['rfq']}/{path_suffix}", data=form, follow_redirects=True)

    assert response.status_code == 200
    assert "comparativo cerrado" in response.get_data(as_text=True)
    with application.app_context():
        awards = database.session.execute(database.select(PurchaseQuotationAward)).scalars().all()
        rounds = database.session.execute(database.select(PurchaseNegotiationRound)).scalars().all()
        assert len(awards) == 1
        assert awards[0].status == "closed"
        assert rounds == []
