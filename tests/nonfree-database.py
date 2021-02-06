import pytest
from unittest import TestCase
import pyodbc
from cacao_accounting import create_app
from cacao_accounting.database import db
from cacao_accounting.datos import base_data, demo_data

MSSQL = "mssql+pyodbc://SA:cacao+SQLSERVER2019@localhost:1433/cacao?driver=ODBC+Driver+17+for+SQL+Server"

try:
    from sqlalchemy import create_engine

    engine = create_engine(MSSQL)
    with engine.connect() as con:
        rs = con.execute("SELECT @@VERSION")
        for row in rs:
            print(row)
    print("MS SQL Server disponible")
except:
    print("MS SQL Server no disponible")