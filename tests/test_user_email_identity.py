# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""User email identity is canonical across account and recovery flows."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from cacao_accounting import create_app
from cacao_accounting.auth.account_throttling import notificar_intento_fallido
from cacao_accounting.auth.device_verification import enviar_otp_por_email
from cacao_accounting.config import configuracion
from cacao_accounting.database import Currency, Entity, Modules, User, database

USER_PASSWORD = "Email-Identity-User-2026!"


def _create_app(*, enforce_internal_controls: bool = False):
    """Build a cloud app with the account and admin routes available."""
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
            "INTERNAL_CONTROLS_ENFORCE": enforce_internal_controls,
        }
    )
    with application.app_context():
        database.create_all()
        database.session.add_all(
            [
                Currency(code="NIO", name="Córdoba", decimals=2, active=True, default=True),
                Modules(module="admin", default=False, enabled=True),
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
                    id="admin",
                    user="admin",
                    name="Administrador",
                    password=b"x",
                    active=True,
                    classification="admin",
                ),
            ]
        )
        database.session.commit()
    return application


def _admin_client(application):
    """Return a client authenticated as the system administrator."""
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "admin"
        session["_fresh"] = True
    return client


def _create_user(application, *, user_id: str, username: str, email: str | None) -> None:
    """Persist a regular user for identity collision scenarios."""
    with application.app_context():
        database.session.add(
            User(
                id=user_id,
                user=username,
                e_mail=email,
                password=b"x",
                active=True,
                classification="system",
            )
        )
        database.session.commit()


def _race_email_commit(monkeypatch, email: str, target_user_id: str | None = None) -> None:
    """Commit a competing account between validation and the request's commit."""
    session = database.session
    raced = False

    def commit_with_race():
        nonlocal raced
        current_session = session()
        if raced:
            return Session.commit(current_session)
        raced = True
        candidate = None
        target = None
        if target_user_id is None:
            candidate = next(user for user in current_session.new if isinstance(user, User))
        else:
            target = current_session.get(User, target_user_id)
        current_session.rollback()
        current_session.add(
            User(
                id="racing-owner",
                user="racing-owner",
                e_mail=email.lower(),
                password=b"x",
                active=True,
                classification="system",
            )
        )
        Session.commit(current_session)
        if candidate is not None:
            current_session.add(candidate)
        else:
            assert target is not None
            target.e_mail = email
            current_session.add(target)
        return Session.commit(current_session)

    monkeypatch.setattr(session, "commit", commit_with_race)


def _race_username_commit(monkeypatch, username: str, target_user_id: str) -> None:
    """Commit a competing username between admin validation and the request commit."""
    session = database.session
    raced = False

    def commit_with_race():
        nonlocal raced
        current_session = session()
        if raced:
            return Session.commit(current_session)
        raced = True
        target = current_session.get(User, target_user_id)
        assert target is not None
        current_session.rollback()
        current_session.add(
            User(
                id="racing-owner",
                user=username,
                password=b"x",
                active=True,
                classification="system",
            )
        )
        Session.commit(current_session)
        target.user = username
        current_session.add(target)
        return Session.commit(current_session)

    monkeypatch.setattr(session, "commit", commit_with_race)


def _close_app(application) -> None:
    """Release the scoped session and in-memory database."""
    with application.app_context():
        database.session.remove()
        database.engine.dispose()


def test_alta_admin_normaliza_el_correo_guardado():
    """The admin form stores a canonical email address."""
    application = _create_app()
    try:
        response = _admin_client(application).post(
            "/settings/users/new",
            data={
                "usuario": "nuevo",
                "e_mail": "Nuevo.Usuario@Example.COM",
                "classification": "system",
                "active": "y",
                "password": USER_PASSWORD,
                "confirm_password": USER_PASSWORD,
                "crear_usuario": "Crear usuario",
            },
        )

        assert response.status_code == 302
        with application.app_context():
            created = database.session.execute(database.select(User).filter_by(user="nuevo")).scalar_one()
            assert created.e_mail == "nuevo.usuario@example.com"
    finally:
        _close_app(application)


