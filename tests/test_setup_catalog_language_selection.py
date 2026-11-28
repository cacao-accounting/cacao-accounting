# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""La selección de catálogo preexistente debe ser explícita y válida."""

from __future__ import annotations

import os
import json
from pathlib import Path

import pytest

from cacao_accounting.database import Book, Entity, database
from cacao_accounting.setup import service
from cacao_accounting.setup.service import choose_catalog_file, create_company

COMPANY_DATA = {"id": "NEW2106", "razon_social": "Empresa ejemplo", "id_fiscal": "TEST-2106", "moneda": "NIO"}


@pytest.mark.parametrize(("country", "language"), [("US", "en"), ("NI", "es")])
def test_sin_archivo_no_aplica_fallback(country, language):
    """País e idioma no seleccionan un catálogo por cuenta del usuario."""
    assert choose_catalog_file(country, language) is None


def test_archivo_explicito_se_respeta():
    """Un `catalog_name` válido se usa, no el base por defecto."""
    catalogo = choose_catalog_file("NI", "es", "us_gaap.csv")
    assert catalogo is not None
    assert os.path.basename(catalogo.file) == "us_gaap.csv"
    assert catalogo.pais == "NI"


def test_archivo_explicito_inexistente_devuelve_none():
    """Un `catalog_name` inexistente no cae al catálogo base."""
    assert choose_catalog_file("NI", "es", "no_existe.csv") is None


@pytest.mark.parametrize("catalog_name", [None, "no_existe.csv"])
def test_catalogo_ausente_no_crea_compania(app, catalog_name):
    """El rechazo ocurre antes de crear o agregar registros de compañía."""
    with app.app_context():
        company_count = database.session.query(Entity).count()
        with pytest.raises(ValueError):
            create_company(
                COMPANY_DATA, catalogo_tipo="preexistente", country="NI", idioma="es", catalogo_archivo=catalog_name
            )
        assert database.session.query(Entity).count() == company_count
        assert not any(isinstance(row, Entity) for row in database.session.new)


@pytest.mark.parametrize("mapping", [None, "{invalid json", '{"default_accounts": {}}'])
def test_catalogo_sin_mapping_valido_no_crea_compania(app, tmp_path, monkeypatch, mapping):
    """Un archivo sin mapping completo se rechaza antes de crear registros."""
    (tmp_path / "invalid.csv").write_text("codigo,nombre,rubro\n1,Caja,Asset\n", encoding="utf-8")
    if mapping is not None:
        (tmp_path / "invalid.json").write_text(mapping, encoding="utf-8")
    monkeypatch.setattr(service, "DIRECTORIO_CTAS", str(tmp_path))
    with app.app_context():
        before = database.session.query(Entity).count()
        with pytest.raises(ValueError):
            create_company(
                COMPANY_DATA, catalogo_tipo="preexistente", country="NI", idioma="es", catalogo_archivo="invalid.csv"
            )
        assert database.session.query(Entity).count() == before


@pytest.mark.parametrize("invalid_row", ["100000,Otra,Asset", "999999,,Asset", "999999,Sin rubro,"])
def test_catalogo_con_filas_invalidas_no_crea_compania(app, tmp_path, monkeypatch, invalid_row):
    """Códigos duplicados o campos requeridos vacíos no llegan a persistirse."""
    source = Path(service.DIRECTORIO_CTAS)
    content = (source / "us_gaap.csv").read_text(encoding="utf-8")
    (tmp_path / "broken.csv").write_text(content + "\n" + invalid_row + ",,,,\n", encoding="utf-8")
    (tmp_path / "broken.json").write_text((source / "us_gaap.json").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(service, "DIRECTORIO_CTAS", str(tmp_path))
    monkeypatch.setitem(app.config, "MODO_ESCRITORIO", False)
    with app.app_context():
        with pytest.raises(ValueError, match="catálogo seleccionado"):
            create_company(
                COMPANY_DATA, catalogo_tipo="preexistente", country="NI", idioma="es", catalogo_archivo="broken.csv"
            )
        assert database.session.execute(database.select(Entity).filter_by(code="NEW2106")).scalar_one_or_none() is None


@pytest.mark.parametrize("cash_code", ["NO-EXISTE", "111200", "200000"])
def test_mapping_no_valido_no_deja_compania_ni_libro(app, tmp_path, monkeypatch, cash_code):
    """Un código ausente o de tipo incompatible se rechaza antes de crear registros."""
    source = Path(service.DIRECTORIO_CTAS)
    (tmp_path / "bad_mapping.csv").write_text((source / "us_gaap.csv").read_text(encoding="utf-8"), encoding="utf-8")
    mapping = json.loads((source / "us_gaap.json").read_text(encoding="utf-8"))
    mapping["default_accounts"]["default_cash"] = cash_code
    (tmp_path / "bad_mapping.json").write_text(json.dumps(mapping), encoding="utf-8")
    monkeypatch.setattr(service, "DIRECTORIO_CTAS", str(tmp_path))
    monkeypatch.setitem(app.config, "MODO_ESCRITORIO", False)
    with app.app_context():
        with pytest.raises(ValueError, match="catálogo seleccionado"):
            create_company(
                COMPANY_DATA, catalogo_tipo="preexistente", country="NI", idioma="es", catalogo_archivo="bad_mapping.csv"
            )
        assert database.session.execute(database.select(Entity).filter_by(code="NEW2106")).scalar_one_or_none() is None
        assert database.session.execute(database.select(Book).filter_by(entity="NEW2106")).scalar_one_or_none() is None
