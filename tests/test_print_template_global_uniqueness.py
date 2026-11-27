# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2131: la plantilla global es única y su siembra tolera carreras reales."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any

import pytest
from flask import Flask
from sqlalchemy import select
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateIndex

from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from cacao_accounting.database import Entity, database
from cacao_accounting.printing import seed
from cacao_accounting.printing.models import PrintTemplate

pytestmark = pytest.mark.database

DOCUMENT_TYPE = "sales_invoice"
TEMPLATE_CODE = "system_default_sales_invoice"


@pytest.fixture
def printing_app(tmp_path):
    """Construye aplicaciones aisladas que pueden compartir una base SQLite."""
    applications: list[Flask] = []

    def build(name: str = "plantillas") -> Flask:
        application = create_app(
            {
                **configuracion,
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / f'{name}.sqlite'}",
                "SQLALCHEMY_ENGINE_OPTIONS": {
                    "connect_args": {"timeout": 30},
                    "pool_size": 4,
                    "max_overflow": 0,
                },
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
                "WTF_CSRF_ENABLED": False,
                "TESTING": True,
                "MODO_ESCRITORIO": False,
                "SECRET_KEY": "print-global-test-secret",
            }
        )
        with application.app_context():
            database.create_all()
        applications.append(application)
        return application

    yield build

    for application in reversed(applications):
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def _template(
    company_code: str | None = None, *, document_type: str = DOCUMENT_TYPE, code: str = TEMPLATE_CODE
) -> PrintTemplate:
    """Crea una plantilla representativa sin depender del cuerpo del seed."""
    return PrintTemplate(
        company_code=company_code,
        document_type=document_type,
        code=code,
        name="Plantilla de prueba",
        template_body="<p>Documento</p>",
        status="published",
        is_system=company_code is None,
        is_default=False,
    )


