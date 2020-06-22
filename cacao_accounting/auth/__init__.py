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

from flask import (
    current_app, Blueprint, redirect, render_template
    )

login = Blueprint("login", __name__, template_folder="templates")

@login.route("/")
def home():
    return redirect("/login")


@login.route("/login")
def inicio():
    return render_template("login.html")
