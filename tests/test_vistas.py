# Copyright 2020 William José Moreno Reyes
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Contributors:
# - William José Moreno Reyes


import pytest
import requests
from cacao_accounting import create_app as app_factory


@pytest.fixture
def client():
    app = app_factory(
        {
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": SQLITE,
            "SECRET_KEY": "jg2ja6ñl3ssl5dak7sj1dkl8asj4fk8jj9",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SESSION_PROTECTION": None,
            "LIVESERVER_PORT": 4589,
            "LIVESERVER_TIMEOUT": 10,
        }
    )
    with flaskr.app.test_client() as client:
        with flaskr.app.app_context():
            yield client


try:
    # Ejecute python tests/server.py en una terminal distinta para ejecutar estas pruebas unitarias
    import time

    time.sleep(3)
    with requests.Session() as session:
        login = session.post("http://localhost:7563/login", data={"usuario": "cacao", "acceso": "cacao"})

        def test_inicio():
            r = requests.get("http://localhost:7563/login")
            assert "Cacao Accounting" in r.text
            assert "/static/css/signin.css" in r.text
            assert "Inicio de Sesión" in r.text

        # <-------------------------------------------------------------------------------------------------------------> #
        # Aplicacion Principal
        def test_app():
            r = session.get("http://localhost:7563/app")
            assert "Aplicacion Contable para Micro Pequeñas y Medianas Empresas." in r.text

        # <-------------------------------------------------------------------------------------------------------------> #
        # Modulo Contabilidad
        def test_contabilidad():
            r = session.get("http://localhost:7563/accounts")
            assert "Módulo Contabilidad." in r.text

        # <-------------------------------------------------------------------------------------------------------------> #
        # Entidades
        def test_entidades():
            r = session.get("http://localhost:7563/accounts/entities")
            assert "Listado de Entidades." in r.text

        def test_entidad():
            r = session.get("http://localhost:7563/accounts/entity/cacao")
            assert "Entidad." in r.text
            assert "Información General" in r.text

        def tes_entidad_nueva():
            r = session.get("http://localhost:7563/accounts/entities/new")
            assert "Crear Nueva Entidad." in r.text

        # <-------------------------------------------------------------------------------------------------------------> #
        # Unidades
        def test_unidades():
            r = session.get("http://localhost:7563/accounts/units")
            assert "Listado de Unidades de Negocio." in r.text

        def test_unidad():
            r = session.get("http://localhost:7563/accounts/unit/masaya")
            assert "Masaya" in r.text

        # <-------------------------------------------------------------------------------------------------------------> #
        # Catalogo de Cuentas
        def text_catalogo():
            r = session.get("http://localhost:7563/accounts/accounts")
            assert "Catálogo de Cuentas Contables." in r.text

        # <-------------------------------------------------------------------------------------------------------------> #
        # Centros de Costos
        def test_centros_de_costos():
            r = session.get("http://localhost:7563/accounts/ccenter")
            assert "Listado de Centros de Costos." in r.text

        # <-------------------------------------------------------------------------------------------------------------> #
        # Proyectos
        def test_proyectos():
            r = session.get("http://localhost:7563/accounts/projects")
            assert "Listado de Proyectos." in r.text

        # <-------------------------------------------------------------------------------------------------------------> #
        # Monedas
        def test_monedas():
            r = session.get("http://localhost:7563/currencies")
            assert "Listado de Monedas." in r.text

        # <-------------------------------------------------------------------------------------------------------------> #
        # Tasas de Cambio
        def test_tasas_de_cambio():
            r = session.get("http://localhost:7563/accounts/exchange")
            assert "Listado de Tasas de Cambio." in r.text


except requests.exceptions.ConnectionError:
    pass
