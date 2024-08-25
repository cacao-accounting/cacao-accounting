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

"""End point para peticiones realizadas vía api."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from functools import wraps

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------
from flask import Blueprint, abort, current_app, jsonify, request
from flask_login import current_user
from jwt import decode


# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------

api = Blueprint("api", __name__, template_folder="templates")


def token_requerido(f):  # pragma: no cover
    @wraps(f)
    def wrapper(*args, **kwds):

        token = None

        if "Authorization" in request.headers:
            token = request.headers["Authorization"].split(" ")[1]

        if not token:
            return {"message": "Authentication Token is missing!", "data": None, "error": "Unauthorized"}, 401

        try:
            data = decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            assert data is not None  # nosec

            if not current_user:
                return {"message": "Invalid Authentication token!", "data": None, "error": "Unauthorized"}, 401

            if not current_user.is_authenticated:
                abort(403)

        except Exception as e:
            return {"message": "Something went wrong", "data": None, "error": str(e)}, 500

        return f(*args, **kwds)

    return wrapper


@api.route("/api/test")
@token_requerido
def test_appy():

    responde_data = {
        "Response": "Holis",
    }

    return jsonify(responde_data)