def test_asignacion_orm_normaliza_y_rechaza_colision_de_correo():
    """Direct ORM writers share canonicalization and the database uniqueness guard."""
    application = _create_app()
    try:
        _create_user(application, user_id="existente", username="existente", email="Persona@Example.COM")
        with application.app_context():
            existing = database.session.get(User, "existente")
            assert existing is not None and existing.e_mail == "persona@example.com"

            duplicate = User(
                id="duplicado",
                user="duplicado",
                e_mail="PERSONA@EXAMPLE.COM",
                password=b"x",
                active=True,
                classification="system",
            )
            database.session.add(duplicate)
            with pytest.raises(IntegrityError):
                database.session.commit()
            database.session.rollback()
            persisted = (
                database.session.execute(database.select(User).where(User.e_mail == "persona@example.com")).scalars().all()
            )
            assert [user.id for user in persisted] == ["existente"]
    finally:
        _close_app(application)


def test_alta_admin_rechaza_correo_duplicado_con_distinta_capitalizacion():
    """A case variant cannot create a second account for the same address."""
    application = _create_app()
    try:
        _create_user(application, user_id="existente", username="existente", email="persona@example.com")
        response = _admin_client(application).post(
            "/settings/users/new",
            data={
                "usuario": "duplicado",
                "e_mail": "PERSONA@EXAMPLE.COM",
                "classification": "system",
                "active": "y",
                "password": USER_PASSWORD,
                "confirm_password": USER_PASSWORD,
                "crear_usuario": "Crear usuario",
            },
        )

        assert response.status_code == 200
        assert "El correo electrónico ya está en uso." in response.get_data(as_text=True)
        with application.app_context():
            assert database.session.execute(database.select(User).filter_by(user="duplicado")).first() is None
    finally:
        _close_app(application)


def test_alta_admin_rechaza_duplicado_unicode_legacy_en_sqlite():
    """Python canonicalization detects a non-ASCII legacy address on SQLite."""
    application = _create_app()
    try:
        with application.app_context():
            database.session.execute(
                User.__table__.insert().values(
                    id="legacy-unicode",
                    user="legacy-unicode",
                    e_mail="Älice@example.com",
                    email_identity="älice@example.com",
                    password=b"x",
                    active=True,
                    classification="system",
                )
            )
            database.session.commit()
        response = _admin_client(application).post(
            "/settings/users/new",
            data={
                "usuario": "duplicado",
                "e_mail": "älice@example.com",
                "classification": "system",
                "active": "y",
                "password": USER_PASSWORD,
                "confirm_password": USER_PASSWORD,
                "crear_usuario": "Crear usuario",
            },
        )

        assert response.status_code == 200
        assert "El correo electrónico ya está en uso." in response.get_data(as_text=True)
        with application.app_context():
            assert database.session.execute(database.select(User).filter_by(user="duplicado")).first() is None
    finally:
        _close_app(application)


def test_alta_admin_maneja_colision_concurrente_de_correo(monkeypatch):
    """A concurrent insert is reported as a duplicate instead of HTTP 500."""
    application = _create_app()
    try:
        client = _admin_client(application)
        with application.app_context():
            _race_email_commit(monkeypatch, "persona@example.com")

        response = client.post(
            "/settings/users/new",
            data={
                "usuario": "nuevo",
                "e_mail": "Persona@Example.COM",
                "classification": "system",
                "active": "y",
                "password": USER_PASSWORD,
                "confirm_password": USER_PASSWORD,
                "crear_usuario": "Crear usuario",
            },
        )

        assert response.status_code == 200
        assert "El correo electrónico ya está en uso." in response.get_data(as_text=True)
        with application.app_context():
            assert database.session.execute(database.select(User).filter_by(user="racing-owner")).first() is not None
            assert database.session.execute(database.select(User).filter_by(user="nuevo")).first() is None
    finally:
        _close_app(application)


