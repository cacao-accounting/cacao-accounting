from cacao_accounting import create_app
from cacao_accounting.conf import configuracion

app = create_app(configuracion)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///cacaoatest.db"


def test_sqlite():
    with app.app_context():
        from cacao_accounting.database import db

        db.create_all()
        from cacao_accounting.datos import base_data, demo_data

        base_data()
        demo_data()
