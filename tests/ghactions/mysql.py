from cacao_accounting import create_app
from cacao_accounting.config import configuracion

app = create_app(configuracion)
app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root@localhost:3306/cacaodb"


def test_mysql():
    with app.app_context():
        from cacao_accounting.database import db

        db.create_all()
        from cacao_accounting.datos import base_data, demo_data

        base_data()
        demo_data()


from base_test import BaseTest


class MyQSL(BaseTest):
    app = create_app(configuracion)
    app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://root@localhost:3306/cacaodb"
    app.app_context().push()


class TestMYSQL(MyQSL):
    def test_mysql_en_configuracion(self):
        url = str(self.app.config["SQLALCHEMY_DATABASE_URI"])
        assert url.startswith("mysql")


from unittest import TestCase
from crud import Entidad


class TestEntidad(MyQSL, Entidad, TestCase):
    pass
