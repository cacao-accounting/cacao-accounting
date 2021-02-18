import pytest
from unittest import TestCase
import pyodbc
from cacao_accounting import create_app
from cacao_accounting.database import db
from cacao_accounting.datos import base_data, demo_data
from database import desplegar_base_de_datos, Entidad, CentroCosto, Unidad, Proyecto, Moneda


@pytest.fixture(autouse=True)
def cargar_datos():
    db.drop_all()
    db.session.commit()
    db.create_all()
    base_data()
    yield
    db.drop_all()


CONFIG = {}
CONFIG["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
CONFIG["ENV"] = "development"
CONFIG["SECRET_KEY"] = "dev"
CONFIG["EXPLAIN_TEMPLATE_LOADING"] = True
CONFIG["DEGUG"] = True

MSSQL = "mssql+pyodbc://SA:cacao+SQLSERVER2019@localhost:1433/cacao?driver=ODBC+Driver+17+for+SQL+Server"


try:
    from sqlalchemy import create_engine

    engine = create_engine(MSSQL)
    with engine.connect() as con:
        rs = con.execute("SELECT @@VERSION")
        for row in rs:
            print("MS SQL Server disponible version:")
            print(row)
    mssql_disponible = True
except:
    print("MS SQL Server no disponible")
    mssql_disponible = False


if mssql_disponible:

    class BaseSQLServer:
        app = create_app(CONFIG)
        app.config["SQLALCHEMY_DATABASE_URI"] = MSSQL
        app.app_context().push()

    class TestSQLServer(BaseSQLServer, TestCase, Entidad, CentroCosto, Unidad, Proyecto, Moneda):
        def test_db(self):
            URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
            assert URL.startswith("mssql")

        def test_demo(self):
            demo_data()
