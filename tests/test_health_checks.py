from cacao_accounting import create_app

app = create_app(
    {
        "TESTING": True,
        "SECRET_KEY": "test_secret_key",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
    }
)


def test_health_endpoint():
    with app.test_client() as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert b"ok" in response.data


def test_ready_endpoint():
    with app.test_client() as client:
        response = client.get("/ready")
        # In this test environment, sqlite:// should be ready
        assert response.status_code == 200
        assert b"ready" in response.data
