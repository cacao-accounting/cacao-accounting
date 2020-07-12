# Copyright 2020 William José Moreno Reyes
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Contributors:
# - William José Moreno Reyes

"""
Definicion de base de datos.
"""

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Moneda(db.Model):
    id = db.Column(db.String(5), primary_key=True, nullable=False)
    nombre = db.Column(db.String(50), nullable=False)
    plural = db.Column(db.String(50), nullable=False)
    pais = db.Column(db.String(50), nullable=False)


class TasaDeCambio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    base = db.Column(db.String(5), db.ForeignKey('moneda.id'), nullable=False)
    conversion = db.Column(
        db.String(5), db.ForeignKey('moneda.id'), nullable=False
        )
    tasa = db.Column(db.Numeric(), nullable=False)
    fecha = db.Column(db.Date(), nullable=False)


class Usuario(UserMixin, db.Model):
    """
    Una entidad con acceso al sistema.
    """
    id = db.Column(db.String(15), primary_key=True, nullable=False)
    p_nombre = db.Column(db.String(80))
    s_nombre = db.Column(db.String(80))
    p_apellido = db.Column(db.String(80))
    s_apellido = db.Column(db.String(80))
    correo_e = db.Column(db.String(150), unique=True, nullable=False)
    clave_acceso = db.Column(db.LargeBinary())
    tipo = db.Column(db.String(10))


class Entidad(db.Model):
    """
    Una entidad es una unidad de negocios de la que se lleva registros
    en el sistema.
    """
    # Información legal de la entidad
    id = db.Column(db.String(5), primary_key=True)
    razon_social = db.Column(db.String(100), unique=True, nullable=False)
    nombre_comercial = db.Column(db.String(50))
    id_fiscal = db.Column(db.String(50), unique=True, nullable=False)
    # Individual, Sociedad, Sin Fines de Lucro
    tipo_entidad = db.Column(db.String(50))
    # Información de contacto
    corre_electronico = db.Column(db.String(50))
    web = db.Column(db.String(50))
    telefono1 = db.Column(db.String(50))
    telefono1 = db.Column(db.String(50))
    fax = db.Column(db.String(50))
    pais = db.Column(db.String(50))
    departamento = db.Column(db.String(50))
    ciudad = db.Column(db.String(50))
    direccion1 = db.Column(db.String(100))
    direccion2 = db.Column(db.String(100))
    calle = db.Column(db.String(100))
    casa = db.Column(db.String(100))
