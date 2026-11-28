# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#1775: un libro referenciado por mapeo activo no puede cambiar de compañía."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import inspect, select

from cacao_accounting.database import (
    Book,
    Entity,
    LedgerMappingRule,
    User,
    UserCompanyAccess,
    database,
)


def _cliente(app):
    """Autentica al administrador de la aplicación aislada."""
    with app.app_context():
        admin = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        admin_id = str(inspect(admin).identity[0])
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = admin_id
        session["_fresh"] = True
    return client


def test_edicion_de_libro_con_mapeo_activo_se_rechaza(entorno_contable_aislado):
    """El guard conserva la compañía y la regla vigente sin dejar referencias huérfanas."""
    app = entorno_contable_aislado.app
    suffix = uuid4().hex[:6]
    with app.app_context():
        beta = Entity(
            code=f"B{suffix}",
            name=f"Beta {suffix}",
            company_name=f"Beta {suffix} SA",
            tax_id=f"T-{suffix}",
            currency="NIO",
            enabled=True,
        )
        database.session.add(beta)
        database.session.flush()
        book = Book(
            code="BOOK1775",
            name="Libro mapeado",
            entity="cacao",
            currency="NIO",
            status="activo",
            is_primary=False,
        )
        database.session.add(book)
        database.session.flush()
        rule = LedgerMappingRule(
            source_book="DEFAULT_BOOK",
            target_book=book.code,
            rule_description="Regla vigente 1775",
            is_active=True,
        )
        database.session.add(rule)
        admin = database.session.execute(select(User).filter_by(user="admin")).scalar_one()
        database.session.add(UserCompanyAccess(user_id=admin.id, company_code=beta.code))
        database.session.commit()
        rule_id = rule.id
        book_code = book.code
        beta_code = beta.code

    response = _cliente(app).post(
        f"/accounting/book/edit/{book_code}",
        data={
            "id": book_code,
            "nombre": "Libro mapeado",
            "entidad": beta_code,
            "moneda": "NIO",
            "estado": "activo",
        },
    )

    assert response.status_code == 200
    assert "No se puede cambiar compañía o moneda de un libro con historial contable" in response.get_data(as_text=True)
    with app.app_context():
        persisted = database.session.execute(select(Book).filter_by(code=book_code)).scalar_one()
        persisted_rule = database.session.get(LedgerMappingRule, rule_id)
        assert persisted.entity == "cacao"
        assert persisted_rule.is_active is True
