import unittest


class TestBasicos(unittest.TestCase):
    def setUp(self):
        from cacao_accounting import create_app
        from cacao_accounting.config import configuracion

        self.app = create_app(configuracion)
        self.app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.app.app_context().push()

    def test_importable(self):
        """El proyecto debe poder importarse sin errores."""

        assert self.app

    def test_cli(self):
        self.app.test_cli_runner()


class TestInstanciasClase(unittest.TestCase):
    def setUp(self):
        from cacao_accounting import create_app
        from cacao_accounting.config import configuracion

        self.app = create_app(configuracion)
        self.app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.app.app_context().push()

    def test_flask(self):
        from flask import Flask

        self.assertIsInstance(self.app, Flask)

    def test_flask_bluepints(self):
        from flask import Blueprint

        from cacao_accounting.admin import admin

        self.assertIsInstance(admin, Blueprint)

        from cacao_accounting.app import cacao_app

        self.assertIsInstance(cacao_app, Blueprint)

        from cacao_accounting.auth import login

        self.assertIsInstance(login, Blueprint)


def test_encryp_passwd():
    from cacao_accounting.auth import proteger_passwd

    p = proteger_passwd("queonzabalanza")
    assert p is not None


def test_valida_url_postgresql_estandar():
    from cacao_accounting.config import valida_direccion_base_datos

    assert valida_direccion_base_datos("postgresql://url.tech/database?sslmode=require") is True


def test_normaliza_url_postgresql_pg8000_sslmode_y_channel_binding():
    from cacao_accounting.config import normaliza_direccion_base_datos

    uri, opciones = normaliza_direccion_base_datos("postgresql://url.tech/database?sslmode=require&channel_binding=require")

    assert uri == "postgresql+pg8000://url.tech/database"
    assert "connect_args" in opciones
    assert "ssl_context" in opciones["connect_args"]


def test_build_version_prefers_prerelease_over_postrelease():
    from cacao_accounting.version import build_version

    assert build_version("1", "2", "3", "dev20250629", "post20250629") == "1.2.3.dev20250629"


def test_build_version_uses_postrelease_when_no_prerelease():
    from cacao_accounting.version import build_version

    assert build_version("1", "2", "3", None, "post20250629") == "1.2.3.post20250629"


def test_build_version_returns_plain_semver_without_release_suffixes():
    from cacao_accounting.version import build_version

    assert build_version("1", "2", "3") == "1.2.3"


def test_falla_verificar_conn_db(request):
    from cacao_accounting import create_app

    if request.config.getoption("--slow") == "True":

        app = create_app({"SQLALCHEMY_DATABASE_URI": "postgresql+pg8000://user:password@host"})
        from cacao_accounting.database.helpers import verifica_coneccion_db

        assert verifica_coneccion_db(app) is False


def test_usuarios_compañias_no_creados(request):
    from cacao_accounting import create_app

    if request.config.getoption("--slow") == "True":

        app = create_app({"SQLALCHEMY_DATABASE_URI": "postgresql+pg8000://user:password@host"})

        from cacao_accounting.database.helpers import entidades_creadas, usuarios_creados

        with app.app_context():
            assert entidades_creadas() is False
            assert usuarios_creados() is False
