from cacao_accounting import create_app
from cacao_accounting.config import configuracion

app = create_app(configuracion)
app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql+psycopg2://cacao:cacao@localhost:5432/cacao"


def test_postgres():
    with app.app_context():
        from cacao_accounting.database import db

        db.create_all()
        from cacao_accounting.datos import base_data, demo_data

        base_data()
        demo_data()
