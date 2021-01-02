"""
Base CRUD check over database
"""

ENTIDAD1 = {
    "id": "cacao1",
    "razon_social": "Choco Sonrisas Sociedad Anonima",
    "nombre_comercial": "Choco Sonrisas",
    "id_fiscal": "J0310000000000",
    "moneda": "NIO",
    "tipo_entidad": "Sociedad",
    "correo_electronico": "info@chocoworld.com",
    "web": "chocoworld.com",
    "telefono1": "+505 8456 6543",
    "telefono2": "+505 8456 7543",
    "fax": "+505 8456 7545",
    "pais": "Nicaragua",
    "departamento": "Managua",
    "ciudad": "Managua",
    "direccion1": "Edicio x",
    "direccion2": "Oficina 23",
    "calle": 25,
    "casa": 3,
    "habilitada": True,
    "predeterminada": True,
}

ENTIDAD2 = {
    "id": "cacao2",
    "razon_social": "Choco Sonrisas 2 Sociedad Anonima",
    "nombre_comercial": "Choco Sonrisas 2",
    "id_fiscal": "J0310000000001",
    "moneda": "NIO",
    "tipo_entidad": "Sociedad",
    "correo_electronico": "info@chocoworld.com",
    "web": "chocoworld.com",
    "telefono1": "+505 8456 6543",
    "telefono2": "+505 8456 7543",
    "fax": "+505 8456 7545",
    "pais": "Nicaragua",
    "departamento": "Managua",
    "ciudad": "Managua",
    "direccion1": "Edicio x",
    "direccion2": "Oficina 23",
    "calle": 25,
    "casa": 3,
    "habilitada": True,
    "predeterminada": True,
}


ENTIDAD3 = {
    "id": "cacao2",
    "razon_social": "Choco Sonrisas 2 Sociedad Anonima",
    "nombre_comercial": "Choco Sonrisas 2",
    "id_fiscal": "J0310000000001",
    "moneda": "NIO",
    "tipo_entidad": "Sociedad",
    "correo_electronico": "info@chocoworld.com",
    "web": "chocoworld.com",
    "telefono1": "+505 8456 6543",
    "telefono2": "+505 8456 7543",
    "fax": "+505 8456 7545",
    "pais": "Nicaragua",
    "departamento": "Managua",
    "ciudad": "Managua",
    "direccion1": "Edicio x",
    "direccion2": "Oficina 23",
    "calle": 25,
    "casa": 3,
    "habilitada": True,
    "predeterminada": True,
}


class Entidad:
    from cacao_accounting.contabilidad.registros.entidad import RegistroEntidad
    from sqlalchemy.exc import IntegrityError
    from cacao_accounting.database import db, Entidad

    instancia_entidad = RegistroEntidad()

    def test_crearentidad(self):
        self.db.drop_all()
        self.db.create_all()
        self.instancia_entidad.crear(ENTIDAD1)
        self.instancia_entidad.crear(ENTIDAD2)

    def test_entidadescreadas(self):
        assert self.db.session.query(self.Entidad).count(), 2
