from unittest import TestCase
from ghactions.crud import Entidad
from cacao_accounting import create_app
from cacao_accounting.config import configuracion
from ghactions.base_test import BaseTest


class SQLite(BaseTest):
    app = create_app(configuracion)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.app_context().push()


class TestSQLite(SQLite):
    def test_sqlite_en_configuracion(self):
        url = str(self.app.config["SQLALCHEMY_DATABASE_URI"])
        assert url.startswith("sqlite")


from unittest import TestCase


class TestEntidad(Entidad, SQLite, TestCase):
    pass
