from unittest import TestCase
from crud import Entidad
from cacao_accounting import create_app
from cacao_accounting.config import configuracion


class MySQL:
    from cacao_accounting.database import db
    from cacao_accounting.datos import base_data

    db = db
    app = create_app(configuracion)
    app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root@localhost:3306/cacaodb"
    app.app_context().push()

    def setUp(self):
        self.db.drop_all()
        self.db.create_all()
        self.base_data()

    def tearDown(self):
        pass


class TestMySQL(MySQL, TestCase):
    def test_sqlite_en_configuracion(self):
        url = str(self.app.config["SQLALCHEMY_DATABASE_URI"])
        assert url.startswith("mysql")


class TestEntidad(Entidad, MySQL):
    app = create_app(configuracion)
    app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root@localhost:3306/cacaodb"
    app.app_context().push()
