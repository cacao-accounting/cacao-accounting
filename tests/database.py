from cacao_accounting.database import db
from cacao_accounting.datos import base_data


def desplegar_base_de_datos():
    db.drop_all()
    db.create_all()
    base_data(carga_rapida=True)


ENTIDAD1 = {
    "id": "cafe1",
    "razon_social": "Cafe y Mas Sociedad Anonima",
    "nombre_comercial": "Cafe y Mas",
    "id_fiscal": "J0320000000078",
    "moneda": "NIO",
    "tipo_entidad": "Sociedad",
    "correo_electronico": "info@cafeland.com",
    "web": "cafeland.com",
    "telefono1": "+505 8456 6543",
    "telefono2": "+505 8456 7543",
    "fax": "+505 8456 7545",
    "habilitada": True,
    "predeterminada": True,
}

ENTIDAD2 = {
    "id": "soda",
    "razon_social": "Soda Land Sociedad Anonima",
    "nombre_comercial": "Soda Land",
    "id_fiscal": "J0310000000778",
    "moneda": "NIO",
    "tipo_entidad": "Sociedad",
    "correo_electronico": "info@sodaland.com",
    "web": "sodaland.com",
    "telefono1": "+505 8456 6543",
    "telefono2": "+505 8456 7543",
    "fax": "+505 8456 7545",
    "habilitada": True,
    "predeterminada": False,
}


ENTIDAD3 = {
    "id": "soda",
    "razon_social": "Soda Land Sociedad Anonima",
    "nombre_comercial": "Soda Land",
    "id_fiscal": "J0310000000778",
    "moneda": "NIO",
    "tipo_entidad": "Sociedad",
    "correo_electronico": "info@sodaland.com",
    "web": "sodaland.com",
    "telefono1": "+505 8456 6543",
    "telefono2": "+505 8456 7543",
    "fax": "+505 8456 7545",
    "habilitada": True,
    "predeterminada": False,
}


class Entidad:
    def test_crear_entidad(self):
        from cacao_accounting.contabilidad.registros.entidad import RegistroEntidad
        from cacao_accounting.database import Entidad

        e = RegistroEntidad()
        e.crear_entidad(datos=ENTIDAD1)
        entidades1 = Entidad.query.count()
        assert entidades1 == 1
        e.crear_entidad(datos=ENTIDAD2)
        entidades2 = Entidad.query.count()
        assert entidades2 == 2


CENTRO_DE_COSTO1 = {
    "activa": True,
    "predeterminado": True,
    "habilitada": True,
    "entidad": "cacao",
    "id": "11.01",
    "nombre": "Centro de Costos de Prueba",
    "grupo": False,
    "padre": None,
}

CENTRO_DE_COSTO2 = {
    "activa": True,
    "predeterminado": True,
    "habilitada": True,
    "id": "11.02",
    "nombre": "Centro de Costos de Prueba 1",
    "grupo": False,
    "padre": None,
}

CENTRO_DE_COSTO3 = {
    "activa": True,
    "predeterminado": True,
    "habilitada": True,
    "entidad": "cacao",
    "id": "11.03",
    "nombre": "Centro de Costos de Prueba 2",
    "grupo": True,
    "padre": None,
}


class CentroCosto:
    def test_crear_centrocosto(self):
        from cacao_accounting.datos import demo_data
        from cacao_accounting.contabilidad.registros.ccosto import RegistroCentroCosto

        demo_data()
        c = RegistroCentroCosto()
        c.crear(datos=CENTRO_DE_COSTO1)
        c.crear(datos=CENTRO_DE_COSTO3)
        c.crear_registro(datos=CENTRO_DE_COSTO2, entidad_madre="cacao")

    def test_eliminar_centrocosto(self):
        from cacao_accounting.datos import demo_data
        from cacao_accounting.contabilidad.registros.ccosto import RegistroCentroCosto

        demo_data()
        c = RegistroCentroCosto()
        c.crear(datos=CENTRO_DE_COSTO1)
        c.eliminar(identificador="11.01")


UNIDAD1 = {
    "id": "ocotal",
    "nombre": "Sucursal Ocotal",
    "entidad": "cacao",
    "correo_electronico": "sucursal1@chocoland.com",
    "web": "chocoland.com",
    "telefono1": "+505 8667 2108",
    "telefono2": "+505 8771 0980",
    "fax": "+505 7272 8181",
}

UNIDAD2 = {
    "id": "esteli",
    "nombre": "Sucursal Esteli",
    "correo_electronico": "sucursal2@chocoland.com",
    "web": "chocoland.com",
    "telefono1": "+505 8667 2108",
    "telefono2": "+505 8771 0980",
    "fax": "+505 7272 8181",
}


class Unidad:
    def test_crear_unidad(self):
        from cacao_accounting.datos import demo_data
        from cacao_accounting.contabilidad.registros.unidad import RegistroUnidad

        demo_data()
        r = RegistroUnidad()
        r.crear(datos=UNIDAD1)
        r.crear_registro(datos=UNIDAD2, entidad_madre="cacao")


PROYECTO = {
    "activo": True,
    "habilitado": True,
    "entidad": "cacao",
    "codigo": "99.01",
    "nombre": "Proyecto de Prueba",
    "grupo": False,
    "padre": None,
    "finalizado": False,
    "presupuesto": 100000.00,
    "ejecutado": 50000,
}


class Proyecto:
    def test_crear_proyecto(self):
        from cacao_accounting.contabilidad.registros.proyecto import RegistroProyecto
        from cacao_accounting.datos import demo_data

        demo_data()
        p = RegistroProyecto()
        p.crear(datos=PROYECTO)


MONEDA = {"id": "LALA", "nombre": "Cordobas Oro", "codigo": 55889, "decimales": 2}


class Moneda:
    def test_crear_moneda(self):
        from cacao_accounting.contabilidad.registros.moneda import RegistroMoneda

        r = RegistroMoneda()
        r.crear(MONEDA)

class Varios:
    def test_obtener_ctas_base(self):
        from cacao_accounting.contabilidad import obtener_catalogo_base
        obtener_catalogo_base()
    
    def test_obtener_ctas(self):
        from cacao_accounting.contabilidad import obtener_catalogo
        obtener_catalogo()
    
    def test_obtener_entidades(self):
        from cacao_accounting.contabilidad import obtener_entidades
        obtener_entidades()
