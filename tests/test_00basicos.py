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
