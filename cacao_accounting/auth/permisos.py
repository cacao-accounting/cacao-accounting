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

"""Administración de permisos de usuario."""

from typing import Union
from cacao_accounting.database import RolesUsuario, Roles, RolesPermisos, Modulos
from cacao_accounting.database.helpers import obtener_id_modulo_por_nombre, obtener_id_rol_por_monbre
from cacao_accounting.loggin import log
from cacao_accounting.registro import Registro

# Solo usuarios con el rol de administrador tienen acceso al modulo administrativo
# por eso no se incluye en esta lista.
MODULOS: list = ["accounting", "cash", "purchases", "inventory", "sales"]


ACCIONES: tuple = (
    # Si un usuario no tiene acceso a un modulo al intentar acceder a este  se debe generar un error 403.
    # Este es un permiso de nivel general y no es una accion que el usuario puede realizar en el sistema.
    "acceso",
    # Esta es la lista de acciones que un usuario puede realizar sobre los registros del sistema.
    "actualizar",
    "anular",
    "autorizar",
    "bi",
    "cerrar",
    "configurar",
    "consultar",
    "corregir",
    "crear",
    "editar",
    "eliminar",
    "importar",
    "listar",
    "reportes",
    "solicitar",
    "validar",
    "validar_solicitud",
)


class RegistroPermisosRol(Registro):  # pylint: disable=R0903
    """Administracion de Permisos por rol."""

    def __init__(self):
        """Administracion de Permisos por rol."""
        self.tabla = RolesPermisos


