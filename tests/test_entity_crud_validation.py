# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""La edición y eliminación de entidades responde de forma controlada.

Escenario de negocio (issues #1768 y #1769): una colisión de identificación
fiscal o razón social llegaba a IntegrityError y el borrado Cloud chocaba con
el guard de modelos sensibles, ambos como HTTP 500.
"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, User, database


def _crear_app(cloud: bool = True):
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": not cloud,
            "INTERNAL_CONTROLS_ENFORCE": cloud,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Modules(module="accounting", default=False, enabled=True),
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                User(
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
                Entity(
                    code="A",
                    name="Comercial A",
                    company_name="Razón A",
                    tax_id="TAX-A",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                Entity(
                    code="B",
                    name="Comercial B",
                    company_name="Razón B",
                    tax_id="TAX-B",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
                Entity(
                    code="C",
                    name="Comercial C",
                    company_name="Razón C",
                    tax_id="TAX-C",
                    currency="NIO",
                    enabled=True,
                    status="activo",
                ),
            ]
        )
        database.session.commit()
        ids = {entity.code: entity.id for entity in database.session.execute(database.select(Entity)).scalars().all()}
    return application, ids


def _cliente(application):
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def _formulario(**overrides) -> dict[str, str]:
    datos = {
        "id_fiscal": "TAX-A",
        "nombre_comercial": "Comercial A",
        "razon_social": "Razón A",
        "habilitado": "on",
    }
    datos.update(overrides)
    return datos


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("id_fiscal", "TAX-B"),
        ("razon_social", "Razón B"),
    ],
)
def test_edicion_con_identidad_duplicada_no_responde_500(campo, valor):
    """#1768: una colisión de tax_id o razón social vuelve al formulario."""
    application, _ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post("/accounting/entity/edit/A", data=_formulario(**{campo: valor}))

        assert respuesta.status_code == 200
        assert "Ya existe otra entidad con esa identificación fiscal o razón social." in respuesta.get_data(as_text=True)
        with application.app_context():
            entidad = database.session.execute(database.select(Entity).filter_by(code="A")).scalar_one()
            assert entidad.tax_id == "TAX-A"
            assert entidad.company_name == "Razón A"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_edicion_exige_identidad_minima():
    """#1768: el servidor no acepta identificación o razón social vacías."""
    application, _ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post("/accounting/entity/edit/A", data=_formulario(id_fiscal="   "))

        assert respuesta.status_code == 200
        assert "La identificación fiscal y la razón social son obligatorias." in respuesta.get_data(as_text=True)
        with application.app_context():
            entidad = database.session.execute(database.select(Entity).filter_by(code="A")).scalar_one()
            assert entidad.tax_id == "TAX-A"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_edicion_valida_se_guarda():
    """#1768: una identidad libre sigue actualizando la entidad."""
    application, _ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.post(
            "/accounting/entity/edit/A",
            data=_formulario(id_fiscal="TAX-A2", razon_social="Razón A2", nombre_comercial="Comercial A2"),
        )

        assert respuesta.status_code == 302
        with application.app_context():
            entidad = database.session.execute(database.select(Entity).filter_by(code="A")).scalar_one()
            assert entidad.tax_id == "TAX-A2"
            assert entidad.company_name == "Razón A2"
            assert entidad.name == "Comercial A2"
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_entidad_inexistente_responde_404():
    """#1768: editar un código ausente no desreferencia None."""
    application, _ids = _crear_app()
    try:
        client = _cliente(application)
        respuesta = client.get("/accounting/entity/edit/NO-EXISTE")

        assert respuesta.status_code == 404
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_borrado_cloud_se_rechaza_controladamente():
    """#1769: el guard sensible se traduce a mensaje y la fila permanece."""
    application, ids = _crear_app(cloud=True)
    try:
        client = _cliente(application)
        respuesta = client.post(f"/accounting/entity/delete/{ids['C']}")

        assert respuesta.status_code == 302
        with application.app_context():
            entidad = database.session.get(Entity, ids["C"])
            assert entidad is not None
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_el_boton_de_borrado_no_se_muestra_en_cloud():
    """#1769: Cloud no ofrece una acción que el guard rechazará."""
    application, _ids = _crear_app(cloud=True)
    try:
        client = _cliente(application)
        html = client.get("/accounting/entity/C").get_data(as_text=True)

        assert "/accounting/entity/delete/" not in html
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
