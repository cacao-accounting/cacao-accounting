from cacao_accounting.database import database
from cacao_accounting.database.helpers import inicia_base_de_datos


def init_test_db(app):
    try:
        inicia_base_de_datos(app=app, user="cacao", passwd="cacao", with_examples=True)
    except:
        database.session.rollback()
        database.drop_all()
        inicia_base_de_datos(app=app, user="cacao", passwd="cacao", with_examples=True)