def test_edicion_admin_normaliza_el_correo_guardado():
    """The admin edit form uses the canonical email representation."""
    application = _create_app()
    try:
        _create_user(application, user_id="editable", username="editable", email=None)
        response = _admin_client(application).post(
            "/settings/users/editable/edit",
            data={
                "usuario": "editable",
                "e_mail": "Edit.User@Example.COM",
                "classification": "system",
                "active": "y",
                "guardar_usuario": "Actualizar Usuario",
            },
        )

        assert response.status_code == 302
        with application.app_context():
            edited = database.session.get(User, "editable")
            assert edited is not None and edited.e_mail == "edit.user@example.com"
    finally:
        _close_app(application)


def test_edicion_admin_rechaza_correo_duplicado_con_distinta_capitalizacion():
    """An admin cannot assign a case variant already owned by another account."""
    application = _create_app()
    try:
        _create_user(application, user_id="existente", username="existente", email="persona@example.com")
        _create_user(application, user_id="editable", username="editable", email="editable@example.com")
        response = _admin_client(application).post(
            "/settings/users/editable/edit",
            data={
                "usuario": "editable",
                "e_mail": "PERSONA@EXAMPLE.COM",
                "classification": "system",
                "active": "y",
                "guardar_usuario": "Actualizar Usuario",
            },
        )

        assert response.status_code == 200
        assert "El correo electrónico ya está en uso." in response.get_data(as_text=True)
        with application.app_context():
            edited = database.session.get(User, "editable")
            assert edited is not None and edited.e_mail == "editable@example.com"
    finally:
        _close_app(application)


def test_edicion_admin_permite_cambiar_datos_con_correo_duplicado_inalterado():
    """Legacy duplicate email data does not block unrelated admin edits."""
    application = _create_app()
    try:
        _create_user(application, user_id="editable", username="editable", email=None)
        with application.app_context():
            database.session.execute(
                User.__table__.update()
                .where(User.id == "editable")
                .values(e_mail="PERSONA@EXAMPLE.COM", email_identity="persona@example.com")
            )
            database.session.execute(
                User.__table__.insert().values(
                    id="legacy",
                    user="legacy",
                    e_mail="persona@example.com",
                    email_identity="persona@example.com",
                    password=b"x",
                    active=True,
                    classification="system",
                )
            )
            database.session.commit()
        response = _admin_client(application).post(
            "/settings/users/editable/edit",
            data={
                "usuario": "editable",
                "name": "Nombre actualizado",
                "e_mail": "persona@example.com",
                "classification": "system",
                "active": "y",
                "guardar_usuario": "Actualizar Usuario",
            },
        )

        assert response.status_code == 302
        with application.app_context():
            edited = database.session.get(User, "editable")
            assert edited is not None
            assert edited.name == "Nombre actualizado"
            assert edited.e_mail == "PERSONA@EXAMPLE.COM"
    finally:
        _close_app(application)


def test_edicion_admin_maneja_colision_concurrente_de_correo(monkeypatch):
    """A concurrent email owner does not leave an unhandled integrity error."""
    application = _create_app()
    try:
        _create_user(application, user_id="editable", username="editable", email=None)
        client = _admin_client(application)
        with application.app_context():
            _race_email_commit(monkeypatch, "persona@example.com", target_user_id="editable")

        response = client.post(
            "/settings/users/editable/edit",
            data={
                "usuario": "editable",
                "e_mail": "Persona@Example.COM",
                "classification": "system",
                "active": "y",
                "guardar_usuario": "Actualizar Usuario",
            },
        )

        assert response.status_code == 200
        assert "El correo electrónico ya está en uso." in response.get_data(as_text=True)
        with application.app_context():
            edited = database.session.get(User, "editable")
            assert edited is not None and edited.e_mail is None
    finally:
        _close_app(application)


