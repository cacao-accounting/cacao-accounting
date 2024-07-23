from cacao_accounting import create_app
from cacao_accounting.config import configuracion

app = create_app(configuracion)

app.config.update(
    {
        "TESTING": True,
        "SECRET_KEY": "jgjañlsldaksjdklasjfkjj",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "WTF_CSRF_ENABLED": False,
        "DEBUG": True,
        "PRESERVE_CONTEXT_ON_EXCEPTION": True,
        "SQLALCHEMY_ECHO": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
    }
)
