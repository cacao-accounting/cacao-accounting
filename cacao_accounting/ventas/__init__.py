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
Modulo de Ventas.
"""

from flask import Blueprint, redirect, render_template
from flask_login import login_required
from cacao_accounting.modulos import validar_modulo_activo

ventas = Blueprint("ventas", __name__, template_folder="templates")


@ventas.route("/ventas")
@ventas.route("/sales")
@login_required
def ventas_():
    if validar_modulo_activo("sales"):
        return render_template("ventas.html")
    else:
        redirect("/app")
