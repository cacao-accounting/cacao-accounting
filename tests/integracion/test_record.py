import pytest

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from cacao_accounting.registro import Registro

RECORD_APP = Flask(__name__)

CONF = {
    "SQLALCHEMY_DATABASE_URI": "sqlite:///record.db",
    "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    "ENV": "development",
    "SECRET_KEY": "dev",
    "TESTING": True,
}

RECORD_APP.config.from_mapping(CONF)

DATABASE = SQLAlchemy(RECORD_APP)


class Maestro(DATABASE.Model):
    id = DATABASE.Column(DATABASE.Integer(), primary_key=True, nullable=False, autoincrement=True)
    name = DATABASE.Column(DATABASE.String(5), nullable=False)
    status = DATABASE.Column(DATABASE.String(20))


class Transaccion(DATABASE.Model):
    id = DATABASE.Column(DATABASE.Integer(), primary_key=True, nullable=False, autoincrement=True)
    nombre = DATABASE.Column(DATABASE.String(10), nullable=False)
    padre = DATABASE.Column(DATABASE.String(5), DATABASE.ForeignKey("maestro.name"), nullable=False)
    status = DATABASE.Column(DATABASE.String(20))


class TransaccionDetalle(DATABASE.Model):
    id = DATABASE.Column(DATABASE.Integer(), primary_key=True, nullable=False, autoincrement=True)
    nombre = DATABASE.Column(DATABASE.String(50), nullable=False)
    padre = DATABASE.Column(DATABASE.String(5), DATABASE.ForeignKey("transaccion.nombre"), nullable=False)
    status = DATABASE.Column(DATABASE.String(20))


class RegistroMaestro(Registro):
    def __init__(self) -> None:
        self.database = DATABASE
        self.tabla = Maestro


class RegistroTransaccion(Registro):
    def __init__(self) -> None:
        self.database = DATABASE
        self.tabla = Transaccion
        self.tabla_detalle = TransaccionDetalle


def test_crear_registro():
    with RECORD_APP.app_context():
        # Eliminamos las tablas por si existe de una ejecucion anterior
        DATABASE.drop_all()
        DATABASE.create_all()
        m = RegistroMaestro()
        m.crear_registro_maestro({"name": "autores", "status": "activa"})
        t = RegistroTransaccion()
        t.crear_registro_transaccion(
            transaccion={"nombre": "verne", "padre": "autores", "status": "activa"},
            transaccion_detalle=(
                {"nombre": "La Vuelta al Mundo en 180 dias.", "padre": "verne", "status": "activa"},
                {"nombre": "De la tierra a la luna.", "padre": "verne", "status": "inactiva"},
            ),
        )


@pytest.fixture
def despliega_db_pruebas():
    with RECORD_APP.app_context():
        # Eliminamos las tablas por si existe de una ejecucion anterior
        DATABASE.drop_all()
        DATABASE.create_all()
        m = RegistroMaestro()
        t = RegistroTransaccion()
        m.crear_registro_maestro({"name": "bandas", "status": "activa"})
        t.crear_registro_transaccion(
            transaccion={"nombre": "therion", "padre": "bandas", "status": "activa"},
            transaccion_detalle=(
                {"nombre": "Theli", "padre": "therion", "status": "activa"},
                {"nombre": "A'arab Zaraq - Lucid Dreaming", "padre": "therion", "status": "activa"},
                {"nombre": "Vovin", "padre": "therion", "status": "activa"},
            ),
        )
        t.crear_registro_transaccion(
            transaccion={"nombre": "mana", "padre": "bandas", "status": "activa"},
            transaccion_detalle=(
                {"nombre": "Sombrero Verde", "padre": "mana", "status": "activa"},
                {"nombre": "Mana", "padre": "mana", "status": "activa"},
                {"nombre": "Falta amor", "padre": "mana", "status": "activa"},
                {"nombre": "¿Dónde jugarán los niños?", "padre": "mana", "status": "activa"},
                {"nombre": "Cuando los ángeles lloran", "padre": "mana", "status": "activa"},
                {"nombre": "Sueños líquidos", "padre": "mana", "status": "activa"},
                {"nombre": "MTV ´Unplugged´", "padre": "mana", "status": "activa"},
                {"nombre": "Revolución de amor ", "padre": "mana", "status": "activa"},
                {"nombre": "Amar es combatir ", "padre": "mana", "status": "activa"},
            ),
        )
        m.crear_registro_maestro({"name": "actores", "status": "activa"})
        t.crear_registro_transaccion(
            transaccion=({"nombre": "Keanu Reeves", "padre": "actores", "status": "activa"}),
            transaccion_detalle=(
                {"nombre": "Matrix", "padre": "Keanu Reeves", "status": "activa"},
                {"nombre": "John Wick", "padre": "Keanu Reeves", "status": "activa"},
            ),
        )
