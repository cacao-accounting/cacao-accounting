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
Modulo de Contabilidad.
"""

from flask import Blueprint, render_template
from flask_login import login_required

contabilidad = Blueprint("contabilidad", __name__, template_folder="templates")


@contabilidad.route("/contabilidad")
@contabilidad.route("/conta")
@contabilidad.route("/accounts")
@login_required
def conta():
    return render_template("contabilidad.html")


@contabilidad.route("/accounts/entities")
@login_required
def entidades():
    from cacao_accounting.database import Entidad

    entidades = Entidad.query.order_by(Entidad.id).all()
    return render_template("contabilidad/entidades.html", entidades=entidades)


@contabilidad.route("/accounts/entities/<id_entidad>")
@login_required
def entidad(id_entidad):
    from cacao_accounting.database import Entidad

    registro = Entidad.query.filter_by(id=id_entidad).first()
    return render_template("contabilidad/entidad.html", registro=registro)


@contabilidad.route("/accounts/units")
@login_required
def unidades():
    from cacao_accounting.database import Unidad

    unidades = Unidad.query.order_by(Unidad.entidad).all()
    return render_template("contabilidad/unidades.html", unidades=unidades)


@contabilidad.route("/accounts/unit/<id_unidad>")
@login_required
def unidad(id_unidad):
    from cacao_accounting.database import Unidad

    registro = Unidad.query.filter_by(id=id_unidad).first()
    return render_template("contabilidad/unidad.html", registro=registro)


@contabilidad.route("/accounts/accounts")
@login_required
def cuentas():
    from cacao_accounting.database import Cuentas

    catalogo = Cuentas.query.order_by(Cuentas.codigo).all()
    return render_template("contabilidad/cuentas.html", catalogo=catalogo)


@contabilidad.route("/accounts/accounts/<id_cta>")
@login_required
def cuenta(id_cta):
    from cacao_accounting.database import Cuentas

    registro = Cuentas.query.filter_by(codigo=id_cta).first()
    return render_template("contabilidad/cuenta.html", registro=registro)


@contabilidad.route("/accounts/ccenter")
@login_required
def ccostos():
    return render_template("contabilidad/ccostos.html")


@contabilidad.route("/accounts/projects")
@login_required
def proyectos():
    return render_template("contabilidad/proyectos.html")


@contabilidad.route("/accounts/exchange")
@login_required
def tc():
    return render_template("contabilidad/tc.html")
