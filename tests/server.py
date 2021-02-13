def servidor_prueba():
    from cacao_accounting import create_app
    from cacao_accounting.config import SQLITE
    from cacao_accounting.database import db
    from cacao_accounting.datos import base_data, demo_data
    from waitress import serve

    test_app = create_app(
        {
            "WTF_CSRF_ENABLED": False,
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": SQLITE,
            "SECRET_KEY": "jgjañlsldaksjdklasjfkjj",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        }
    )
    with test_app.app_context():
        db.drop_all()
        db.create_all()
        base_data(carga_rapida=True)
        demo_data()
        serve(test_app, port=7563)


if __name__ == "__main__":
    servidor_prueba()
