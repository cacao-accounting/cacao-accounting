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


def test_dos_cambios_concurrentes_dejan_un_solo_default(tmp_path, monkeypatch):
    """#2323: dos cambios simultáneos no pueden dejar dos predeterminados."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, BrokenBarrierError

    from cacao_accounting import create_app
    from cacao_accounting.config import configuracion
    from cacao_accounting.contabilidad import services as cost_center_services
    from cacao_accounting.contabilidad.services import _ensure_single_default_cost_center

    database_uri = f"sqlite:///{tmp_path / 'cost-centers-2323.sqlite'}"
    settings = {
        **configuracion,
        "SQLALCHEMY_DATABASE_URI": database_uri,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "WTF_CSRF_ENABLED": False,
        "TESTING": True,
        "MODO_ESCRITORIO": True,
    }
    writer = create_app(settings)
    reader = create_app(settings)
    entity = f"X{uuid4().hex[:7].upper()}"
    with writer.app_context():
        from cacao_accounting.database import Currency

        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add(
            Entity(
                code=entity,
                name=entity,
                company_name=entity,
                tax_id=f"T{entity}",
                currency="NIO",
                status="activo",
                enabled=True,
            )
        )
        database.session.flush()
        for code, is_default in (("MAIN", True), ("A", False), ("B", False)):
            database.session.add(
                CostCenter(
                    entity=entity,
                    code=code,
                    name=code,
                    active=True,
                    enabled=True,
                    default=is_default,
                    group=False,
                    status="activo",
                )
            )
        database.session.commit()
        target_ids = {
            code: str(
                database.session.execute(database.select(CostCenter.id).filter_by(entity=entity, code=code)).scalar_one()
            )
            for code in ("A", "B")
        }

    barrier = Barrier(2)
    choose_barrier = Barrier(2)
    original_choose = cost_center_services._choose_default_cost_center

    def _synchronized_choose(centers, preferred_id):
        try:
            choose_barrier.wait(timeout=0.2)
        except BrokenBarrierError:
            pass
        return original_choose(centers, preferred_id)

    monkeypatch.setattr(cost_center_services, "_choose_default_cost_center", _synchronized_choose)

    def _change(app, target_id: str) -> None:
        with app.app_context():
            barrier.wait(timeout=10)
            _ensure_single_default_cost_center(entity, preferred_id=target_id)
            database.session.commit()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(_change, writer, target_ids["A"]),
            executor.submit(_change, reader, target_ids["B"]),
        ]
        for future in futures:
            future.result(timeout=30)

    with writer.app_context():
        database.session.expire_all()
        defaults = database.session.execute(database.select(CostCenter).filter_by(entity=entity, default=True)).scalars().all()
        assert len(defaults) == 1
        assert defaults[0].code in {"A", "B"}
        database.session.remove()
        database.engine.dispose()
    with reader.app_context():
        database.session.remove()
        database.engine.dispose()


def test_orden_de_locks_es_compania_y_luego_scope(app, monkeypatch):
    """#2323: el orden no se invierte respecto de las rutas de alta/edición."""
    from cacao_accounting.contabilidad import services as cost_center_services

    code = f"O{uuid4().hex[:7].upper()}"
    calls: list[str] = []
    monkeypatch.setattr(
        cost_center_services,
        "_lock_cost_center_companies",
        lambda _codes: calls.append("company"),
    )
    monkeypatch.setattr(
        "cacao_accounting.default_scope.lock_default_scope",
        lambda *args, **kwargs: calls.append("scope"),
    )
    with app.app_context():
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
        database.session.add(
            CostCenter(
                entity=code,
                code="MAIN",
                name="Main",
                active=True,
                enabled=True,
                default=True,
                group=False,
                status="activo",
            )
        )
        database.session.flush()
        try:
            cost_center_services._ensure_single_default_cost_center(code)
            assert calls == ["company", "scope"]
        finally:
            database.session.rollback()
