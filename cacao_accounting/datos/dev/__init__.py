# Copyright 2020 William José Moreno Reyes
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Contributors:
# - William José Moreno Reyes

# pylint: disable=too-many-lines

"""Datos de ejemplo."""

from datetime import date
from cacao_accounting.auth.roles import asigna_rol_a_usuario
from cacao_accounting.loggin import log
from cacao_accounting.transaccion import Transaccion

# pylint: disable=import-outside-toplevel, too-many-locals, too-many-statements


def _demo_usuarios():
    """Usuarios para demostracion."""
    from cacao_accounting.auth.registros import RegistroUsuario
    from cacao_accounting.auth import proteger_passwd

    USUARIO = RegistroUsuario()

    log.debug("Creando usuarios de prueba.")
    admin = Transaccion(
        registro="Usuario",
        tipo="principal",
        estatus_actual=None,
        nuevo_estatus=None,
        uuid=None,
        accion="crear",
        datos={
            "usuario": "administrador",
            "correo_e": "administrador@cacao_accounting.io",
            "clave_acceso": proteger_passwd("administrador"),
        },
        datos_detalle=None,
        relaciones=None,
        relacion_id=None,
    )
    USUARIO.ejecutar_transaccion(admin)
    asigna_rol_a_usuario("administrador", "admin")
    auditor = Transaccion(
        registro="Usuario",
        tipo="principal",
        estatus_actual=None,
        nuevo_estatus=None,
        uuid=None,
        accion="crear",
        datos={
            "usuario": "auditor",
            "correo_e": "auditor@cacao_accounting.io",
            "clave_acceso": proteger_passwd("auditor"),
        },
        datos_detalle=None,
        relaciones=None,
        relacion_id=None,
    )
    USUARIO.ejecutar_transaccion(auditor)
    asigna_rol_a_usuario("auditor", "comptroller")
    analista = Transaccion(
        registro="Usuario",
        tipo="principal",
        estatus_actual=None,
        nuevo_estatus=None,
        uuid=None,
        accion="crear",
        datos={
            "usuario": "analista",
            "correo_e": "analista@cacao_accounting.io",
            "clave_acceso": proteger_passwd("analista"),
        },
        datos_detalle=None,
        relaciones=None,
        relacion_id=None,
    )
    USUARIO.ejecutar_transaccion(analista)
    asigna_rol_a_usuario("analista", "business_analyst")
    contabilidad = Transaccion(
        registro="Usuario",
        tipo="principal",
        estatus_actual=None,
        nuevo_estatus=None,
        uuid=None,
        accion="crear",
        datos={
            "usuario": "contabilidad",
            "correo_e": "contabilidad@cacao_accounting.io",
            "clave_acceso": proteger_passwd("contabilidad"),
        },
        datos_detalle=None,
        relaciones=None,
        relacion_id=None,
    )

    USUARIO.ejecutar_transaccion(contabilidad)
    asigna_rol_a_usuario("contabilidad", "accounting_manager")
    contabilidadj = Transaccion(
        registro="Usuario",
        tipo="principal",
        estatus_actual=None,
        nuevo_estatus=None,
        uuid=None,
        accion="crear",
        datos={
            "usuario": "contabilidadj",
            "correo_e": "contabilidadj@cacao_accounting.io",
            "clave_acceso": proteger_passwd("contabilidadj"),
        },
        datos_detalle=None,
        relaciones=None,
        relacion_id=None,
    )

    USUARIO.ejecutar_transaccion(contabilidadj)
    asigna_rol_a_usuario("contabilidadj", "accounting_auxiliar")
    compras = Transaccion(
        registro="Usuario",
        tipo="principal",
        estatus_actual=None,
        nuevo_estatus=None,
        uuid=None,
        accion="crear",
        datos={"usuario": "compras", "correo_e": "compras@cacao_accounting.io", "clave_acceso": proteger_passwd("compras")},
        datos_detalle=None,
        relaciones=None,
        relacion_id=None,
    )
    USUARIO.ejecutar_transaccion(compras)
    asigna_rol_a_usuario("compras", "purchasing_manager")
    compras_junior = Transaccion(
        registro="Usuario",
        tipo="principal",
        estatus_actual=None,
        nuevo_estatus=None,
        uuid=None,
        accion="crear",
        datos={"usuario": "comprasj", "correo_e": "comprasj@cacao_accounting.io", "clave_acceso": proteger_passwd("comprasj")},
        datos_detalle=None,
        relaciones=None,
        relacion_id=None,
    )
    USUARIO.ejecutar_transaccion(compras_junior)
    asigna_rol_a_usuario("comprasj", "purchasing_auxiliar")
    ventas = Transaccion(
        registro="Usuario",
        tipo="principal",
        estatus_actual=None,
        nuevo_estatus=None,
        uuid=None,
        accion="crear",
        datos={"usuario": "ventas", "correo_e": "ventas@cacao_accounting.io", "clave_acceso": proteger_passwd("ventas")},
        datos_detalle=None,
        relaciones=None,
        relacion_id=None,
    )
    USUARIO.ejecutar_transaccion(ventas)
    asigna_rol_a_usuario("ventas", "sales_manager")
    ventasj = Transaccion(
        registro="Usuario",
        tipo="principal",
        estatus_actual=None,
        nuevo_estatus=None,
        uuid=None,
        accion="crear",
        datos={"usuario": "ventasj", "correo_e": "ventasj@cacao_accounting.io", "clave_acceso": proteger_passwd("ventasj")},
        datos_detalle=None,
        relaciones=None,
        relacion_id=None,
    )
    USUARIO.ejecutar_transaccion(ventasj)
    asigna_rol_a_usuario("ventasj", "sales_auxiliar")
    inventario = Transaccion(
        registro="Usuario",
        tipo="principal",
        estatus_actual=None,
        nuevo_estatus=None,
        uuid=None,
        accion="crear",
        datos={
            "usuario": "inventario",
            "correo_e": "inventario@cacao_accounting.io",
            "clave_acceso": proteger_passwd("inventario"),
        },
        datos_detalle=None,
        relaciones=None,
        relacion_id=None,
    )
    USUARIO.ejecutar_transaccion(inventario)
    asigna_rol_a_usuario("inventario", "inventory_manager")
    inventarioj = Transaccion(
        registro="Usuario",
        tipo="principal",
        estatus_actual=None,
        nuevo_estatus=None,
        uuid=None,
        accion="crear",
        datos={
            "usuario": "inventarioj",
            "correo_e": "inventarioj@cacao_accounting.io",
            "clave_acceso": proteger_passwd("inventarioj"),
        },
        datos_detalle=None,
        relaciones=None,
        relacion_id=None,
    )
    USUARIO.ejecutar_transaccion(inventarioj)
    asigna_rol_a_usuario("inventarioj", "inventory_auxiliar")
    tesoreria = Transaccion(
        registro="Usuario",
        tipo="principal",
        estatus_actual=None,
        nuevo_estatus=None,
        uuid=None,
        accion="crear",
        datos={
            "usuario": "tesoreria",
            "correo_e": "tesoreria@cacao_accounting.io",
            "clave_acceso": proteger_passwd("tesoreria"),
        },
        datos_detalle=None,
        relaciones=None,
        relacion_id=None,
    )
    USUARIO.ejecutar_transaccion(tesoreria)
    asigna_rol_a_usuario("tesoreria", "head_of_treasury")
    tesoreriaj = Transaccion(
        registro="Usuario",
        tipo="principal",
        estatus_actual=None,
        nuevo_estatus=None,
        uuid=None,
        accion="crear",
        datos={
            "usuario": "tesoreriaj",
            "correo_e": "tesoreriaj@cacao_accounting.io",
            "clave_acceso": proteger_passwd("tesoreriaj"),
        },
        datos_detalle=None,
        relaciones=None,
        relacion_id=None,
    )
    USUARIO.ejecutar_transaccion(tesoreriaj)
    asigna_rol_a_usuario("tesoreriaj", "auxiliar_of_treasury")
    pasante = Transaccion(
        registro="Usuario",
        tipo="principal",
        estatus_actual=None,
        nuevo_estatus=None,
        uuid=None,
        accion="crear",
        datos={
            "usuario": "pasante",
            "correo_e": "pasante@cacao_accounting.io",
            "clave_acceso": proteger_passwd("pasante"),
        },
        datos_detalle=None,
        relaciones=None,
        relacion_id=None,
    )
    USUARIO.ejecutar_transaccion(pasante)
    asigna_rol_a_usuario("pasante", "purchasing_auxiliar")
    asigna_rol_a_usuario("pasante", "accounting_auxiliar")
    asigna_rol_a_usuario("pasante", "auxiliar_of_treasury")
    asigna_rol_a_usuario("pasante", "inventory_auxiliar")
    asigna_rol_a_usuario("pasante", "sales_auxiliar")
    usuario = Transaccion(
        registro="Usuario",
        tipo="principal",
        estatus_actual=None,
        nuevo_estatus=None,
        uuid=None,
        accion="crear",
        datos={
            "usuario": "usuario",
            "correo_e": "usuario@cacao_accounting.io",
            "clave_acceso": proteger_passwd("usuario"),
        },
        datos_detalle=None,
        relaciones=None,
        relacion_id=None,
    )
    USUARIO.ejecutar_transaccion(usuario)
    asigna_rol_a_usuario("usuario", "purchasing_user")
    asigna_rol_a_usuario("usuario", "accounting_user")
    asigna_rol_a_usuario("usuario", "inventory_user")
    asigna_rol_a_usuario("usuario", "user_of_treasury")
    asigna_rol_a_usuario("usuario", "sales_user")


