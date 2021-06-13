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
