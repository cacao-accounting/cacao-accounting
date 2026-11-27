# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1678: la descarga de plantillas no depende de un archivo compartido."""

from __future__ import annotations

import io
import threading
from contextlib import contextmanager

import openpyxl
import pytest

from cacao_accounting.database import Modules, database

# Rutas que dejaron las implementaciones rechazadas: el directorio temporal por
# petición y el archivo compartido del código anterior a esa corrección.
PREFIJO_TEMPORAL = "import-template-"
CAMINO_COMPARTIDO = ("templates", "template_customer.csv")


def _estado_modulo_imports() -> tuple[str, bool | None] | None:
    """Devuelve identidad y estado del módulo, o ``None`` si no existe."""
    modulo = database.session.execute(database.select(Modules).filter_by(module="imports")).scalar_one_or_none()
    return None if modulo is None else (modulo.id, modulo.enabled)


def _restaura_modulo_imports(estado: tuple[str, bool | None] | None) -> None:
    """Restaura existencia y ``enabled`` en una sesión nueva de limpieza."""
    database.session.remove()
    modulo = database.session.execute(database.select(Modules).filter_by(module="imports")).scalar_one_or_none()
    if estado is None:
        if modulo is not None:
            database.session.delete(modulo)
    else:
        if modulo is None:
            database.session.add(Modules(id=estado[0], module="imports", default=False, enabled=estado[1]))
        else:
            modulo.enabled = estado[1]
    database.session.commit()


@contextmanager
def modulo_imports_activado(app):
    """Habilita el módulo y restaura su estado previo incluso si falla la prueba."""
    with app.app_context():
        estado = _estado_modulo_imports()
        modulo = database.session.execute(database.select(Modules).filter_by(module="imports")).scalar_one_or_none()
        if modulo is None:
            database.session.add(Modules(module="imports", default=False, enabled=True))
        else:
            modulo.enabled = True
        database.session.commit()
        try:
            yield
        finally:
            _restaura_modulo_imports(estado)


@pytest.fixture
def instancia_aislada(app, tmp_path, monkeypatch):
    """Dirige ``instance_path`` a un directorio vacío y exclusivo de la prueba."""
    instancia = tmp_path / "instance"
    instancia.mkdir()
    monkeypatch.setattr(app, "instance_path", str(instancia))
    return instancia


def _residuo_temporal(instancia) -> list[str]:
    """Nombres ``import-template-*`` sobrevivientes bajo el directorio de instancia."""
    return [p.name for p in instancia.iterdir() if p.name.startswith(PREFIJO_TEMPORAL)]


def test_cada_descarga_usa_el_idioma_de_su_peticion_sin_dejar_archivos(
    app, entorno_contable, authenticated_client, monkeypatch, instancia_aislada
):
    """Dos locales seguidos no comparten contenido ni escriben en ``instance_path``."""
    with modulo_imports_activado(app):
        from cacao_accounting.imports import routes as modulo_rutas

        cliente = authenticated_client("admin")
        cuerpos = {}
        for idioma, encabezado in (("es", "nombre,"), ("en", "name,")):
            monkeypatch.setattr(modulo_rutas, "get_locale", lambda: idioma)
            respuesta = cliente.get("/imports/template/customer?format=csv")
            assert respuesta.status_code == 200, respuesta.status_code
            cuerpos[idioma] = respuesta.data.decode("utf-8-sig").strip()
            assert cuerpos[idioma].startswith(encabezado), cuerpos[idioma][:40]

        # El defecto original era un archivo compartido entre peticiones: si algo vuelve
        # a materializarse en disco, el contenido dependerá del orden de escritura.
        assert cuerpos["es"] != cuerpos["en"]
        assert not _residuo_temporal(instancia_aislada)
        assert not (instancia_aislada / CAMINO_COMPARTIDO[0] / CAMINO_COMPARTIDO[1]).exists()


def test_descarga_no_depende_de_que_exista_instance_path(app, entorno_contable, authenticated_client, tmp_path, monkeypatch):
    """Una instalación limpia responde 200 aunque falte el directorio de instancia."""
    with modulo_imports_activado(app):
        monkeypatch.setattr(app, "instance_path", str(tmp_path / "instance" / "ausente"))
        assert not (tmp_path / "instance" / "ausente").exists()

        respuesta = authenticated_client("admin").get("/imports/template/customer?format=csv")

        assert respuesta.status_code == 200
        assert respuesta.data.decode("utf-8-sig").strip().startswith("nombre,")
        assert respuesta.mimetype == "text/csv"