def _demo_entidad():
    """Entidad de demostración."""
    from cacao_accounting.contabilidad.registros.entidad import RegistroEntidad

    log.debug("Creando entidades de prueba.")
    ENTIDAD = RegistroEntidad()
    ENTIDAD1 = Transaccion(
        registro="Entidad",
        tipo="principal",
        estatus_actual=None,
        nuevo_estatus=None,
        uuid=None,
        accion="crear",
        datos={
            "entidad": "cacao",
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
            "habilitada": True,
            "predeterminada": True,
            "status": "predeterminado",
        },
        datos_detalle=None,
        relaciones=None,
        relacion_id=None,
    )
    ENTIDAD2 = Transaccion(
        registro="Entidad",
        tipo="principal",
        estatus_actual=None,
        nuevo_estatus=None,
        uuid=None,
        accion="crear",
        datos={
            "entidad": "cafe",
            "razon_social": "Mundo Cafe Sociedad Anonima",
            "nombre_comercial": "Mundo Cafe",
            "id_fiscal": "J0310000000001",
            "moneda": "USD",
            "tipo_entidad": "Sociedad",
            "correo_electronico": "info@mundocafe.com",
            "web": "mundocafe.com",
            "telefono1": "+505 8456 6542",
            "telefono2": "+505 8456 7542",
            "fax": "+505 8456 7546",
            "habilitada": True,
            "predeterminada": False,
            "status": "activo",
        },
        datos_detalle=None,
        relaciones=None,
        relacion_id=None,
    )
    ENTIDAD3 = Transaccion(
        registro="Entidad",
        tipo="principal",
        estatus_actual=None,
        nuevo_estatus=None,
        uuid=None,
        accion="crear",
        datos={
            "entidad": "dulce",
            "razon_social": "Mundo Sabor Sociedad Anonima",
            "nombre_comercial": "Dulce Sabor",
            "id_fiscal": "J0310000000002",
            "moneda": "NIO",
            "tipo_entidad": "Sociedad",
            "correo_electronico": "info@chocoworld.com",
            "web": "chocoworld.com",
            "telefono1": "+505 8456 6543",
            "telefono2": "+505 8456 7543",
            "fax": "+505 8456 7545",
            "habilitada": False,
            "predeterminada": False,
            "status": "inactivo",
        },
        datos_detalle=None,
        relaciones=None,
        relacion_id=None,
    )
    ENTIDAD.ejecutar_transaccion(ENTIDAD1)
    ENTIDAD.ejecutar_transaccion(ENTIDAD2)
    ENTIDAD.ejecutar_transaccion(ENTIDAD3)