class Permisos:  # pylint: disable=R0902
    """
    Administración de Permisos.

    Los permisos en Cacao Accounting se basan en los siguientes conceptos:

     - Usuario: Una persona con acceso al sistema identificado por su id y contraseña.

     - Rol: Los usuarios pueden tener uno o mas roles asignados, los permisos se definen a nivel de rol
      nunca a nivel de usuario.

     - Roles de Usuario: Esta tabla mapea los roles asignados a cada usuario.

     - Permisos Roles: Lista de permisos que otorga un Rol en un modulo determinado.

     - Acción: Es un acto realizado por un usuario que cambia el estado de una transacción, se han definido
     las siguientes acciones: actualizar, anular, autorizar, bi, cerrar, configurar, consultar, corregir,
     crear, editar, eliminar, importar, listar, reportes, solicitar, validar, validar_solicitud.

    Los permisos se validan por usuario y por modulo, para inicializar la clase se debe inicializar pasando
    como parametros un UUID valido de usuario y un UUID valido de modulo.

    Para cada acción se valida que el usuario posee un rol que da acceso a la apción determinada en el modulo
    especificado, si uno de los roles del usuario otorga permiso se aprueba como valido.
    """

    def __init__(self, modulo: Union[None, str] = None, usuario: Union[None, str] = None) -> None:  # pylint: disable=R0915
        """Inicia la clase permisos."""
        self.__init_valido: Union[bool, str, None] = self.valida_modulo(modulo) and usuario
        if self.__init_valido:
            self.modulo: Union[str, None] = modulo
            self.usuario: Union[str, None] = usuario
            self.administrador: Union[bool, None] = self.valida_usuario_tiene_rol_administrativo()
            self.roles: Union[list, None] = self.obtener_roles_de_usuario()
            self.permisos_usuario: Union[list, None] = self.obtiene_lista_de_permisos()
            if self.administrador:
                self.autorizado: Union[bool, None] = True
                self.actualizar: Union[bool, None] = True
                self.anular: Union[bool, None] = True
                self.autorizar: Union[bool, None] = True
                self.bi: Union[bool, None] = True
                self.cerrar: Union[bool, None] = True
                self.configurar: Union[bool, None] = True
                self.consultar: Union[bool, None] = True
                self.corregir: Union[bool, None] = True
                self.crear: Union[bool, None] = True
                self.editar: Union[bool, None] = True
                self.eliminar: Union[bool, None] = True
                self.importar: Union[bool, None] = True
                self.listar: Union[bool, None] = True
                self.reportes: Union[bool, None] = True
                self.solicitar: Union[bool, None] = True
                self.validar: Union[bool, None] = True
                self.validar_solicitud: Union[bool, None] = True
            else:
                self.autorizado = self.__usuario_autorizado()
                self.actualizar = self.__actualizar()
                self.anular = self.__anular()
                self.autorizar = self.__autorizar()
                self.bi = self.__bi()
                self.cerrar = self.__cerrar()
                self.configurar = self.__configurar()
                self.consultar = self.__consultar()
                self.corregir = self.__corregir()
                self.crear = self.__crear()
                self.editar = self.__editar()
                self.eliminar = self.__eliminar()
                self.importar = self.__importar()
                self.listar = self.__listar()
                self.reportes = self.__reportes()
                self.solicitar = self.__solicitar()
                self.validar = self.__validar()
                self.validar_solicitud = self.__validar_solicitud()
        else:
            self.modulo = None
            self.usuario = None
            self.administrador = False
            self.roles = None
            self.permisos_usuario = None
            self.autorizado = False
            self.actualizar = False
            self.anular = False
            self.autorizar = False
            self.bi = False
            self.cerrar = False
            self.configurar = False
            self.consultar = False
            self.corregir = False
            self.crear = False
            self.editar = False
            self.eliminar = False
            self.importar = False
            self.listar = False
            self.reportes = False
            self.solicitar = False
            self.validar = False
            self.validar_solicitud = False

    def valida_modulo(self, modulo: Union[str, None]) -> bool:  # pylint: disable=R0201
        """Verifica si un modulo se encuentra activo."""
        if modulo:
            LISTA_MODULOS_ACTIVOS = []
            CONSULTA = Modulos.query.filter_by(habilitado=True)
            if CONSULTA:
                for r in CONSULTA:
                    LISTA_MODULOS_ACTIVOS.append(r.id)
            return modulo in LISTA_MODULOS_ACTIVOS
        else:
            return False

    def obtener_roles_de_usuario(self) -> list:
        """Devuelve una lista con los roles del usuario."""
        ROLES_USUARIO = RolesUsuario.query.filter_by(user_id=self.usuario)
        ROLES = [ROL.role_id for ROL in ROLES_USUARIO]
        return ROLES

    def obtener_id_rol_administrador(self) -> str:  # pylint: disable=R0201
        """Devuelve el UUID asignado al rol administrador."""
        ID_ROL_ADMIN = Roles.query.filter_by(name="admin").first()
        return ID_ROL_ADMIN.id

    def valida_usuario_tiene_rol_administrativo(self) -> bool:
        """Retorno verdadero o falso según si el usuario es miembro del grupo admin."""
        CONSULTA = RolesUsuario.query.filter(
            RolesUsuario.role_id == self.obtener_id_rol_administrador(), RolesUsuario.user_id == self.usuario
        ).first()
        return CONSULTA is not None

    def obtiene_lista_de_permisos(self) -> Union[list, None]:
        """Devuelve una lista con los permisos del usuario."""
        if self.roles:
            PERMISOS = []
            for rol in self.roles:
                CONSULTA_PERMISOS = RolesPermisos.query.filter(
                    RolesPermisos.rol_id == rol, RolesPermisos.modulo_id == self.modulo
                )
                PERMISOS.append(CONSULTA_PERMISOS)
            return PERMISOS
        else:
            return None

    def __usuario_autorizado(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.acceso is True:
                        ACCESO = True
                        break
        return ACCESO

    def __actualizar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.actualizar is True:
                        ACCESO = True
                        break
        return ACCESO

    def __anular(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.anular is True:
                        ACCESO = True
                        break
        return ACCESO

    def __autorizar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.autorizar is True:
                        ACCESO = True
                        break
        return ACCESO

    def __bi(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.bi is True:
                        ACCESO = True
                        break
        return ACCESO

    def __cerrar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.cerrar is True:
                        ACCESO = True
                        break
        return ACCESO

    def __crear(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.crear is True:
                        ACCESO = True
                        break
        return ACCESO

    def __configurar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.configurar is True:
                        ACCESO = True
                        break
        return ACCESO

    def __consultar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.consultar is True:
                        ACCESO = True
                        break
        return ACCESO

    def __corregir(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.corregir is True:
                        ACCESO = True
                        break
        return ACCESO

    def __editar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.editar is True:
                        ACCESO = True
                        break
        return ACCESO

    def __eliminar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.eliminar is True:
                        ACCESO = True
                        break
        return ACCESO

    def __importar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.importar is True:
                        ACCESO = True
                        break
        return ACCESO

    def __listar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.listar is True:
                        ACCESO = True
                        break
        return ACCESO

    def __reportes(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.reportes is True:
                        ACCESO = True
                        break
        return ACCESO

    def __solicitar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.solicitar is True:
                        ACCESO = True
                        break
        return ACCESO

    def __validar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.validar is True:
                        ACCESO = True
                        break
        return ACCESO

    def __validar_solicitud(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.validar_solicitud is True:
                        ACCESO = True
                        break
        return ACCESO


# <------------------------------------------------------------------------------------------------------------------------> #
# Permisos Predeterminados


def cargar_permisos_predeterminados() -> None:  # pylint: disable=R0914
    """Carga permisos predeterminados a la base de datos."""
    from cacao_accounting.database import database

    log.debug("Inicia craga permisos predeterminados.")
    PURCHASING_MANAGER = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("purchasing_manager"),
        modulo_id=obtener_id_modulo_por_nombre("purchases"),
        acceso=True,
        actualizar=True,
        anular=True,
        autorizar=True,
        bi=True,
        cerrar=True,
        configurar=True,
        consultar=True,
        corregir=True,
        crear=True,
        editar=True,
        eliminar=False,
        importar=True,
        listar=True,
        reportes=True,
        solicitar=True,
        validar=True,
        validar_solicitud=True,
    )
    PURCHASING_AUXILIAR = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("purchasing_auxiliar"),
        modulo_id=obtener_id_modulo_por_nombre("purchases"),
        acceso=True,
        actualizar=True,
        anular=False,
        autorizar=False,
        bi=True,
        cerrar=False,
        configurar=False,
        consultar=True,
        corregir=False,
        crear=True,
        editar=True,
        eliminar=False,
        importar=False,
        listar=True,
        reportes=True,
        solicitar=True,
        validar=False,
        validar_solicitud=False,
    )
    PURCHASING_USER = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("purchasing_user"),
        modulo_id=obtener_id_modulo_por_nombre("purchases"),
        acceso=True,
        actualizar=False,
        anular=False,
        autorizar=False,
        bi=False,
        cerrar=False,
        configurar=False,
        consultar=True,
        corregir=False,
        crear=False,
        editar=False,
        eliminar=False,
        importar=False,
        listar=True,
        reportes=False,
        solicitar=True,
        validar=False,
        validar_solicitud=False,
    )
    ACCOUNTING_MANAGER = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("accounting_manager"),
        modulo_id=obtener_id_modulo_por_nombre("accounting"),
        acceso=True,
        actualizar=True,
        anular=True,
        autorizar=True,
        bi=True,
        cerrar=True,
        configurar=True,
        consultar=True,
        corregir=True,
        crear=True,
        editar=True,
        eliminar=False,
        importar=True,
        listar=True,
        reportes=True,
        solicitar=True,
        validar=True,
        validar_solicitud=True,
    )
    ACCOUNTING_AUXILIAR = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("accounting_auxiliar"),
        modulo_id=obtener_id_modulo_por_nombre("accounting"),
        acceso=True,
        actualizar=True,
        anular=False,
        autorizar=False,
        bi=True,
        cerrar=False,
        configurar=False,
        consultar=True,
        corregir=False,
        crear=True,
        editar=True,
        eliminar=False,
        importar=False,
        listar=True,
        reportes=True,
        solicitar=True,
        validar=False,
        validar_solicitud=False,
    )
    ACCOUNTING_USER = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("accounting_user"),
        modulo_id=obtener_id_modulo_por_nombre("accounting"),
        acceso=True,
        actualizar=False,
        anular=False,
        autorizar=False,
        bi=False,
        cerrar=False,
        configurar=False,
        consultar=True,
        corregir=False,
        crear=False,
        editar=False,
        eliminar=False,
        importar=False,
        listar=True,
        reportes=False,
        solicitar=True,
        validar=False,
        validar_solicitud=False,
    )
    INVENTORY_MANAGER = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("inventory_manager"),
        modulo_id=obtener_id_modulo_por_nombre("inventory"),
        acceso=True,
        actualizar=True,
        anular=True,
        autorizar=True,
        bi=True,
        cerrar=True,
        configurar=True,
        consultar=True,
        corregir=True,
        crear=True,
        editar=True,
        eliminar=False,
        importar=True,
        listar=True,
        reportes=True,
        solicitar=True,
        validar=True,
        validar_solicitud=True,
    )
    INVENTORY_AUXILIAR = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("inventory_auxiliar"),
        modulo_id=obtener_id_modulo_por_nombre("inventory"),
        acceso=True,
        actualizar=True,
        anular=False,
        autorizar=False,
        bi=True,
        cerrar=False,
        configurar=False,
        consultar=True,
        corregir=False,
        crear=True,
        editar=True,
        eliminar=False,
        importar=False,
        listar=True,
        reportes=True,
        solicitar=True,
        validar=False,
        validar_solicitud=False,
    )
    INVENTORY_USER = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("inventory_user"),
        modulo_id=obtener_id_modulo_por_nombre("inventory"),
        acceso=True,
        actualizar=False,
        anular=False,
        autorizar=False,
        bi=False,
        cerrar=False,
        configurar=False,
        consultar=True,
        corregir=False,
        crear=False,
        editar=False,
        eliminar=False,
        importar=False,
        listar=True,
        reportes=False,
        solicitar=True,
        validar=False,
        validar_solicitud=False,
    )
    HEAD_OF_TREASURY = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("head_of_treasury"),
        modulo_id=obtener_id_modulo_por_nombre("cash"),
        acceso=True,
        actualizar=True,
        anular=True,
        autorizar=True,
        bi=True,
        cerrar=True,
        configurar=True,
        consultar=True,
        corregir=True,
        crear=True,
        editar=True,
        eliminar=False,
        importar=True,
        listar=True,
        reportes=True,
        solicitar=True,
        validar=True,
        validar_solicitud=True,
    )
    JUNIOR_OF_TREASURY = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("auxiliar_of_treasury"),
        modulo_id=obtener_id_modulo_por_nombre("cash"),
        acceso=True,
        actualizar=True,
        anular=False,
        autorizar=False,
        bi=True,
        cerrar=False,
        configurar=False,
        consultar=True,
        corregir=False,
        crear=True,
        editar=True,
        eliminar=False,
        importar=False,
        listar=True,
        reportes=True,
        solicitar=True,
        validar=False,
        validar_solicitud=False,
    )
    USER_OF_TREASURY = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("user_of_treasury"),
        modulo_id=obtener_id_modulo_por_nombre("cash"),
        acceso=True,
        actualizar=False,
        anular=False,
        autorizar=False,
        bi=False,
        cerrar=False,
        configurar=False,
        consultar=True,
        corregir=False,
        crear=False,
        editar=False,
        eliminar=False,
        importar=False,
        listar=True,
        reportes=False,
        solicitar=True,
        validar=False,
        validar_solicitud=False,
    )
    SALES_MANAGER = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("sales_manager"),
        modulo_id=obtener_id_modulo_por_nombre("sales"),
        acceso=True,
        actualizar=True,
        anular=True,
        autorizar=True,
        bi=True,
        cerrar=True,
        configurar=True,
        consultar=True,
        corregir=True,
        crear=True,
        editar=True,
        eliminar=False,
        importar=True,
        listar=True,
        reportes=True,
        solicitar=True,
        validar=True,
        validar_solicitud=True,
    )
    SALES_AUXILIAR = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("sales_auxiliar"),
        modulo_id=obtener_id_modulo_por_nombre("sales"),
        acceso=True,
        actualizar=True,
        anular=False,
        autorizar=False,
        bi=True,
        cerrar=False,
        configurar=False,
        consultar=True,
        corregir=False,
        crear=True,
        editar=True,
        eliminar=False,
        importar=False,
        listar=True,
        reportes=True,
        solicitar=True,
        validar=False,
        validar_solicitud=False,
    )
    SALES_USER = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("sales_user"),
        modulo_id=obtener_id_modulo_por_nombre("sales"),
        acceso=True,
        actualizar=False,
        anular=False,
        autorizar=False,
        bi=False,
        cerrar=False,
        configurar=False,
        consultar=True,
        corregir=False,
        crear=False,
        editar=False,
        eliminar=False,
        importar=False,
        listar=True,
        reportes=False,
        solicitar=True,
        validar=False,
        validar_solicitud=False,
    )
    CONTROLLER = []
    for MODULO in MODULOS:
        CONTROLLER.append(
            RolesPermisos(
                rol_id=obtener_id_rol_por_monbre("comptroller"),
                modulo_id=obtener_id_modulo_por_nombre(MODULO),
                acceso=True,
                actualizar=False,
                anular=False,
                autorizar=False,
                bi=False,
                cerrar=False,
                configurar=False,
                consultar=True,
                corregir=False,
                crear=False,
                editar=False,
                eliminar=False,
                importar=False,
                listar=True,
                reportes=True,
                solicitar=False,
                validar=False,
                validar_solicitud=False,
            )
        )
    BI = []
    for MODULO in MODULOS:
        BI.append(
            RolesPermisos(
                rol_id=obtener_id_rol_por_monbre("business_analyst"),
                modulo_id=obtener_id_modulo_por_nombre(MODULO),
                acceso=True,
                actualizar=False,
                anular=False,
                autorizar=False,
                bi=True,
                cerrar=False,
                configurar=False,
                consultar=True,
                corregir=False,
                crear=False,
                editar=False,
                eliminar=False,
                importar=False,
                listar=True,
                reportes=True,
                solicitar=False,
                validar=False,
                validar_solicitud=False,
            )
        )

    PERMISOS_PREDETERMINADOS = [
        PURCHASING_MANAGER,
        PURCHASING_AUXILIAR,
        PURCHASING_USER,
        ACCOUNTING_MANAGER,
        ACCOUNTING_AUXILIAR,
        ACCOUNTING_USER,
        INVENTORY_MANAGER,
        INVENTORY_AUXILIAR,
        INVENTORY_USER,
        HEAD_OF_TREASURY,
        JUNIOR_OF_TREASURY,
        USER_OF_TREASURY,
        SALES_MANAGER,
        SALES_AUXILIAR,
        SALES_USER,
        CONTROLLER,
        BI,
    ]
    for permisos in PERMISOS_PREDETERMINADOS:
        # pylint: disable=E1101
        if isinstance(permisos, list):
            for MODULO in permisos:
                database.session.add(MODULO)
                database.session.commit()
        else:
            database.session.add(permisos)
            database.session.commit()
