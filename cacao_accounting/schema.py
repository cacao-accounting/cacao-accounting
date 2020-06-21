"""
Copyright 2020 William José Moreno Reyes

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Contributors:
 - William José Moreno Reyes
"""

from cacao_accounting_mockup import db


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(80), nullable=False)
    apellido = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)


class Moneda(db.Model):
    id = db.Column(db.Integer, primary_key=True)


class Pais(db.Model):
    id = db.Column(db.String(10), primary_key=True)
    moneda = db.Column()


class Entidad(db.Model):
    id = db.Column(db.Integer, primary_key=True)
