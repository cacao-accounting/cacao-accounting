# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#909: regresión del smart-select de terceros con alcance de compañía.

El selector de terceros ejecuta el endpoint real ``/api/search-select`` de
principio a fin. El escenario cubre un tercero vinculado a dos compañías
autorizadas (la condición que motivaba ``DISTINCT``), varios grados de
relevancia y un tercero fuera del alcance solicitado.

La variante marcada con ``database`` reutiliza el motor configurado
(PostgreSQL en Tier 1) para detectar el ``ORDER BY`` inválido que SQLite no
rechaza: ``for SELECT DISTINCT, ORDER BY expressions must appear in select
list`` (#909).
"""

from __future__ import annotations

from dataclasses import dataclass
from secrets import token_hex
from typing import Any, Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.auth import proteger_passwd
from cacao_accounting.config import configuracion
from cacao_accounting.database import (
    CompanyParty,
    Currency,
    Entity,
    Modules,
    Party,
    User,
    UserCompanyAccess,
    database,
)

PASSWORD = "party-search-select-password"


@dataclass(frozen=True)
class PartySearchScenario:
    """Datos sembrados y cliente autenticado para la regresión."""

    app: Flask
    client: FlaskClient
    user_id: str
    company_alpha: str
    company_beta: str
    exact_id: str
    prefix_id: str
    substring_id: str
    foreign_id: str
    exact_code: str


def _configured_test_uri() -> str:
    """Devuelve el motor configurado; SQLite se aísla en memoria."""
    configured_uri = str(configuracion["SQLALCHEMY_DATABASE_URI"])
    if make_url(configured_uri).get_backend_name() == "sqlite":
        return "sqlite://"
    return configured_uri


def _create_test_app(database_uri: str) -> Flask:
    """Crea una aplicación con el motor solicitado y CSRF deshabilitado."""
    settings: dict[str, Any] = {
        **configuracion,
        "SQLALCHEMY_DATABASE_URI": database_uri,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "WTF_CSRF_ENABLED": False,
        "TESTING": True,
        "SECRET_KEY": "party-search-select-regression",
        "MODO_ESCRITORIO": False,
    }
    if database_uri == "sqlite://":
        settings["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False},
        }
    app = create_app(settings)
    with app.app_context():
        assert database.engine.dialect.name == make_url(database_uri).get_backend_name()
    return app


def _seed_company(code: str) -> Entity:
    """Reutiliza o crea una compañía habilitada con moneda local."""
    company = database.session.execute(database.select(Entity).filter_by(code=code)).scalar_one_or_none()
    if company is None:
        company = Entity(
            code=code,
            name=code,
            company_name=f"Compañía {code}",
            tax_id=f"J-{code}",
            currency="NIO",
            enabled=True,
        )
        database.session.add(company)
        database.session.flush()
    return company


def _seed_party(code: str, name: str) -> Party:
    """Crea un tercero activo con código único."""
    party = Party(code=code, name=name, is_customer=True, is_active=True)
    database.session.add(party)
    database.session.flush()
    return party


def _seed_scenario(app: Flask) -> PartySearchScenario:
    """Siembra compañías, un usuario con dos grants y cuatro terceros."""
    suffix = token_hex(3).upper()
    alpha_code = f"A909{suffix}"
    beta_code = f"B909{suffix}"
    exact_code = f"Z909{suffix}"

    with app.app_context():
        database.create_all()
        if database.session.execute(database.select(Currency).filter_by(code="NIO")).scalar_one_or_none() is None:
            database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
            database.session.flush()

        _seed_company(alpha_code)
        _seed_company(beta_code)
        for module_name in ("sales", "purchases"):
            if database.session.execute(database.select(Modules).filter_by(module=module_name)).scalar_one_or_none() is None:
                database.session.add(Modules(module=module_name, default=False, enabled=True))
        database.session.flush()

        user = User(
            user=f"u909{suffix}",
            name="Consulta Terceros",
            password=proteger_passwd(PASSWORD),
            classification="admin",
            active=True,
            company=alpha_code,
        )
        database.session.add(user)
        database.session.flush()
        database.session.add_all(
            [
                UserCompanyAccess(user_id=user.id, company_code=alpha_code),
                UserCompanyAccess(user_id=user.id, company_code=beta_code),
            ]
        )

        # El tercero exacto también está vinculado a beta: el alcance multiempresa
        # es el caso que antes se intentaba resolver con DISTINCT.
        exact = _seed_party(exact_code, "Tercero Exacto 909")
        prefix = _seed_party(f"{exact_code}-P", "Tercero Prefijo 909")
        substring = _seed_party(f"0{exact_code}", "Tercero Contenido 909")
        foreign = _seed_party(f"X909{suffix}", "Tercero Ajeno 909")
        database.session.add_all(
            [
                CompanyParty(company=alpha_code, party_id=exact.id, is_active=True),
                CompanyParty(company=beta_code, party_id=exact.id, is_active=True),
                CompanyParty(company=alpha_code, party_id=prefix.id, is_active=True),
                CompanyParty(company=alpha_code, party_id=substring.id, is_active=True),
                CompanyParty(company=beta_code, party_id=foreign.id, is_active=True),
            ]
        )
        database.session.commit()

        client = app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = user.id
            session["_auth_version"] = user.auth_version
            session["_fresh"] = True

        return PartySearchScenario(
            app=app,
            client=client,
            user_id=user.id,
            company_alpha=alpha_code,
            company_beta=beta_code,
            exact_id=exact.id,
            prefix_id=prefix.id,
            substring_id=substring.id,
            foreign_id=foreign.id,
            exact_code=exact_code,
        )


def _cleanup_scenario(scenario: PartySearchScenario) -> None:
    """Elimina únicamente los datos sembrados por esta prueba."""
    party_ids = [scenario.exact_id, scenario.prefix_id, scenario.substring_id, scenario.foreign_id]
    with scenario.app.app_context():
        database.session.execute(database.delete(UserCompanyAccess).where(UserCompanyAccess.user_id == scenario.user_id))
        database.session.execute(database.delete(CompanyParty).where(CompanyParty.party_id.in_(party_ids)))
        database.session.execute(database.delete(User).where(User.id == scenario.user_id))
        database.session.execute(database.delete(Party).where(Party.id.in_(party_ids)))
        database.session.execute(
            database.delete(Entity).where(Entity.code.in_([scenario.company_alpha, scenario.company_beta]))
        )
        database.session.commit()
        database.session.remove()
        database.engine.dispose()


@pytest.fixture
def party_search_scenario() -> Iterator[PartySearchScenario]:
    """Ejecuta el endpoint real sobre una base aislada por prueba."""
    app = _create_test_app(_configured_test_uri())
    scenario = _seed_scenario(app)
    try:
        yield scenario
    finally:
        _cleanup_scenario(scenario)


def _party_results(client: FlaskClient, **params: str) -> dict[str, Any]:
    """Invoca el endpoint de smart-select y devuelve el payload validado."""
    response = client.get("/api/search-select", query_string={"doctype": "party", **params})
    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["doctype"] == "party"
    return payload


def _assert_party_search_contract(scenario: PartySearchScenario) -> None:
    """Verifica relevancia, deduplicación y alcance de compañía."""
    relevance = _party_results(scenario.client, q=scenario.exact_code)
    values = [row["value"] for row in relevance["results"]]  # type: ignore[index]

    # El tercero vinculado a dos compañías aparece una sola vez y el orden es
    # por relevancia (exacto, prefijo, contenido), no por código.
    assert values == [scenario.exact_id, scenario.prefix_id, scenario.substring_id]
    assert len(values) == len(set(values))
    assert values.count(scenario.exact_id) == 1
    assert relevance["has_more"] is False

    alpha = _party_results(scenario.client, q="Tercero", company=scenario.company_alpha)
    alpha_values = [row["value"] for row in alpha["results"]]  # type: ignore[index]
    assert set(alpha_values) == {scenario.exact_id, scenario.prefix_id, scenario.substring_id}
    assert scenario.foreign_id not in alpha_values

    beta = _party_results(scenario.client, q="Tercero", company=scenario.company_beta)
    beta_values = [row["value"] for row in beta["results"]]  # type: ignore[index]
    assert set(beta_values) == {scenario.exact_id, scenario.foreign_id}
    assert beta_values.count(scenario.exact_id) == 1


def test_party_search_select_relevance_and_company_scope(party_search_scenario):
    """El smart-select de terceros respeta relevancia, deduplicación y alcance."""
    _assert_party_search_contract(party_search_scenario)


@pytest.mark.database
def test_party_search_select_relevance_and_company_scope_on_configured_engine(party_search_scenario):
    """La misma regresión corre sobre PostgreSQL, donde DISTINCT+ORDER BY falla (#909)."""
    _assert_party_search_contract(party_search_scenario)
