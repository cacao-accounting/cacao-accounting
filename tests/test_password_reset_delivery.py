# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Un fallo de correo no deja un token de recuperación activo.

Escenario de negocio (issue #2023): la ruta generaba y confirmaba el token
antes de enviar el correo; si SMTP fallaba, el enlace previo quedaba consumido
y el nuevo activo sin que la persona lo recibiera.
"""

from __future__ import annotations

from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.auth.device_verification import generar_token_recuperacion
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, PasswordResetToken, User, database
from cacao_accounting.messaging.email import EmailError


def _crear_app():
    application = create_app(
        {
            **configuracion,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "MODO_ESCRITORIO": False,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add(Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True))
        database.session.flush()
        database.session.add_all(
            [
                Entity(
                    code="cacao",
                    name="Cacao",
                    company_name="Cacao SA",
                    tax_id="J0001",
                    currency="NIO",
                    enabled=True,
                    status="default",
                ),
                User(
                    id="usuario",
                    user="usuario",
                    name="Usuario",
                    password=b"x",
                    e_mail="usuario@example.com",
                    active=True,
                    classification="system",
                ),
            ]
        )
        database.session.commit()
    return application


def _token_previo(application) -> str:
    with application.app_context():
        token = generar_token_recuperacion("usuario")
        database.session.commit()
        return token


def _tokens(application):
    return database.session.execute(database.select(PasswordResetToken)).scalars().all()


def test_fallo_de_correo_conserva_el_token_anterior(monkeypatch):
    """No se consume el enlace previo ni se confirma el nuevo."""
    application = _crear_app()
    try:
        token_previo = _token_previo(application)

        def _falla(**_kwargs):
            raise EmailError("SMTP no disponible")

        monkeypatch.setattr("cacao_accounting.messaging.email.send_email", _falla)
        client = application.test_client()
        respuesta = client.post("/auth/forgot-password", data={"email": "usuario@example.com"})

        assert respuesta.status_code == 302
        with application.app_context():
            tokens = _tokens(application)
            assert len(tokens) == 1
            assert tokens[0].token == token_previo
            assert tokens[0].consumed is False
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()


def test_entrega_correcta_consume_el_anterior_y_activa_el_nuevo(monkeypatch):
    """El control positivo mantiene la rotación normal de tokens."""
    application = _crear_app()
    try:
        token_previo = _token_previo(application)
        enviados: list[str] = []
        monkeypatch.setattr(
            "cacao_accounting.messaging.email.send_email",
            lambda **kwargs: enviados.append(kwargs["to_email"]),
        )

        client = application.test_client()
        respuesta = client.post("/auth/forgot-password", data={"email": "usuario@example.com"})

        assert respuesta.status_code == 302
        assert enviados == ["usuario@example.com"]
        with application.app_context():
            tokens = _tokens(application)
            assert len(tokens) == 2
            anteriores = [token for token in tokens if token.token == token_previo]
            assert anteriores and anteriores[0].consumed is True
            assert any(token.consumed is False for token in tokens)
    finally:
        with application.app_context():
            database.session.remove()
            database.engine.dispose()
