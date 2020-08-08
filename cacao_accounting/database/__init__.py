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

db = SQLAlchemy()


class Moneda(db.Model):
    """
    Una moneda para los registros de la entidad.
    """

<<<<<<< HEAD
    __table_args__ = ARGUMENTOS
=======
>>>>>>> d68b2682e2238139cf47ff78d2c1e52c5efca086
    id = db.Column(db.String(5), primary_key=True, nullable=False)
    nombre = db.Column(db.String(50), nullable=False)
    plural = db.Column(db.String(50), nullable=False)
    pais = db.Column(db.String(50), nullable=False)


class TasaDeCambio(db.Model):
    """
    Tasa de conversión entre dos monedas distintas.
    """

    id = db.Column(db.Integer, primary_key=True)
    base = db.Column(db.String(5), db.ForeignKey("moneda.id"), nullable=False)
    conversion = db.Column(db.String(5), db.ForeignKey("moneda.id"), nullable=False)
    tasa = db.Column(db.Numeric(), nullable=False)
    fecha = db.Column(db.Date(), nullable=False)


class Usuario(UserMixin, db.Model):
    """
    Una entidad con acceso al sistema.
    """

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

    id = db.Column(db.String(15), primary_key=True, unique=True)
    nombre = db.Column(db.String(50))
    detalle = db.Column(db.String(250))
    modulo = db.Column(db.String(20), nullable=False)


class Permisos(db.Model):
    """
    Define los permisos que otorga cada rol.
    """

    id = db.Column(db.Integer(), primary_key=True)
    perfil = db.Column(db.String(50), db.ForeignKey("perfiles.id"))
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

    # Información legal de la entidad
    id = db.Column(db.String(5), primary_key=True, unique=True, index=True)
    razon_social = db.Column(db.String(100), unique=True, nullable=False)
    nombre_comercial = db.Column(db.String(50))
    id_fiscal = db.Column(db.String(50), unique=True, nullable=False)
    moneda = db.Column(db.String(5), db.ForeignKey("moneda.id"))
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


class Unidad(db.Model):
    """
    Llamese sucursal, oficina o un aréa operativa una entidad puede tener muchas unidades de negocios.
    """

<<<<<<< HEAD
    __table_args__ = ARGUMENTOS
    # Información legal de la entidad
    id = db.Column(db.Integer(), primary_key=True, unique=True, index=True, autoincrement=True)
    nombre = db.Column(db.String(50), nullable=False)
    entidad = db.Column(db.String(5), db.ForeignKey(ESQUEMA + "entidad.id"))
=======
    # Información legal de la entidad
    id = db.Column(db.Integer(), primary_key=True, unique=True, index=True, autoincrement=True)
    nombre = db.Column(db.String(50), nullable=False)
    entidad = db.Column(db.String(5), db.ForeignKey("entidad.id"))
>>>>>>> d68b2682e2238139cf47ff78d2c1e52c5efca086
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


# Bases de la contabilidad
class CuentaContable(db.Model):
    """
    La base de contabilidad es el catalogo de cuentas.
    """

<<<<<<< HEAD
    __table_args__ = ARGUMENTOS
=======
    __table_args__ = (db.UniqueConstraint("id", "codigo", name="cta_unica"),)
>>>>>>> d68b2682e2238139cf47ff78d2c1e52c5efca086
    id = db.Column(db.Integer(), unique=True, primary_key=True, index=True, autoincrement=True)
    activa = db.Column(db.Boolean(), index=True)
    # Una cuenta puede estar activa pero deshabilitada temporalmente.
    habilitada = db.Column(db.Boolean(), index=True)
    # Todas las cuentas deben estan vinculadas a una compañia
<<<<<<< HEAD
    entidad = db.Column(db.String(5), db.ForeignKey(ESQUEMA + "entidad.id"))
    # Suficiente para un código de cuenta muy extenso y en la practica poco practico:
    # 11.01.001.001.001.001.00001.0001.0001.00001.000001
    codigo = db.Column(db.String(50))
    nombre = db.Column(db.String(100))
    # Cuenta agrupador o cuenta que recibe movimientos
    grupo = db.Column(db.Boolean())
    padre = db.Column(db.String(50), db.ForeignKey(ESQUEMA + "cuenta_contable.codigo"))
    moneda = db.Column(db.String(5), db.ForeignKey(ESQUEMA + "moneda.id"), nullable=False)
=======
    entidad = db.Column(db.String(5), db.ForeignKey("entidad.id"))
    # Suficiente para un código de cuenta muy extenso y en la practica poco practico:
    # 11.01.001.001.001.001.00001.0001.0001.00001.000001
    codigo = db.Column(db.String(50), unique=True)
    nombre = db.Column(db.String(100))
    # Cuenta agrupador o cuenta que recibe movimientos
    grupo = db.Column(db.Boolean())
    padre = db.Column(db.String(50), db.ForeignKey("cuenta_contable.codigo"))
    moneda = db.Column(db.String(5), db.ForeignKey("moneda.id"), nullable=False)
