# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""#1965: un hash de contraseña ilegible no rompe el login.

La credencial almacenada inválida se trata como intento fallido controlado, sin
HTTP 500 ni sesión autenticada.
"""

from __future__ import annotations

from uuid import uuid4

from cacao_accounting.database import User, database


def _usuario_con_hash_invalido() -> str:
    """Crea un usuario activo cuya contraseña no es un hash Argon2 válido."""
    suffix = uuid4().hex[:6]
    usuario = f"hash-{suffix}"
    with database.session.no_autoflush:
        database.session.add(
            User(
                user=usuario,
                name="Hash Inválido",
                password=b"bad",
                classification="user",
                active=True,
                company="cacao",
            )
        )
        database.session.commit()
    return usuario


def test_login_con_hash_invalido_rechaza_sin_500(app, client):
    """El intento falla de forma controlada y no autentica la sesión."""
    usuario = _usuario_con_hash_invalido()

    response = client.post("/login", data={"usuario": usuario, "acceso": "CualquierClave1"})

    assert response.status_code < 500
    protegido = client.get("/app")
    assert protegido.status_code == 302
    assert "/login" in protegido.headers["Location"]


def test_login_con_hash_invalido_conserva_la_fila_de_usuario(app, client):
    """El rechazo no elimina ni reescribe el usuario con evidencia ilegible."""
    usuario = _usuario_con_hash_invalido()

    client.post("/login", data={"usuario": usuario, "acceso": "CualquierClave1"})

    with app.app_context():
        registro = database.session.execute(database.select(User).filter_by(user=usuario)).scalar_one()
        assert registro.password == b"bad"
        assert registro.active is True
