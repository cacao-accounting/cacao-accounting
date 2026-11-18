# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Verifica el filtro de período para un usuario con acceso de Inventario."""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.auth import proteger_passwd
from cacao_accounting.database import Roles, RolesAccess, RolesUser, User, UserCompanyAccess, database
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre


def test_entregas_muestra_periodos_de_compania_autorizada(entorno_contable):
    """El picker de entregas incluye la compañía accesible por Inventario."""
    app = entorno_contable.app
    with app.app_context():
        user = User(
            user=f"inventory-reader-{uuid4().hex}",
            name="Consulta de Inventario",
            password=proteger_passwd("inventory-reader-test"),
            classification="user",
            active=True,
            company="cacao",
        )
        database.session.add(user)
        database.session.flush()
        role = Roles(name=f"inventory-reader-{uuid4().hex}", note="Consulta de Inventario")
        database.session.add(role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(
                    rol_id=role.id,
                    module_id=obtener_id_modulo_por_nombre("inventory"),
                    access=True,
                    view=True,
                ),
                RolesUser(user_id=user.id, role_id=role.id, active=True),
                UserCompanyAccess(user_id=user.id, company_code="cacao"),
            ]
        )
        database.session.commit()
        user_id, auth_version = user.id, user.auth_version

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_auth_version"] = auth_version
        session["_fresh"] = True

    response = client.get("/sales/delivery-note/list?company=cacao")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="list-company"' in html
    assert 'id="list-period-from"' in html
    assert 'id="list-period-to"' in html
    assert 'initialValue: "cacao"' in html
    assert 'initialLabel: "Mayo 2026"' in html
    assert 'initialValue: "alpha"' not in html


def test_entregas_no_se_filtran_por_la_compania_del_primer_modulo(entorno_contable):
    """Ventas en una compañía e Inventario en otra no recortan el listado (#2110)."""
    from datetime import date

    from cacao_accounting.database import DeliveryNote, Entity

    app = entorno_contable.app
    suffix = uuid4().hex[:6]
    cacao_document = f"DN-CACAO-{suffix}"
    alpha_document = f"DN-ALPHA-{suffix}"
    with app.app_context():
        if database.session.execute(database.select(Entity).filter_by(code="alpha")).scalar_one_or_none() is None:
            database.session.add(
                Entity(
                    code="alpha",
                    name="Alpha",
                    company_name="Alpha Company",
                    tax_id=f"J-ALPHA-{suffix}",
                    currency="NIO",
                    enabled=True,
                )
            )
            database.session.flush()
        user = User(
            user=f"mixed-reader-{suffix}",
            name="Consulta mixta Ventas/Inventario",
            password=proteger_passwd("mixed-reader-test"),
            classification="user",
            active=True,
            company="cacao",
        )
        database.session.add(user)
        database.session.flush()
        role = Roles(name=f"mixed-reader-{suffix}", note="Ventas e Inventario en compañías distintas")
        database.session.add(role)
        database.session.flush()
        database.session.add_all(
            [
                RolesAccess(
                    rol_id=role.id,
                    module_id=obtener_id_modulo_por_nombre("sales"),
                    access=True,
                    view=True,
                ),
                RolesAccess(
                    rol_id=role.id,
                    module_id=obtener_id_modulo_por_nombre("inventory"),
                    access=True,
                    view=True,
                ),
                RolesUser(user_id=user.id, role_id=role.id, active=True),
                UserCompanyAccess(user_id=user.id, company_code="cacao"),
                UserCompanyAccess(user_id=user.id, company_code="alpha"),
                DeliveryNote(
                    company="cacao",
                    document_no=cacao_document,
                    customer_name="Cliente Cacao",
                    posting_date=date(2026, 5, 10),
                ),
                DeliveryNote(
                    company="alpha",
                    document_no=alpha_document,
                    customer_name="Cliente Alpha",
                    posting_date=date(2026, 5, 11),
                ),
            ]
        )
        database.session.commit()
        user_id, auth_version = user.id, user.auth_version

    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_auth_version"] = auth_version
        session["_fresh"] = True

    response = client.get("/sales/delivery-note/list")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert cacao_document in html
    assert alpha_document in html

    with app.app_context():
        for document in (cacao_document, alpha_document):
            note = database.session.execute(database.select(DeliveryNote).filter_by(document_no=document)).scalar_one()
            database.session.delete(note)
        database.session.commit()


def test_resolver_de_periodo_usa_la_union_de_los_modulos(entorno_contable, monkeypatch):
    """Con concesiones distintas por módulo no se elige una compañía ambigua (#2110).

    El modelo actual comparte las concesiones de compañía entre módulos, así que
    el caso no se alcanza por HTTP; esta prueba fija el contrato del resolver
    para cuando la autorización sea por módulo.
    """
    from flask_login import login_user

    from cacao_accounting.ventas import services

    app = entorno_contable.app
    with app.app_context():
        user = User(
            user=f"ambiguous-reader-{uuid4().hex}",
            name="Consulta ambigua",
            password=proteger_passwd("ambiguous-reader-test"),
            classification="user",
            active=True,
            company="cacao",
        )
        database.session.add(user)
        database.session.commit()
        user_id = user.id

    class FakePermisos:
        """Concesiones por módulo para el escenario reportado."""

        def __init__(self, modulo=None, usuario=None, libro=None):
            self.consultar = True
            self._companies = {"sales": ["cacao"], "inventory": ["alpha"]}[modulo]

        def obtener_companias_autorizadas(self):
            """Devuelve las compañías del módulo simulado."""
            return list(self._companies)

    monkeypatch.setattr(services, "Permisos", FakePermisos)
    monkeypatch.setattr(services, "obtener_id_modulo_por_nombre", lambda module: module)

    with app.test_request_context("/sales/delivery-note/list"):
        login_user(database.session.get(User, user_id))
        assert services._period_company_for_query(("sales", "inventory")) is None
