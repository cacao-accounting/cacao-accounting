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

El objetivo es que el sistema contable pueda ser desplegado sin tener que depender
de una base de datos especifica, la prioridad en soportar Postresql como base de datos
primaria para entornos multiusuarios y Sqlite como base de datos para entornos de un
solo usuario.

Mysql en su versión comunitaria es una opción secundaria, Mariadb no es un opción debido
a que por el momento no soportan el tipo de datos JSON.

Referencia:
 - https://mariadb.com/kb/en/json-data-type/

"""

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from cacao_accounting.conf import configuracion

# Postgresql trabajo por defecto con el esquema "public", lo definiminos explisitamente
# unicamente si la base de datos es "postgresl"

if "DATABASE" in configuracion and configuracion["DATABASE"] == "postgresql":
    ARGUMENTOS = {"schema": "public"}
    ESQUEMA = "public."
else:
    ARGUMENTOS = {}
    ESQUEMA = ""
db = SQLAlchemy()


class Moneda(db.Model):
    __table_args__ = (ARGUMENTOS)
    id = db.Column(db.String(5), primary_key=True, nullable=False)
    nombre = db.Column(db.String(50), nullable=False)
    plural = db.Column(db.String(50), nullable=False)
    pais = db.Column(db.String(50), nullable=False)


class TasaDeCambio(db.Model):
    __table_args__ = (ARGUMENTOS)
    id = db.Column(db.Integer, primary_key=True)
    base = db.Column(db.String(5), db.ForeignKey(ESQUEMA + "moneda.id"), nullable=False)
    conversion = db.Column(db.String(5), db.ForeignKey(ESQUEMA + "moneda.id"), nullable=False)
    tasa = db.Column(db.Numeric(), nullable=False)
    fecha = db.Column(db.Date(), nullable=False)


class Usuario(UserMixin, db.Model):
    """
    Una entidad con acceso al sistema.
    """
    __table_args__ = (ARGUMENTOS)
    # Información Básica
    id = db.Column(db.String(15), primary_key=True, nullable=False)
    p_nombre = db.Column(db.String(80))
    s_nombre = db.Column(db.String(80))
    p_apellido = db.Column(db.String(80))
    s_apellido = db.Column(db.String(80))
    correo_e = db.Column(db.String(150), unique=True, nullable=False)
    clave_acceso = db.Column(db.LargeBinary(), nullable=False)
    tipo = db.Column(db.String(15))
    activo = db.Column(db.Boolean())
    # Información Complementaria
    genero = db.Column(db.String(10))
    nacimiento = db.Column(db.Date())
    telefono = db.Column(db.String(50))
    # Roles y Permisos
    admin = db.Column(db.Boolean())
    # Si esta columna es tipo JSON, así que debemos seguir el soporte de bases de datos a este
    # tipo de datos
    # Referencia: https://docs.sqlalchemy.org/en/13/core/type_basics.html#sqlalchemy.types.JSON
    # JSON is provided as a facade for vendor-specific JSON types. Since it supports JSON SQL operations,
    # it only works on backends that have an actual JSON type, currently:
    #  - PostgreSQL
    #  - MySQL as of version 5.7 (MariaDB as of the 10.2 series does not)
    #  - SQLite as of version 3.9
    roles = db.Column(db.JSON())


class Perfiles(db.Model):
    """
    Define los roles de acceso predeterminados.
    """
    __table_args__ = (ARGUMENTOS)
    id = db.Column(db.String(15), primary_key=True, unique=True)
    nombre = db.Column(db.String(50))
    detalle = db.Column(db.String(250))
    modulo = db.Column(db.String(20), nullable=False)


class Permisos(db.Model):
    """
    Define los permisos que otorga cada rol.
    """
    __table_args__ = (ARGUMENTOS)
    id = db.Column(db.Integer(), primary_key=True)
    perfil = db.Column(db.String(50), db.ForeignKey(ESQUEMA + "perfiles.id"))
    documento = db.Column(db.String(50))
    consultar = db.Column(db.Boolean())
    crear = db.Column(db.Boolean())
    autorizar = db.Column(db.Boolean())
    cancelar = db.Column(db.Boolean())
    corregir = db.Column(db.Boolean())


class Entidad(db.Model):
    """
    Una entidad es una unidad de negocios de la que se lleva registros
    en el sistema.
    """
    __table_args__ = (ARGUMENTOS)
    # Información legal de la entidad
    id = db.Column(db.String(5), primary_key=True)
    razon_social = db.Column(db.String(100), unique=True, nullable=False)
    nombre_comercial = db.Column(db.String(50))
    id_fiscal = db.Column(db.String(50), unique=True, nullable=False)
    moneda = db.Column(db.String(5), db.ForeignKey(ESQUEMA + "moneda.id"))
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
