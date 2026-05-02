# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

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
    """Decorador para proteger el acceso a la API vía tokens."""

    @wraps(f)
    def wrapper(*args, **kwds):
        """Protege la API con un token."""
        token = None

        if "Authorization" in request.headers:
            token = request.headers["Authorization"].split(" ")[1]

        if not token:
            return {
                "message": "Authentication Token is missing!",
                "data": None,
                "error": "Unauthorized",
            }, 401

        try:
            data = decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
            assert data is not None  # nosec

            if not current_user:
                return {
                    "message": "Invalid Authentication token!",
                    "data": None,
                    "error": "Unauthorized",
                }, 401

            if not current_user.is_authenticated:
                abort(403)

        except Exception as e:
            return {
                "message": "Something went wrong",
                "data": None,
                "error": str(e),
            }, 500

        return f(*args, **kwds)

    return wrapper


@api.route("/api/test")
@token_requerido
def test_appy():
    """Vista de prueba para probar el API."""
    responde_data = {
        "Response": "Holis",
    }

    return jsonify(responde_data)
