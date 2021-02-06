import pytest
from unittest import TestCase
import pyodbc
from cacao_accounting import create_app
from cacao_accounting.database import db
from cacao_accounting.datos import base_data, demo_data
from opensource_database import CONFIG, desplegar_base_de_datos, Entidad, CentroCosto, Unidad, Proyecto, Moneda

MSSQL = "mssql+pyodbc://SA:cacao+SQLSERVER2019@localhost:1433/cacao?driver=ODBC+Driver+17+for+SQL+Server"

try:
    from sqlalchemy import create_engine

    engine = create_engine(MSSQL)
    with engine.connect() as con:
        rs = con.execute("SELECT @@VERSION")
        for row in rs:
            print(row)
    mssql_disponible = True
    print("MS SQL Server disponible")
except:
    print("MS SQL Server no disponible")
    mssql_disponible = False


if mssql_disponible:

    class BaseSQLServer:
        app = create_app(CONFIG)
        app.config["SQLALCHEMY_DATABASE_URI"] = MSSQL
        app.app_context().push()

    class TestSQLServer(BaseSQLServer, TestCase, Entidad, CentroCosto, Unidad, Proyecto, Moneda):
        def setUp(self):
            db.drop_all()
            db.create_all()
            base_data()

        def tearDown(self):
            pass

        def test_db(self):
            URL = self.app.config["SQLALCHEMY_DATABASE_URI"]
            assert URL.startswith("mssql")

        def test_demo(self):
            db.drop_all()
            db.create_all()
            base_data(carga_rapida=False)
            demo_data()
            db.drop_all()
