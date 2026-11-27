# SPDX-License-Identifier: Apache-2.0
"""#2323: cada compa??a debe tener exactamente un centro de costo predeterminado."""

from __future__ import annotations

from uuid import uuid4

import pytest

from cacao_accounting.database import CostCenter, Entity, Modules, database


@pytest.fixture
def admin_mod(app):
    with app.app_context():
        mod = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        created = False
        prev = True
        if mod is None:
            mod = Modules(module="admin", default=False, enabled=True)
            database.session.add(mod)
            created = True
        else:
            prev = bool(mod.enabled)
            mod.enabled = True
        database.session.commit()
    yield
    with app.app_context():
        mod = database.session.execute(database.select(Modules).filter_by(module="admin")).scalar_one_or_none()
        if mod is not None:
            if created:
                database.session.delete(mod)
            else:
                mod.enabled = prev
            database.session.commit()


def _count_defaults(app, entity_code: str) -> int:
    with app.app_context():
        return (
            database.session.execute(
                database.select(database.func.count(CostCenter.id)).filter_by(entity=entity_code, default=True)
            ).scalar()
            or 0
        )


def _find_default(app, entity_code: str) -> CostCenter | None:
    with app.app_context():
        return database.session.execute(
            database.select(CostCenter).filter_by(entity=entity_code, default=True)
        ).scalar_one_or_none()


def test_setup_creates_default_cost_center(app):
    from cacao_accounting.setup.repository import create_default_entity, create_default_cost_center

    code = f"C{uuid4().hex[:7].upper()}"
    with app.app_context():
        entity = create_default_entity(
            {
                "id": code,
                "razon_social": f"Co {code}",
                "nombre_comercial": f"Co {code}",
                "id_fiscal": f"T{code}",
                "moneda": "NIO",
            },
            status="activo",
            default=False,
        )
        database.session.add(entity)
        database.session.flush()
        cc = create_default_cost_center(entity)
        database.session.commit()
        assert cc.default is True
        assert cc.code == "MAIN"
        assert cc.entity == code
        assert _count_defaults(app, code) == 1


def test_nuevo_centro_costo_marca_unico_default(app, authenticated_client, admin_mod):
    client = authenticated_client("admin")
    # use existing company from fixtures
    company = "cacao"
    code = f"CC{uuid4().hex[:6].upper()}"

    resp = client.post(
        "/accounting/costs_center/new",
        data={
            "id": code,
            "nombre": "CC test",
            "entidad": company,
            "activo": "y",
            "predeterminado": "y",
            "grupo": "",
            "padre": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    with app.app_context():
        rows = database.session.execute(database.select(CostCenter).filter_by(entity=company, default=True)).scalars().all()
        assert len(rows) == 1
        assert rows[0].code == code


@pytest.fixture
def default_cacao(app, admin_mod):
    """Garantiza el centro predeterminado base que estas pruebas editan o eliminan."""
    del admin_mod
    from cacao_accounting.contabilidad.services import _ensure_single_default_cost_center

    with app.app_context():
        centro = _ensure_single_default_cost_center("cacao")
        database.session.commit()
        return str(centro.id)


def test_no_permite_desmarcar_unico_default(app, authenticated_client, default_cacao):
    client = authenticated_client("admin")
    company = "cacao"
    cc_id = default_cacao
    with app.app_context():
        current = database.session.get(CostCenter, cc_id)

    resp = client.post(
        f"/accounting/costs_center/{cc_id}/edit",
        data={"nombre": current.name, "entidad": company, "activo": "y", "predeterminado": "", "grupo": "", "padre": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True).lower()
    assert "predeterminado" in body
    assert _count_defaults(app, company) == 1


def test_no_permite_eliminar_unico_default(app, authenticated_client, default_cacao):
    client = authenticated_client("admin")
    company = "cacao"
    cc_id = default_cacao

    resp = client.post(f"/accounting/costs_center/{cc_id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        still = database.session.get(CostCenter, cc_id)
        assert still is not None
        assert bool(still.default) is True
    assert _count_defaults(app, company) == 1


def test_cambio_default_es_atomico(app, authenticated_client, admin_mod):
    client = authenticated_client("admin")
    company = "cacao"
    code = f"ND{uuid4().hex[:6].upper()}"
    # create non-default
    resp = client.post(
        "/accounting/costs_center/new",
        data={"id": code, "nombre": "Nuevo default", "entidad": company, "activo": "y", "grupo": "", "padre": ""},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)
    with app.app_context():
        new_cc = database.session.execute(database.select(CostCenter).filter_by(entity=company, code=code)).scalar_one()
        new_id = new_cc.id

    resp = client.post(
        f"/accounting/costs_center/{new_id}/edit",
        data={"nombre": "Nuevo default", "entidad": company, "activo": "y", "predeterminado": "y", "grupo": "", "padre": ""},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    with app.app_context():
        defaults = (
            database.session.execute(database.select(CostCenter).filter_by(entity=company, default=True)).scalars().all()
        )
        assert len(defaults) == 1
        assert defaults[0].id == new_id


def test_empresas_independientes(app):
    from cacao_accounting.contabilidad.services import _ensure_single_default_cost_center

    with app.app_context():
        codes = []
        for _ in range(2):
            code = f"E{uuid4().hex[:7].upper()}"
            database.session.add(
                Entity(
                    code=code,
                    name=code,
                    company_name=code,
                    tax_id=f"T{code}",
                    currency="NIO",
                    status="activo",
                    enabled=True,
                )
            )
            database.session.flush()
            cc = CostCenter(
                entity=code,
                code="MAIN",
                name="P",
                active=True,
                enabled=True,
                default=True,
                group=False,
                status="activo",
            )
            database.session.add(cc)
            codes.append(code)
        database.session.commit()

        _ensure_single_default_cost_center(codes[0])
        database.session.commit()
        assert _count_defaults(app, codes[0]) == 1
        assert _count_defaults(app, codes[1]) == 1


def test_normaliza_main_historico_no_posteable(app):
    """Si MAIN existe pero no es posteable y no hay otro candidato, se reactiva MAIN (#2323)."""
    from cacao_accounting.contabilidad.services import _ensure_single_default_cost_center

    code = f"H{uuid4().hex[:7].upper()}"
    with app.app_context():
        database.session.add(
            Entity(code=code, name=code, company_name=code, tax_id=f"T{code}", currency="NIO", status="activo", enabled=True)
        )
        database.session.flush()
        database.session.add(
            CostCenter(
                entity=code,
                code="MAIN",
                name="Main historico",
                active=False,
                enabled=False,
                default=True,
                group=True,
                status="inactivo",
            )
        )
        database.session.commit()

        chosen = _ensure_single_default_cost_center(code)
        database.session.commit()
        assert chosen.code == "MAIN"
        assert bool(chosen.default) is True
        assert bool(chosen.active) is True
        assert bool(chosen.enabled) is True
        assert bool(chosen.group) is False
        defaults = database.session.execute(database.select(CostCenter).filter_by(entity=code, default=True)).scalars().all()
        assert len(defaults) == 1
        assert defaults[0].code == "MAIN"