def _single_document_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Limita la siembra al tipo documental que ejerce el caso."""
    monkeypatch.setattr(
        seed,
        "PRINTABLE_DOCUMENTS",
        {DOCUMENT_TYPE: {"label": "Factura", "root_context_name": "invoice"}},
    )


def test_esquema_rechaza_dos_plantillas_globales_iguales(printing_app):
    """Dos filas con company_code NULL no pueden compartir tipo y código."""
    application = printing_app()
    with application.app_context():
        database.session.add(_template())
        database.session.commit()
        database.session.add(_template())
        with pytest.raises(IntegrityError):
            database.session.commit()
        database.session.rollback()

        templates = database.session.execute(select(PrintTemplate)).scalars().all()
        assert len(templates) == 1
        assert templates[0].company_code is None


def test_plantilla_de_compania_coexiste_con_la_global(printing_app, monkeypatch):
    """El mismo tipo y código admite una plantilla por compañía y una global."""
    application = printing_app()
    _single_document_registry(monkeypatch)
    with application.app_context():
        database.session.add(
            Entity(
                code="EMPRESA",
                company_name="Empresa de prueba",
                tax_id="TRIBUTO-2131",
            )
        )
        database.session.commit()
        company_template = _template("EMPRESA")
        database.session.add(company_template)
        database.session.commit()
        company_template_id = company_template.id

        seed.seed_print_templates()

        templates = (
            database.session.execute(
                select(PrintTemplate).where(
                    PrintTemplate.document_type == DOCUMENT_TYPE,
                    PrintTemplate.code == TEMPLATE_CODE,
                )
            )
            .scalars()
            .all()
        )
        templates_by_company = {template.company_code: template.id for template in templates}
        assert templates_by_company["EMPRESA"] == company_template_id
        assert set(templates_by_company) == {"EMPRESA", None}


def test_siembra_repetida_actualiza_sin_duplicar(printing_app, monkeypatch):
    """La segunda siembra conserva la fila y aplica una versión anterior pendiente."""
    application = printing_app()
    _single_document_registry(monkeypatch)
    with application.app_context():
        seed.seed_print_templates()
        seed.seed_print_templates()
        template = database.session.execute(select(PrintTemplate)).scalar_one()
        template_id = template.id
        template.version = 1
        template.template_body = "<p>Versión anterior</p>"
        template.stylesheet_body = "body { color: red; }"
        database.session.commit()

        seed.seed_print_templates()
        database.session.refresh(template)

        assert database.session.execute(select(PrintTemplate)).scalars().all() == [template]
        assert template.id == template_id
        assert template.version == seed.SEED_TEMPLATE_VERSION
        assert template.template_body != "<p>Versión anterior</p>"
        assert template.stylesheet_body == seed.BASE_CSS


def test_siembra_fallida_no_confirma_plantillas_parciales(printing_app, monkeypatch):
    """Un fallo durante el lote revierte también las inserciones ya ejecutadas."""
    application = printing_app()
    original = seed._ensure_system_template
    monkeypatch.setattr(
        seed,
        "PRINTABLE_DOCUMENTS",
        {
            DOCUMENT_TYPE: {"label": "Factura", "root_context_name": "invoice"},
            "purchase_invoice": {"label": "Factura de compra", "root_context_name": "invoice"},
        },
    )

    def fail_second(document_type: str, label: Any, root_name: str) -> None:
        original(document_type, label, root_name)
        if document_type == "purchase_invoice":
            raise RuntimeError("fallo simulado después de la primera inserción")

    monkeypatch.setattr(seed, "_ensure_system_template", fail_second)
    with application.app_context():
        with pytest.raises(RuntimeError, match="fallo simulado"):
            seed.seed_print_templates()

        assert database.session.execute(select(PrintTemplate)).scalars().all() == []


def test_colision_recupera_la_plantilla_ganadora(printing_app, monkeypatch):
    """Una colisión real recupera la fila confirmada sin abortar la transacción externa."""
    application = printing_app()
    original_find = seed._find_system_template
    stale_read = True

    def find_with_stale_first_read(document_type: str, code: str, *, for_update: bool = False) -> PrintTemplate | None:
        nonlocal stale_read
        if stale_read:
            stale_read = False
            return None
        return original_find(document_type, code, for_update=for_update)

    monkeypatch.setattr(seed, "_find_system_template", find_with_stale_first_read)
    with application.app_context():
        with Session(database.engine) as winner:
            winner.add(_template())
            winner.commit()

        database.session.add(Entity(code="EMPRESA", company_name="Empresa externa", tax_id="TRIBUTO-2131-2"))
        seed._ensure_system_template(DOCUMENT_TYPE, "Factura", "invoice")
        database.session.commit()

        templates = database.session.execute(select(PrintTemplate)).scalars().all()
        assert len(templates) == 1
        database.session.expire_all()
        assert database.session.execute(select(Entity).filter_by(code="EMPRESA")).scalar_one_or_none() is not None


def test_dos_sesiones_siembran_una_sola_plantilla_global(printing_app, monkeypatch):
    """Dos sesiones que no ven la fila convergen en una única plantilla confirmada."""
    _single_document_registry(monkeypatch)
    first = printing_app("carrera-a")
    second = printing_app("carrera-b")
    barrier = Barrier(2, timeout=30)

    def sow(application: Flask) -> None:
        with application.app_context():
            barrier.wait(timeout=10)
            seed.seed_print_templates()

    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(sow, application) for application in (first, second)]
        for future in futures:
            future.result(timeout=40)

    with second.app_context():
        templates = database.session.execute(select(PrintTemplate)).scalars().all()
        assert len(templates) == 1
        assert templates[0].company_code is None
        assert templates[0].code == TEMPLATE_CODE
        assert templates[0].version == seed.SEED_TEMPLATE_VERSION


@pytest.mark.parametrize("dialect", [sqlite.dialect(), postgresql.dialect(), mysql.dialect()])
def test_indice_global_compila_en_los_motores_soportados(dialect):
    """La expresión de unicidad no depende de índices parciales privativos."""
    index = next(index for index in PrintTemplate.__table__.indexes if index.name == "uq_print_template_company_document_code")
    statement = str(CreateIndex(index).compile(dialect=dialect))

    assert "company_code IS NOT NULL" in statement
    assert "coalesce" in statement.lower()
    assert "UNIQUE" in statement.upper()
