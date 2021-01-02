class BaseTest:
    from cacao_accounting import create_app
    from cacao_accounting.config import configuracion
    from cacao_accounting.datos import base_data, demo_data

    app = create_app(configuracion)
    app.config["TESTING"] = True
    app.config["DEBUG"] = True
    app.app_context().push()

    def setUp(self):
        self.db.drop_all()
        self.db.create_all()
        self.base_data()

    def tearDown(self):
        pass