def test_edicion_admin_no_confunde_colision_de_usuario_con_correo_legacy(monkeypatch):
    """An unrelated username race is not mislabeled as a legacy email conflict."""
    application = _create_app()
    try:
        _create_user(application, user_id="editable", username="editable", email=None)
        with application.app_context():
            database.session.execute(
                User.__table__.update()
                .where(User.id == "editable")
                .values(e_mail="PERSONA@EXAMPLE.COM", email_identity="persona@example.com")
            )
            database.session.execute(
                User.__table__.insert().values(
                    id="legacy",
                    user="legacy",
                    e_mail="persona@example.com",
                    email_identity="persona@example.com",
                    password=b"x",
                    active=True,
                    classification="system",
                )
            )
            database.session.commit()
            _race_username_commit(monkeypatch, "nuevo-nombre", "editable")

        with pytest.raises(IntegrityError):
            _admin_client(application).post(
                "/settings/users/editable/edit",
                data={
                    "usuario": "nuevo-nombre",
                    "e_mail": "persona@example.com",
                    "classification": "system",
                    "active": "y",
                    "guardar_usuario": "Actualizar Usuario",
                },
            )

        with application.app_context():
            edited = database.session.get(User, "editable")
            assert edited is not None
            assert edited.user == "editable"
            assert edited.e_mail == "PERSONA@EXAMPLE.COM"
            assert database.session.execute(database.select(User).filter_by(user="nuevo-nombre")).scalar_one().id == (
                "racing-owner"
            )
    finally:
        _close_app(application)


def test_perfil_rechaza_correo_ajeno_con_distinta_capitalizacion():
    """The self-service profile applies the same duplicate identity rule."""
    application = _create_app()
    try:
        _create_user(application, user_id="existente", username="existente", email="persona@example.com")
        response = _admin_client(application).post(
            "/auth/profile",
            data={"guardar_perfil": "Guardar cambios", "e_mail": "PERSONA@EXAMPLE.COM"},
        )

        assert response.status_code == 200
        assert "El correo electrónico ya está en uso por otro usuario." in response.get_data(as_text=True)
        with application.app_context():
            admin = database.session.get(User, "admin")
            assert admin is not None and admin.e_mail is None
    finally:
        _close_app(application)


def test_perfil_permite_editar_datos_con_correo_duplicado_inalterado():
    """Legacy duplicate email data does not block unrelated profile changes."""
    application = _create_app()
    try:
        with application.app_context():
            database.session.execute(
                User.__table__.update()
                .where(User.id == "admin")
                .values(e_mail="PERSONA@EXAMPLE.COM", email_identity="persona@example.com")
            )
            database.session.execute(
                User.__table__.insert().values(
                    id="legacy",
                    user="legacy",
                    e_mail="persona@example.com",
                    email_identity="persona@example.com",
                    password=b"x",
                    active=True,
                    classification="system",
                )
            )
            database.session.commit()
        response = _admin_client(application).post(
            "/auth/profile",
            data={
                "guardar_perfil": "Guardar cambios",
                "name": "Nombre actualizado",
                "e_mail": "persona@example.com",
            },
        )

        assert response.status_code == 302
        with application.app_context():
            admin = database.session.get(User, "admin")
            assert admin is not None
            assert admin.name == "Nombre actualizado"
            assert admin.e_mail == "PERSONA@EXAMPLE.COM"
    finally:
        _close_app(application)


def test_perfil_normaliza_el_correo_guardado():
    """Self-service profile updates write the canonical email representation."""
    application = _create_app()
    try:
        response = _admin_client(application).post(
            "/auth/profile",
            data={"guardar_perfil": "Guardar cambios", "e_mail": "Profile.User@Example.COM"},
        )

        assert response.status_code == 302
        with application.app_context():
            admin = database.session.get(User, "admin")
            assert admin is not None and admin.e_mail == "profile.user@example.com"
    finally:
        _close_app(application)


def test_notificaciones_de_cuenta_normalizan_destinatario_legacy(monkeypatch):
    """OTP and failed-login notices use the canonical destination of legacy users."""
    application = _create_app()
    try:
        _create_user(application, user_id="padded", username="padded", email="user@example.com")
        with application.app_context():
            database.session.execute(User.__table__.update().where(User.id == "padded").values(e_mail="  User@Example.COM  "))
            database.session.commit()
            user = database.session.get(User, "padded")
            assert user is not None
            delivered_to: list[str] = []
            monkeypatch.setattr(
                "cacao_accounting.messaging.email.send_email",
                lambda **kwargs: delivered_to.append(kwargs["to_email"]),
            )

            assert enviar_otp_por_email(user, "123456")
            notificar_intento_fallido(user)

        assert delivered_to == ["user@example.com", "user@example.com"]
    finally:
        _close_app(application)