>>>>>>> d68b2682e2238139cf47ff78d2c1e52c5efca086
    # Activo, Pasivo, Patrimonio, Ingresos, Gastos
    rubro = db.Column(db.String(15), index=True)
    # Efectivo, Cta. Bancaria, Inventario, Por Cobrar, Por Pagar
    # las cuentas de tipo especial no deberan ser afectadas directamente en registros manuales
    # unicamente desde sus respectivo modulos
    tipo = db.Column(db.String(15))
<<<<<<< HEAD
    db.UniqueConstraint("codigo")
=======
>>>>>>> d68b2682e2238139cf47ff78d2c1e52c5efca086


class CentroCosto(db.Model):
    """
    La mejor forma de llegar los registros de una entidad es por Centros de Costos (CC).
    """

<<<<<<< HEAD
    __table_args__ = ARGUMENTOS
=======
    __table_args__ = (db.UniqueConstraint("id", "nombre", name="cc_unico"),)
>>>>>>> d68b2682e2238139cf47ff78d2c1e52c5efca086
    id = db.Column(db.Integer(), unique=True, primary_key=True, index=True, autoincrement=True)
    activa = db.Column(db.Boolean(), index=True)
    predeterminado = db.Column(db.Boolean())
    # Un CC puede estar activo pero deshabilitado temporalmente.
    habilitada = db.Column(db.Boolean(), index=True)
    # Todos los CC deben estan vinculados a una compañia
<<<<<<< HEAD
    entidad = db.Column(db.String(5), db.ForeignKey(ESQUEMA + "entidad.id"))
=======
    entidad = db.Column(db.String(5), db.ForeignKey("entidad.id"))
>>>>>>> d68b2682e2238139cf47ff78d2c1e52c5efca086
    # Suficiente para un código de cuenta muy extenso y en la practica poco practico:
    # 11.01.001.001.001.001.00001.0001.0001.00001.000001
    codigo = db.Column(db.String(50), unique=True, index=True)
    nombre = db.Column(db.String(100), unique=True)
    # Cuenta agrupador o cuenta que recibe movimientos
    grupo = db.Column(db.Boolean())
<<<<<<< HEAD
    padre = db.Column(db.String(100), db.ForeignKey(ESQUEMA + "centro_costo.nombre"))
=======
    padre = db.Column(db.String(100), db.ForeignKey("centro_costo.nombre"))
>>>>>>> d68b2682e2238139cf47ff78d2c1e52c5efca086
    db.UniqueConstraint("nombre")


class Proyecto(db.Model):
    """
    Similar a un Centro de Costo pero con una vida mas efimera y normalmente con un presupuesto
    definido ademas de fechas de inicio y fin.
    """

<<<<<<< HEAD
    __table_args__ = ARGUMENTOS
=======
    __table_args__ = (db.UniqueConstraint("id", "nombre", name="proyecto_unico"),)
>>>>>>> d68b2682e2238139cf47ff78d2c1e52c5efca086
    id = db.Column(db.Integer(), unique=True, primary_key=True, index=True, autoincrement=True)
    activa = db.Column(db.Boolean(), index=True)
    # Un CC puede estar activo pero deshabilitado temporalmente.
    habilitada = db.Column(db.Boolean(), index=True)
    # Todos los CC deben estan vinculados a una compañia
<<<<<<< HEAD
    entidad = db.Column(db.String(5), db.ForeignKey(ESQUEMA + "entidad.id"))
=======
    entidad = db.Column(db.String(5), db.ForeignKey("entidad.id"))
>>>>>>> d68b2682e2238139cf47ff78d2c1e52c5efca086
    # Suficiente para un código de cuenta muy extenso y en la practica poco practico:
    # 11.01.001.001.001.001.00001.0001.0001.00001.000001
    codigo = db.Column(db.String(50), unique=True, index=True)
    nombre = db.Column(db.String(100), unique=True)
    # Cuenta agrupador o cuenta que recibe movimientos
    grupo = db.Column(db.Boolean())
<<<<<<< HEAD
    padre = db.Column(db.String(100), db.ForeignKey(ESQUEMA + "centro_costo.nombre"))
    db.UniqueConstraint("nombre")
=======
    padre = db.Column(db.String(100), db.ForeignKey("centro_costo.nombre"))
>>>>>>> d68b2682e2238139cf47ff78d2c1e52c5efca086
    inicio = db.Column(db.Date())
    fin = db.Column(db.Date())
    finalizado = db.Column(db.Boolean())
    fecha_fin = db.Column(db.Date())
    presupuesto = db.Column(db.Float())
    ejecutado = db.Column(db.Float())


class PeriodoContable(db.Model):
    """
    Todas las transaciones deben estar vinculadas a un periodo contable.
    """

    id = db.Column(db.Integer(), unique=True, primary_key=True, index=True, autoincrement=True)
    nombre = db.Column(db.String(50))
    habilitada = db.Column(db.Boolean(), index=True)
    inicio = db.Column(db.Date())
    fin = db.Column(db.Date())
