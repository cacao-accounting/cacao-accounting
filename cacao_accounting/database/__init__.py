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

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    p_nombre = db.Column(db.String(80))
    s_nombre = db.Column(db.String(80))
    p_apellido = db.Column(db.String(80))
    s_apellido = db.Column(db.String(80))
    correo_e = db.Column(db.String(150), unique=True, nullable=False)
    acceso = db.Column(db.Binary())


class Pais(db.Model):
    id = db.Column(db.String(5), primary_key=True)
    moneda = db.Column(db.String(5), db.ForeignKey('moneda.id'))



class Idioma(db.Model):
    id = db.Column(db.String(5), primary_key=True)
    nombre = db.Column(db.String(50), primary_key=True)


class Moneda(db.Model):
    id = db.Column(db.String(5), primary_key=True)
    singular = db.Column(db.String(50))
    plural = db.Column(db.String(50))
    simbolo = db.Column(db.String(5))


class TasaDeCambio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    moneda_base = db.Column(db.String(5), db.ForeignKey('moneda.id'))
    moneda_destino = db.Column(db.String(5), db.ForeignKey('moneda.id'))
    fecha = db.Column(db.Date())
    tasa = db.Column(db.Float())


class Entidad(db.Model):
    id = db.Column(db.String(5), primary_key=True)
    razon_social = db.Column(db.String(100), unique=True, nullable=False)
    nombre_comercial = db.Column(db.String(50))
    nit = db.Column(db.String(50), unique=True, nullable=False)
    corre_electronico = db.Column(db.String(50))
    nombre_comercial = db.Column(db.String(50))
    moneda = db.Column(db.String(5), db.ForeignKey('moneda.id'))
    pais = db.Column(db.String(5), db.ForeignKey('pais.id'))
