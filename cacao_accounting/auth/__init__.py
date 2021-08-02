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
Inición de sesión de usuarios.
"""

from os import environ
from cacao_accounting.database import Usuario
from flask import Blueprint, redirect, render_template, flash
from flask_login import LoginManager, logout_user, login_user

login = Blueprint("login", __name__, template_folder="templates")
administrador_sesion = LoginManager()


@administrador_sesion.user_loader
def cargar_sesion(identidad):
    if identidad is not None:
        return Usuario.query.get(identidad)
    return None


@administrador_sesion.unauthorized_handler
def no_autorizado():
    flash("Favor iniciar sesión para acceder al sistema.")
    return redirect("/login")


def proteger_passwd(clave):
    from bcrypt import hashpw, gensalt

    clave_encriptada = hashpw(clave.encode(), gensalt())
    return clave_encriptada


def validar_acceso(usuario, clave):
    from bcrypt import checkpw

    acceso = clave
    registro = Usuario.query.filter_by(usuario=usuario).first()
    if registro is not None:
        clave_validada = checkpw(acceso.encode(), registro.clave_acceso)
    else:
        clave_validada = False
    return clave_validada


@login.route("/")
@login.route("/home")
@login.route("/index")
@login.route("/inicio")
@login.route("/main")
def home():
    return redirect("/login")


@login.route("/login", methods=["GET", "POST"])
def inicio_sesion():
    from cacao_accounting.auth.forms import LoginForm

    form = LoginForm()
    if form.validate_on_submit():
        if validar_acceso(form.usuario.data, form.acceso.data):
            identidad = Usuario.query.filter_by(usuario=form.usuario.data).first()
            login_user(identidad)
            return redirect("/app")
        else:
            flash("Inicio de Sesion Incorrecto.")
            return redirect("/login")
    return render_template("login.html", form=form, titulo="Inicio de Sesion - Cacao Accounting")


@login.route("/exit")
@login.route("/logout")
@login.route("/salir")
def cerrar_sesion():
    logout_user()
    return redirect("/login")


if environ.get("CACAO_TEST") or environ.get("FLASK_ENV") == "development":
    from flask_login import login_required

    @login.route("/test_roles")
    @login_required
    def test_roles():
        from flask_login import current_user
        from cacao_accounting.auth.roles import obtener_roles_por_usuario
        from cacao_accounting.database import Modulos
        from cacao_accounting.auth.permisos import Permisos

        MODULOS = Modulos.query.all()

        return render_template("test_roles.html",permisos=Permisos ,roles=obtener_roles_por_usuario(current_user.usuario), modulos=MODULOS)
