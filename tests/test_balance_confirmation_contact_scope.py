# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1777: los correos de confirmación se aíslan por compañía.

Party y Contact siguen siendo globales, pero un correo solo se sugiere a
través de un `PartyContact` explícito de la compañía autorizada. El flujo
autoriza compañía y tercero antes de cargar destinatarios, y no expone
`Party.primary_email` por sí solo.
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.contabilidad import balance_confirmation_bp
from cacao_accounting.database import (
    BalanceConfirmation,
    CompanyParty,
    Contact,
    Currency,
    Entity,
    Modules,
    Party,
    PartyContact,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)
from cacao_accounting.party_management import create_party_contact, update_party_contact

RUTA = "/accounting/balance-confirmations/new"


@pytest.fixture
def escenario_contactos():
    """Tercero compartido por Alpha/Beta con un contacto explícito en cada una."""
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
    suffix = uuid4().hex[:6].upper()
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="accounting", default=True, enabled=True),
                Entity(code="alpha", name="Alpha", company_name="Alpha SA", tax_id="A-1", currency="NIO", enabled=True),
                Entity(code="beta", name="Beta", company_name="Beta SA", tax_id="B-1", currency="NIO", enabled=True),
            ]
        )
        database.session.flush()
        modulo = database.session.execute(database.select(Modules).filter_by(module="accounting")).scalar_one()
        party = Party(code=f"CLI-{suffix}", name="Cliente Compartido", is_customer=True, primary_email="principal@example.com")
        database.session.add(party)
        database.session.flush()
        database.session.add_all(
            [
                CompanyParty(company="alpha", party_id=party.id, is_active=True),
                CompanyParty(company="beta", party_id=party.id, is_active=True),
            ]
        )
        contact_alpha = Contact(first_name="Alpha", email=f"alpha-{suffix}@example.com", is_active=True)
        contact_beta = Contact(first_name="Beta", email=f"beta-{suffix}@example.com", is_active=True)
        database.session.add_all([contact_alpha, contact_beta])
        database.session.flush()
        database.session.add_all(
            [
                PartyContact(party_id=party.id, contact_id=contact_alpha.id, company="alpha"),
                PartyContact(party_id=party.id, contact_id=contact_beta.id, company="beta"),
            ]
        )
        user_id = f"user-{suffix}"
        role = Roles(name=f"confirmaciones-{suffix}", note="Confirmaciones")
        database.session.add_all(
            [
                User(id=user_id, user=user_id, name="Solicitante", password=b"unused", active=True, company="alpha"),
                role,
            ]
        )
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(rol_id=role.id, module_id=modulo.id, access=True, view=True, create=True, request=True),
                RolesUser(user_id=user_id, role_id=role.id, active=True),
                UserCompanyAccess(user_id=user_id, company_code="alpha"),
            ]
        )
        database.session.commit()
        ids = {
            "party": party.id,
            "user": user_id,
            "alpha_email": contact_alpha.email,
            "beta_email": contact_beta.email,
            "alpha_link": database.session.execute(
                database.select(PartyContact.id).filter_by(party_id=party.id, company="alpha")
            ).scalar_one(),
        }
    yield application, ids
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def _login(application, user_id: str):
    """Cliente autenticado."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True
    return client


def _url(ids: dict, company: str | None = None) -> str:
    """URL del formulario con tercero y compañía opcional."""
    url = f"{RUTA}?party_id={ids['party']}&party_type=customer"
    return f"{url}&company_id={company}" if company else url


def test_company_autorizada_solo_sugiere_sus_contactos(escenario_contactos):
    """Con Alpha autorizada se cargan los correos Alpha y no los de Beta."""
    application, ids = escenario_contactos
    client = _login(application, ids["user"])

    response = client.get(_url(ids, "alpha"))

    assert response.status_code == 200
    pagina = response.get_data(as_text=True)
    assert ids["alpha_email"] in pagina
    assert ids["beta_email"] not in pagina
    assert "principal@example.com" not in pagina


def test_sin_compania_no_se_cargan_correos(escenario_contactos):
    """El flujo exige compañía antes de exponer destinatarios."""
    application, ids = escenario_contactos
    client = _login(application, ids["user"])

    response = client.get(_url(ids))

    assert response.status_code == 200
    assert ids["alpha_email"] not in response.get_data(as_text=True)
    assert ids["beta_email"] not in response.get_data(as_text=True)


def test_compania_no_autorizada_o_ajena_responde_403(escenario_contactos):
    """No se puede enumerar Beta ni la compañía no asignada."""
    application, ids = escenario_contactos
    client = _login(application, ids["user"])

    assert client.get(_url(ids, "beta")).status_code == 403
    response = client.post(
        f"{RUTA}?party_id={ids['party']}&party_type=customer",
        data={"company_id": "beta", "cutoff_date": "2026-05-15", "emails": ids["alpha_email"]},
    )
    assert response.status_code == 403


def test_fallo_interno_de_creacion_revierte_y_no_expone_detalle(escenario_contactos, monkeypatch):
    """Un error interno se registra sin revelar su detalle ni conservar escritura parcial."""
    application, ids = escenario_contactos
    private_detail = "PRIVATE-SQL-SMTP-DETAIL-2128"

    def fail_after_writing(**kwargs):
        database.session.add(
            BalanceConfirmation(
                company=kwargs["company_id"],
                party_type=kwargs["party_type"],
                party_id=kwargs["party_id"],
                cutoff_date=kwargs["cutoff_date"],
                status="draft",
            )
        )
        database.session.flush()
        raise ValueError(private_detail)

    monkeypatch.setattr(balance_confirmation_bp, "create_balance_confirmation", fail_after_writing)
    with application.app_context():
        count_before = database.session.query(BalanceConfirmation).count()
    client = _login(application, ids["user"])
    response = client.post(
        _url(ids, "alpha"),
        data={"company_id": "alpha", "cutoff_date": date.today().isoformat(), "emails": ids["alpha_email"]},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert private_detail not in response.get_data(as_text=True)
    assert "No fue posible crear la confirmación de saldo." in response.get_data(as_text=True)
    with application.app_context():
        assert database.session.query(BalanceConfirmation).count() == count_before


def test_contacto_compartido_entre_companias_no_se_edita(escenario_contactos):
    """Editar un contacto compartido alteraría evidencia de otra compañía."""
    application, ids = escenario_contactos
    with application.app_context():
        shared = Contact(first_name="Compartido", email="shared@example.com", is_active=True)
        database.session.add(shared)
        database.session.flush()
        database.session.add_all(
            [
                PartyContact(party_id=ids["party"], contact_id=shared.id, company="alpha"),
                PartyContact(party_id=ids["party"], contact_id=shared.id, company="beta"),
            ]
        )
        database.session.commit()
        alpha_link = database.session.execute(
            database.select(PartyContact.id).filter_by(party_id=ids["party"], company="alpha", contact_id=shared.id)
        ).scalar_one()

        with pytest.raises(ValueError, match="compartido"):
            update_party_contact(ids["party"], alpha_link, {"first_name": "Cambio", "email": "x@example.com"}, "alpha")


def test_alta_de_contacto_exige_compania_vinculada_al_tercero(escenario_contactos):
    """No se crea un contacto para una compañía sin vínculo con el tercero."""
    application, ids = escenario_contactos
    with application.app_context():
        with pytest.raises(ValueError, match="habilitado"):
            create_party_contact(ids["party"], {"first_name": "X", "email": "x@example.com"}, "gamma")

        contacto = create_party_contact(ids["party"], {"first_name": "Y", "email": "y@example.com"}, "alpha")
        link = database.session.execute(
            database.select(PartyContact).filter_by(party_id=ids["party"], contact_id=contacto.id)
        ).scalar_one()
        assert link.company == "alpha"
