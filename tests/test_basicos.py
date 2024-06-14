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

    def test_flask_subclass(self):
        from flask import Flask

        self.assertIsInstance(self.app, Flask)
