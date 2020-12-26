class BaseTest:
    from cacao_accounting import create_app
    from cacao_accounting.conf import configuracion
    from cacao_accounting.database import db

    app = create_app(configuracion)
    app.app_context().push()
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["TESTING"] = True
    app.config["DEBUG"] = True
    db.drop_all()
    db.create_all()