@pytest.mark.parametrize("formato", ["xlsx", "ods"])
def test_plantillas_binarias_se_entregan_completas(app, entorno_contable, authenticated_client, formato, instancia_aislada):
    """El buffer en memoria debe rebobinarse: entregado desde el final sale vacío."""
    with modulo_imports_activado(app):
        respuesta = authenticated_client("admin").get(f"/imports/template/customer?format={formato}")

        assert respuesta.status_code == 200
        esperado = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if formato == "xlsx"
            else "application/vnd.oasis.opendocument.spreadsheet"
        )
        assert respuesta.mimetype == esperado
        assert "attachment" in respuesta.headers["Content-Disposition"]
        assert respuesta.data[:2] == b"PK", "el cuerpo debe ser un ZIP válido"
        assert not _residuo_temporal(instancia_aislada)
        if formato == "xlsx":
            hoja = openpyxl.load_workbook(io.BytesIO(respuesta.data)).active
            assert str(hoja["A1"].value).startswith("nombre"), "la fila de encabezados debe existir"


def test_construccion_concurrente_no_comparte_buffer(monkeypatch):
    """Dos hebras simultáneas obtienen payloads independientes, sin recurso compartido."""
    from cacao_accounting.imports import routes as modulo_rutas
    from cacao_accounting.imports.adapters.customer import CustomerAdapter

    idioma_hilo = threading.local()
    monkeypatch.setattr(modulo_rutas, "get_locale", lambda: getattr(idioma_hilo, "codigo", "es"))
    adapter = CustomerAdapter()
    barrera = threading.Barrier(2, timeout=30)
    resultados: dict[str, str] = {}
    errores: list[str] = []

    def construir(codigo: str, encabezado: str) -> None:
        """Genera la plantilla al mismo tiempo que la otra hebra."""
        try:
            idioma_hilo.codigo = codigo
            barrera.wait(timeout=30)
            cuerpo, _ = modulo_rutas._plantilla_en_memoria(adapter, "csv")
            texto = cuerpo.read().decode("utf-8")
            if not texto.startswith(encabezado):
                errores.append(f"{codigo}: {texto[:40]!r}")
                return
            resultados[codigo] = texto
        except Exception as exc:  # noqa: BLE001 - el fallo de la hebra debe verse en la prueba
            errores.append(f"{codigo}: {exc!r}")

    hebras = [
        threading.Thread(target=construir, args=("es", "nombre,")),
        threading.Thread(target=construir, args=("en", "name,")),
    ]
    for hebra in hebras:
        hebra.start()
    for hebra in hebras:
        hebra.join(timeout=60)
        assert not hebra.is_alive(), "la construcción concurrente quedó bloqueada"

    assert not errores, errores
    assert set(resultados) == {"es", "en"}
    assert resultados["es"] != resultados["en"], "ambas hebras leyeron el mismo contenido"


@pytest.mark.parametrize("estado_inicial", ["ausente", "deshabilitado", "habilitado"])
def test_estado_del_modulo_se_restaura_tras_un_fallo(app, request, estado_inicial):
    """Existencia y ``enabled`` vuelven a su valor tras una aserción fallida."""
    with app.app_context():
        original = _estado_modulo_imports()
        database.session.remove()
        if estado_inicial == "ausente":
            modulo = database.session.execute(database.select(Modules).filter_by(module="imports")).scalar_one_or_none()
            if modulo is not None:
                database.session.delete(modulo)
        else:
            modulo = database.session.execute(database.select(Modules).filter_by(module="imports")).scalar_one_or_none()
            if modulo is None:
                database.session.add(Modules(module="imports", default=False, enabled=estado_inicial == "habilitado"))
            else:
                modulo.enabled = estado_inicial == "habilitado"
        database.session.commit()
    request.addfinalizer(lambda: _restaura_modulo_imports(original))

    with pytest.raises(AssertionError, match="fallo simulado"):
        with modulo_imports_activado(app):
            assert False, "fallo simulado"

    with app.app_context():
        actual = _estado_modulo_imports()
        if estado_inicial == "ausente":
            assert actual is None
        else:
            assert actual is not None
            assert actual[1] is (estado_inicial == "habilitado")