def _demo_unidades():
    """Unidades de Negocio de Demostración."""
    from cacao_accounting.contabilidad.registros.unidad import RegistroUnidad

    log.debug("Cargando unidades de negocio de prueba.")
    UNIDAD = RegistroUnidad()

    UNIDAD.ejecutar_transaccion(
        Transaccion(
            registro="Unidad",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "nombre": "Casa Matriz",
                "entidad": "cacao",
                "unidad": "matriz",
                "status": "activo",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )

    UNIDAD.ejecutar_transaccion(
        Transaccion(
            registro="Unidad",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "nombre": "Movil",
                "entidad": "cacao",
                "unidad": "movil",
                "status": "activo",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )

    UNIDAD.ejecutar_transaccion(
        Transaccion(
            registro="Unidad",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "nombre": "Masaya",
                "entidad": "cacao",
                "unidad": "masaya",
                "status": "inactivo",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )


def _catalogo():
    from cacao_accounting.contabilidad.ctas import base, cargar_catalogos
    from cacao_accounting.contabilidad.registros.cuenta import RegistroCuentaContable

    log.debug("Cargando catalogos de cuentas.")
    cargar_catalogos(base, "cacao")
    cargar_catalogos(base, "dulce")
    cargar_catalogos(base, "cafe")
    CUENTA_CONTABLE = RegistroCuentaContable()
    CUENTA_CONTABLE.ejecutar_transaccion(
        Transaccion(
            registro="Moneda",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "activa": True,
                "habilitada": True,
                "entidad": "cacao",
                "codigo": "6",
                "nombre": "Cuenta Prueba Nivel 0",
                "grupo": True,
                "padre": None,
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )
    CUENTA_CONTABLE.ejecutar_transaccion(
        Transaccion(
            registro="Moneda",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "activa": True,
                "habilitada": True,
                "entidad": "cacao",
                "codigo": "6.1",
                "nombre": "Cuenta Prueba Nivel 1",
                "grupo": True,
                "padre": "6",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )
    CUENTA_CONTABLE.ejecutar_transaccion(
        Transaccion(
            registro="Moneda",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "activa": True,
                "habilitada": True,
                "entidad": "cacao",
                "codigo": "6.1.1",
                "nombre": "Cuenta Prueba Nivel 2",
                "grupo": True,
                "padre": "6.1",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )
    CUENTA_CONTABLE.ejecutar_transaccion(
        Transaccion(
            registro="Moneda",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "activa": True,
                "habilitada": True,
                "entidad": "cacao",
                "codigo": "6.1.1.1",
                "nombre": "Cuenta Prueba Nivel 3",
                "grupo": True,
                "padre": "6.1.1",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )
    CUENTA_CONTABLE.ejecutar_transaccion(
        Transaccion(
            registro="Moneda",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "activa": True,
                "habilitada": True,
                "entidad": "cacao",
                "codigo": "6.1.1.1.1",
                "nombre": "Cuenta Prueba Nivel 4",
                "grupo": True,
                "padre": "6.1.1.1",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )
    CUENTA_CONTABLE.ejecutar_transaccion(
        Transaccion(
            registro="Moneda",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "activa": True,
                "habilitada": True,
                "entidad": "cacao",
                "codigo": "6.1.1.1.1.1",
                "nombre": "Cuenta Prueba Nivel 5",
                "grupo": True,
                "padre": "6.1.1.1.1",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )
    CUENTA_CONTABLE.ejecutar_transaccion(
        Transaccion(
            registro="Moneda",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "activa": True,
                "habilitada": True,
                "entidad": "cacao",
                "codigo": "6.1.1.1.1.1.1",
                "nombre": "Cuenta Prueba Nivel 6",
                "grupo": True,
                "padre": "6.1.1.1.1.1",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )
    CUENTA_CONTABLE.ejecutar_transaccion(
        Transaccion(
            registro="Moneda",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "activa": True,
                "habilitada": True,
                "entidad": "cacao",
                "codigo": "6.1.1.1.1.1.1.1",
                "nombre": "Cuenta Prueba Nivel 7",
                "grupo": True,
                "padre": "6.1.1.1.1.1.1",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )
    CUENTA_CONTABLE.ejecutar_transaccion(
        Transaccion(
            registro="Moneda",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "activa": True,
                "habilitada": True,
                "entidad": "cacao",
                "codigo": "6.1.1.1.1.1.1.1.1",
                "nombre": "Cuenta Prueba Nivel 8",
                "grupo": True,
                "padre": "6.1.1.1.1.1.1.1",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )
    CUENTA_CONTABLE.ejecutar_transaccion(
        Transaccion(
            registro="Moneda",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "activa": True,
                "habilitada": True,
                "entidad": "cacao",
                "codigo": "6.1.1.1.1.1.1.1.1.1",
                "nombre": "Cuenta Prueba Nivel 9",
                "grupo": False,
                "padre": "6.1.1.1.1.1.1.1.1",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )


def _centros_de_costos():
    from cacao_accounting.contabilidad.registros.ccosto import RegistroCentroCosto

    CENTRO_DE_COSTO = RegistroCentroCosto()
    log.debug("Cargando centros de costos.")
    CENTRO_DE_COSTO.ejecutar_transaccion(
        Transaccion(
            registro="Centro de Costo",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "activa": True,
                "predeterminado": True,
                "habilitada": True,
                "entidad": "cacao",
                "grupo": False,
                "codigo": "A00000",
                "nombre": "Centro Costos Predeterminado",
                "status": "activo",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )
    CENTRO_DE_COSTO.ejecutar_transaccion(
        Transaccion(
            registro="Centro de Costo",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "activa": True,
                "predeterminado": True,
                "habilitada": True,
                "entidad": "cacao",
                "grupo": True,
                "codigo": "B00000",
                "nombre": "Centro Costos Nivel 0",
                "status": "activo",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )
    CENTRO_DE_COSTO.ejecutar_transaccion(
        Transaccion(
            registro="Centro de Costo",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "activa": True,
                "predeterminado": True,
                "habilitada": True,
                "entidad": "cacao",
                "grupo": True,
                "codigo": "B00001",
                "nombre": "Centro Costos Nivel 1",
                "status": "activo",
                "padre": "B00000",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )
    CENTRO_DE_COSTO.ejecutar_transaccion(
        Transaccion(
            registro="Centro de Costo",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "activa": True,
                "predeterminado": True,
                "habilitada": True,
                "entidad": "cacao",
                "grupo": True,
                "codigo": "B00011",
                "nombre": "Centro Costos Nivel 2",
                "status": "activo",
                "padre": "B00001",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )
    CENTRO_DE_COSTO.ejecutar_transaccion(
        Transaccion(
            registro="Centro de Costo",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "activa": True,
                "predeterminado": True,
                "habilitada": True,
                "entidad": "cacao",
                "grupo": True,
                "codigo": "B00111",
                "nombre": "Centro Costos Nivel 3",
                "status": "activo",
                "padre": "B00011",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )
    CENTRO_DE_COSTO.ejecutar_transaccion(
        Transaccion(
            registro="Centro de Costo",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "activa": True,
                "predeterminado": True,
                "habilitada": True,
                "entidad": "cacao",
                "grupo": True,
                "codigo": "B01111",
                "nombre": "Centro Costos Nivel 4",
                "status": "activo",
                "padre": "B00111",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )
    CENTRO_DE_COSTO.ejecutar_transaccion(
        Transaccion(
            registro="Centro de Costo",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "activa": True,
                "predeterminado": True,
                "habilitada": True,
                "entidad": "cacao",
                "grupo": False,
                "codigo": "B11111",
                "nombre": "Centro Costos Nivel 5",
                "status": "activo",
                "padre": "B01111",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )
    CENTRO_DE_COSTO.ejecutar_transaccion(
        Transaccion(
            registro="Centro de Costo",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "activa": True,
                "predeterminado": True,
                "habilitada": True,
                "entidad": "cafe",
                "grupo": False,
                "codigo": "A00000",
                "nombre": "Centro Costos Predeterminado",
                "status": "activa",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )
    CENTRO_DE_COSTO.ejecutar_transaccion(
        Transaccion(
            registro="Centro de Costo",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "activa": True,
                "predeterminado": True,
                "habilitada": True,
                "entidad": "dulce",
                "grupo": False,
                "codigo": "A00000",
                "nombre": "Centro Costos Predeterminado",
                "status": "activa",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )


def _proyectos():
    from cacao_accounting.contabilidad.registros.proyecto import RegistroProyecto

    PROYECTO = RegistroProyecto()
    log.debug("Creando proyectos de pruebas.")
    PROYECTO.ejecutar_transaccion(
        Transaccion(
            registro="Proyecto",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "habilitado": True,
                "entidad": "cacao",
                "codigo": "PTO001",
                "nombre": "Proyecto Prueba",
                "fechainicio": date(year=2020, month=6, day=5),
                "fechafin": date(year=2020, month=9, day=5),
                "presupuesto": 10000,
                "status": "abierto",
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )


MONEDA01 = {
    "codigo": "custom",
    "nombre": "Dolar Paralelo",
    "decimales": 4,
    "activa": True,
    "predeterminada": False,
}


def _monedas():
    from cacao_accounting.contabilidad.registros.moneda import RegistroMoneda

    MONEDA = RegistroMoneda()
    log.debug("Creando monedas de prueba.")
    MONEDA.ejecutar_transaccion(
        Transaccion(
            registro="Moneda",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "codigo": "custom",
                "nombre": "Dolar Paralelo",
                "decimales": 4,
                "activa": True,
                "predeterminada": False,
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )


def _tasas_de_cambio():
    from cacao_accounting.contabilidad.registros.tasa_cambio import RegistroTasaCambio

    TASA_CAMBIO = RegistroTasaCambio()
    log.debug("Creando tasas de cambio de pruebas.")
    TASA_CAMBIO.ejecutar_transaccion(
        Transaccion(
            registro="Tasa de Cambio",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "base": "NIO",
                "destino": "USD",
                "tasa": 34.5984,
                "fecha": date(year=2021, month=6, day=30),
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )


def master_data():
    """Carga datos maestros de desarrollo a la base de datos."""
    log.debug("Iniciando carga de master data de pruebas.")
    _demo_usuarios()
    _demo_entidad()
    _demo_unidades()
    _centros_de_costos()
    _proyectos()
    _monedas()
    _tasas_de_cambio()
    _catalogo()
    log.debug("Master data de prueba creada correctamente.")


def _periodo_contable():
    """Crea periodos contables para desarrollo."""
    from cacao_accounting.contabilidad.registros.periodo import RegistroPeriodoContable

    PERIODO = RegistroPeriodoContable()
    log.debug("Creando periodos contables de prueba.")
    PERIODO.ejecutar_transaccion(
        Transaccion(
            registro="Periodo Contable",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "entidad": "cacao",
                "nombre": "2019",
                "status": "cerrado",
                "habilitada": False,
                "inicio": date(year=2019, month=1, day=1),
                "fin": date(year=2019, month=12, day=31),
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )

    PERIODO.ejecutar_transaccion(
        Transaccion(
            registro="Periodo Contable",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "entidad": "cacao",
                "nombre": "2020",
                "status": "actual",
                "habilitada": False,
                "inicio": date(year=2020, month=1, day=1),
                "fin": date(year=2020, month=12, day=31),
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )
    PERIODO.ejecutar_transaccion(
        Transaccion(
            registro="Periodo Contable",
            tipo="principal",
            estatus_actual=None,
            nuevo_estatus=None,
            uuid=None,
            accion="crear",
            datos={
                "entidad": "cacao",
                "nombre": "2021",
                "status": "abierto",
                "habilitada": False,
                "inicio": date(year=2021, month=1, day=1),
                "fin": date(year=2021, month=12, day=31),
            },
            datos_detalle=None,
            relaciones=None,
            relacion_id=None,
        )
    )


def transacciones():
    """Crea transacciones de desarrollo en la base de datos."""
    _periodo_contable()
    log.debug("Transacciones de Pruebas Creadas correstamente.")


def dev_data():
    """Carga datos de desarrollo a la base de datos."""
    master_data()
    transacciones()
