# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

from datetime import datetime, timedelta, timezone
import pytest
import jwt
from cacao_accounting import create_app
from cacao_accounting.database import User
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
