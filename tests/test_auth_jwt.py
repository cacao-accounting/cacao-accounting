# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

from datetime import datetime, timedelta, timezone
import pytest
import jwt
from cacao_accounting import create_app
from cacao_accounting.database import User, database
from cacao_accounting.auth.helpers import asignar_token_para_usuario


def test_asignar_token_para_usuario():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "SECRET_KEY": "test-secret-key"})
    with app.app_context():
        # Create a mock user
        user = User()
        user.id = "user-123"
        user.token = None

        asignar_token_para_usuario(user)

        assert user.token is not None

        # Decode the token and verify the claims
        payload = jwt.decode(user.token, "test-secret-key", algorithms=["HS256"])
        assert payload["user_id"] == "user-123"
        assert "iat" in payload
        assert "nbf" in payload
        assert "exp" in payload

        # Check that 'exp' is after 'iat' by 8 hours
        iat_time = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        nbf_time = datetime.fromtimestamp(payload["nbf"], tz=timezone.utc)

        assert exp_time == iat_time + timedelta(hours=8)
        assert nbf_time == iat_time


def test_jwt_expiration_validation():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "SECRET_KEY": "test-secret-key"})
    with app.app_context():
        # Construct an expired token
        ahora = datetime.now(timezone.utc)
        expired_payload = {
            "user_id": "user-expired",
            "iat": ahora - timedelta(hours=9),
            "nbf": ahora - timedelta(hours=9),
            "exp": ahora - timedelta(hours=1),
        }
        expired_token = jwt.encode(expired_payload, "test-secret-key", algorithm="HS256")

        # PyJWT should raise ExpiredSignatureError when decoding an expired token
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(expired_token, "test-secret-key", algorithms=["HS256"])


def test_token_cache_persistence_and_invalidation():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "SECRET_KEY": "test-secret-key"})
    with app.app_context():
        database.create_all()

        user = User(
            user="tokenuser",
            name="Token User",
            password=b"secret",
        )
        database.session.add(user)
        database.session.commit()

        user_id = user.id
        assert user.token is None

        # Assign token
        asignar_token_para_usuario(user)
        token_val = user.token
        assert token_val is not None

        # Reload user from DB
        database.session.expire_all()
        reloaded_user = database.session.get(User, user_id)

        # The token should be persisted/retrieved via cache!
        assert reloaded_user.token == token_val

        # Revoke token on logout
        reloaded_user.token = None
        assert reloaded_user.token is None

        # Verify that retrieving again yields None (revoked)
        database.session.expire_all()
        reloaded_user_after_logout = database.session.get(User, user_id)
        assert reloaded_user_after_logout.token is None


def test_token_requerido_decorator():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "SECRET_KEY": "test-secret-key"})
    with app.app_context():
        database.create_all()

        user = User(
            user="tokenuser2",
            name="Token User 2",
            password=b"secret",
        )
        database.session.add(user)
        database.session.commit()

        asignar_token_para_usuario(user)
        token_val = user.token

        # Test request client
        client = app.test_client()

        # 1. Missing Authorization header
        response = client.get("/api/test")
        assert response.status_code == 401
        assert response.get_json()["message"] == "Authentication Token is missing!"

        # 2. Invalid or malformed token
        headers_bad = {"Authorization": "Bearer badtoken"}
        response = client.get("/api/test", headers=headers_bad)
        assert response.status_code == 500  # Decoding badtoken raises PyJWT exceptions which returns 500

        # 3. Valid active token
        headers_good = {"Authorization": f"Bearer {token_val}"}
        response = client.get("/api/test", headers=headers_good)
        assert response.status_code == 200
        assert response.get_json()["Response"] == "Holis"

        # 4. Revoked token (by setting User.token = None / logging out)
        user.token = None
        database.session.commit()

        response = client.get("/api/test", headers=headers_good)
        assert response.status_code == 401
        assert response.get_json()["message"] == "Invalid or expired Authentication token!"
