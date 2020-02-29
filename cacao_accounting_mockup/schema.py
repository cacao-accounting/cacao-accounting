from cacao_accounting_mockup import db


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(80), nullable=False)
    apellido = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)


class Moneda(db.Model):
    id = db.Column(db.Integer, primary_key=True)


class Pais(db.Model):
    id = db.Column(db.String(10), primary_key=True)
    moneda = db.Column()


class Entidad(db.Model):
    id = db.Column(db.Integer, primary_key=True)
