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

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, BooleanField, SelectField
from wtforms.validators import DataRequired
from cacao_accounting.database import Entidad, Moneda


def lista_monedas():
    """
    Devuelve la lista de monedas disponibles en la base de datos.
    """
    monedas = []
    consulta = Moneda.query.all()
    for i in consulta:
        moneda = (i.id, i.nombre)
        monedas.append(moneda)
    return monedas


# <------------------------------------------------------------------------------------------------------------------------> #
# Entidades


class FormularioEntidad(FlaskForm):
    """
    Formulario base para la administración de entidades.

    Este formulario este vinculada la la tabla Entidad en la base de datos y debe contener
    un mapeo de la mayoria de sus campos.
    """

    id = StringField(validators=[DataRequired()])
    razon_social = StringField(validators=[DataRequired()])
    nombre_comercial = StringField(validators=[])
    id_fiscal = StringField(validators=[DataRequired()])
    moneda = SelectField("Tipo de Entidad", choices=lista_monedas())
    tipo_entidad = SelectField("Tipo de Entidad", choices=Entidad.tipo_entidad_lista)
    correo_electronico = StringField(validators=[])
    web = StringField(validators=[])
    telefono1 = StringField(validators=[])
    telefono2 = StringField(validators=[])
    fax = StringField(validators=[])
    pais = StringField(validators=[])
    departamento = StringField(validators=[])
    ciudad = StringField(validators=[])
    direccion1 = StringField(validators=[])
    direccion2 = StringField(validators=[])
    calle = StringField(validators=[])
    casa = StringField(validators=[])
    avenida = StringField(validators=[])
    habilitada = BooleanField()
    predeterminada = BooleanField()
    enviar = (SubmitField(),)
