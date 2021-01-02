from unittest import TestCase
from crud import Entidad
from cacao_accounting import create_app
from cacao_accounting.config import configuracion


class PostgreSQL:
    from cacao_accounting.database import db
    from cacao_accounting.datos import base_data

    db = db
    app = create_app(configuracion)
    app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql+psycopg2://cacao:cacao@localhost:5432/cacao"
    app.app_context().push()

    def setUp(self):
        self.db.drop_all()
        self.db.create_all()
        self.base_data()

    def tearDown(self):
        pass


class TestPostgreSQL(PostgreSQL, TestCase):
    def test_sqlite_en_configuracion(self):
        url = str(self.app.config["SQLALCHEMY_DATABASE_URI"])
        assert url.startswith("postgresql")


class TestEntidad(Entidad, PostgreSQL):
    app = create_app(configuracion)
    app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql+psycopg2://cacao:cacao@localhost:5432/cacao"
    app.app_context().push()