def test_perfil_maneja_colision_concurrente_de_correo(monkeypatch):
    """A concurrent email owner is reported without aborting profile update."""
    application = _create_app()
    try:
        client = _admin_client(application)
        with application.app_context():
            _race_email_commit(monkeypatch, "persona@example.com", target_user_id="admin")

        response = client.post(
            "/auth/profile",
            data={"guardar_perfil": "Guardar cambios", "e_mail": "Persona@Example.COM"},
        )

        assert response.status_code == 200
        assert "El correo electrónico ya está en uso por otro usuario." in response.get_data(as_text=True)
        with application.app_context():
            admin = database.session.get(User, "admin")
            assert admin is not None and admin.e_mail is None
    finally:
        _close_app(application)


def test_recuperacion_busca_correo_sin_distinguir_capitalizacion(monkeypatch):
    """Recovery locates and delivers to a padded, case-variant legacy address."""
    application = _create_app()
    try:
        _create_user(application, user_id="persona", username="persona", email="persona@example.com")
        with application.app_context():
            database.session.execute(
                User.__table__.update().where(User.id == "persona").values(e_mail="  Persona@Example.COM  ")
            )
            database.session.commit()
        delivered_to: list[str] = []
        monkeypatch.setattr(
            "cacao_accounting.messaging.email.send_email",
            lambda **kwargs: delivered_to.append(kwargs["to_email"]),
        )

        response = application.test_client().post("/auth/forgot-password", data={"email": "PERSONA@EXAMPLE.COM"})

        assert response.status_code == 302
        assert delivered_to == ["persona@example.com"]
    finally:
        _close_app(application)


def test_recuperacion_ambigua_no_falla_ni_envia_correo(monkeypatch):
    """Legacy case-variant duplicates produce a generic response without selecting an account."""
    application = _create_app()
    try:
        with application.app_context():
            database.session.execute(
                User.__table__.insert(),
                [
                    {
                        "id": "legacy-a",
                        "user": "legacy-a",
                        "e_mail": "persona@example.com",
                        "email_identity": "persona@example.com",
                        "password": b"x",
                        "active": True,
                        "classification": "system",
                    },
                    {
                        "id": "legacy-b",
                        "user": "legacy-b",
                        "e_mail": "PERSONA@EXAMPLE.COM",
                        "email_identity": "persona@example.com",
                        "password": b"x",
                        "active": True,
                        "classification": "system",
                    },
                ],
            )
            database.session.commit()
        delivered_to: list[str] = []
        monkeypatch.setattr(
            "cacao_accounting.messaging.email.send_email",
            lambda **kwargs: delivered_to.append(kwargs["to_email"]),
        )

        response = application.test_client().post("/auth/forgot-password", data={"email": "persona@example.com"})

        assert response.status_code == 302
        assert delivered_to == []
    finally:
        _close_app(application)


def test_recuperacion_unicode_ambigua_falla_cerrado_en_sqlite(monkeypatch):
    """SQLite Unicode lower differences cannot select one legacy account for recovery."""
    application = _create_app()
    try:
        with application.app_context():
            database.session.execute(
                User.__table__.insert(),
                [
                    {
                        "id": "legacy-unicode-a",
                        "user": "legacy-unicode-a",
                        "e_mail": "Älice@example.com",
                        "email_identity": "älice@example.com",
                        "password": b"x",
                        "active": True,
                        "classification": "system",
                    },
                    {
                        "id": "legacy-unicode-b",
                        "user": "legacy-unicode-b",
                        "e_mail": "älice@example.com",
                        "email_identity": "älice@example.com",
                        "password": b"x",
                        "active": True,
                        "classification": "system",
                    },
                ],
            )
            database.session.commit()
        delivered_to: list[str] = []
        monkeypatch.setattr(
            "cacao_accounting.messaging.email.send_email",
            lambda **kwargs: delivered_to.append(kwargs["to_email"]),
        )

        response = application.test_client().post(
            "/auth/forgot-password",
            data={"email": "älice@example.com"},
        )

        assert response.status_code == 302
        assert delivered_to == []
    finally:
        _close_app(application)
