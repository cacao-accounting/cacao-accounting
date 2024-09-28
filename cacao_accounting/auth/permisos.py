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

"""Administración de permisos de usuario."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------
from typing import Union

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from cacao_accounting.database import Modules, Roles, RolesAccess, RolesUser
from cacao_accounting.database.helpers import (
    obtener_id_modulo_por_nombre,
    obtener_id_rol_por_monbre,
)
from cacao_accounting.logs import log

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------


# Solo usuarios con el rol de administrador tienen acceso al modulo administrativo
# por eso no se incluye en esta lista.
MODULOS: list = ["accounting", "cash", "purchases", "inventory", "sales"]


class RegistroPermisosRol:
    """Administracion de Permisos por rol."""


class Permisos:
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

    def __init__(self, modulo: Union[None, str] = None, usuario: Union[None, str] = None) -> None:
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
                self.reportes: Union[bool, None] = True
                self.solicitar: Union[bool, None] = True
                self.validar: Union[bool, None] = True
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
                self.reportes = self.__reportes()
                self.solicitar = self.__solicitar()
                self.validar = self.__validar()
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
            self.reportes = False
            self.solicitar = False
            self.validar = False

    def valida_modulo(self, modulo: Union[str, None]) -> bool:
        """Verifica si un modulo se encuentra activo."""
        if modulo:
            LISTA_MODULOS_ACTIVOS = []
            CONSULTA = Modules.query.filter_by(enabled=True)
            if CONSULTA:
                for r in CONSULTA:
                    LISTA_MODULOS_ACTIVOS.append(r.id)
                return modulo in LISTA_MODULOS_ACTIVOS
            else:
                return False
        else:
            return False

    def obtener_roles_de_usuario(self) -> list:
        """Devuelve una lista con los roles del usuario."""
        ROLES_USUARIO = RolesUser.query.filter_by(user_id=self.usuario)
        ROLES = [ROL.role_id for ROL in ROLES_USUARIO]
        return ROLES

    def obtener_id_rol_administrador(self) -> str:
        """Devuelve el UUID asignado al rol administrador."""
        ID_ROL_ADMIN = Roles.query.filter_by(name="admin").first()
        return ID_ROL_ADMIN.id

    def valida_usuario_tiene_rol_administrativo(self) -> bool:
        """Retorno verdadero o falso según si el usuario es miembro del grupo admin."""
        CONSULTA = RolesUser.query.filter(
            RolesUser.role_id == self.obtener_id_rol_administrador(),
            RolesUser.user_id == self.usuario,
        ).first()
        return CONSULTA is not None

    def obtiene_lista_de_permisos(self) -> Union[list, None]:
        """Devuelve una lista con los permisos del usuario."""
        if self.roles:
            PERMISOS = []
            for rol in self.roles:
                CONSULTA_PERMISOS = RolesAccess.query.filter(RolesAccess.rol_id == rol, RolesAccess.module_id == self.modulo)
                PERMISOS.append(CONSULTA_PERMISOS)
            return PERMISOS
        else:
            return None

    def __usuario_autorizado(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.access is True:
                        ACCESO = True
                        break
        return ACCESO

    def __actualizar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.update is True:
                        ACCESO = True
                        break
        return ACCESO

    def __anular(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.set_null is True:
                        ACCESO = True
                        break
        return ACCESO

    def __autorizar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.approve is True:
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
                    if permiso.close is True:
                        ACCESO = True
                        break
        return ACCESO

    def __crear(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.create is True:
                        ACCESO = True
                        break
        return ACCESO

    def __configurar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.setup is True:
                        ACCESO = True
                        break
        return ACCESO

    def __consultar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.view is True:
                        ACCESO = True
                        break
        return ACCESO

    def __corregir(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.update is True:
                        ACCESO = True
                        break
        return ACCESO

    def __editar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.edit is True:
                        ACCESO = True
                        break
        return ACCESO

    def __eliminar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.delete is True:
                        ACCESO = True
                        break
        return ACCESO

    def __importar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.import_ is True:
                        ACCESO = True
                        break
        return ACCESO

    def __reportes(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.report is True:
                        ACCESO = True
                        break
        return ACCESO

    def __solicitar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.request is True:
                        ACCESO = True
                        break
        return ACCESO

    def __validar(self) -> bool:
        ACCESO = False
        if self.__init_valido and self.permisos_usuario:
            for permisos in self.permisos_usuario:
                for permiso in permisos:
                    if permiso.validate is True:
                        ACCESO = True
                        break
        return ACCESO


# <------------------------------------------------------------------------------------------------------------------------> #
# Permisos Predeterminados


def cargar_permisos_predeterminados() -> None:
    """Carga permisos predeterminados a la base de datos."""
    from cacao_accounting.database import database

    log.debug("Inicia craga permisos predeterminados.")
    PURCHASING_MANAGER = RolesAccess(
        rol_id=obtener_id_rol_por_monbre("purchasing_manager"),
        module_id=obtener_id_modulo_por_nombre("purchases"),
        access=True,
        update=True,
        set_null=True,
        approve=True,
        bi=True,
        close=True,
        setup=True,
        view=True,
        create=True,
        edit=True,
        delete=False,
        import_=True,
        report=True,
        request=True,
        validate=True,
    )
    PURCHASING_AUXILIAR = RolesAccess(
        rol_id=obtener_id_rol_por_monbre("purchasing_auxiliar"),
        module_id=obtener_id_modulo_por_nombre("purchases"),
        access=True,
        update=True,
        set_null=False,
        approve=False,
        bi=True,
        close=False,
        setup=False,
        view=True,
        create=True,
        edit=True,
        delete=False,
        import_=False,
        report=True,
        request=True,
        validate=False,
    )
    PURCHASING_USER = RolesAccess(
        rol_id=obtener_id_rol_por_monbre("purchasing_user"),
        module_id=obtener_id_modulo_por_nombre("purchases"),
        access=True,
        update=False,
        set_null=False,
        approve=False,
        bi=False,
        close=False,
        setup=False,
        view=True,
        create=False,
        edit=False,
        delete=False,
        import_=False,
        report=False,
        request=True,
        validate=False,
    )
    ACCOUNTING_MANAGER = RolesAccess(
        rol_id=obtener_id_rol_por_monbre("accounting_manager"),
        module_id=obtener_id_modulo_por_nombre("accounting"),
        access=True,
        update=True,
        set_null=True,
        approve=True,
        bi=True,
        close=True,
        setup=True,
        view=True,
        create=True,
        edit=True,
        delete=False,
        import_=True,
        report=True,
        request=True,
        validate=True,
    )
    ACCOUNTING_AUXILIAR = RolesAccess(
        rol_id=obtener_id_rol_por_monbre("accounting_auxiliar"),
        module_id=obtener_id_modulo_por_nombre("accounting"),
        access=True,
        update=True,
        set_null=False,
        approve=False,
        bi=True,
        close=False,
        setup=False,
        view=True,
        create=True,
        edit=True,
        delete=False,
        import_=False,
        report=True,
        request=True,
        validate=False,
    )
    ACCOUNTING_USER = RolesAccess(
        rol_id=obtener_id_rol_por_monbre("accounting_user"),
        module_id=obtener_id_modulo_por_nombre("accounting"),
        access=True,
        update=False,
        set_null=False,
        approve=False,
        bi=False,
        close=False,
        setup=False,
        view=True,
        create=False,
        edit=False,
        delete=False,
        import_=False,
        report=False,
        request=True,
        validate=False,
    )
    INVENTORY_MANAGER = RolesAccess(
        rol_id=obtener_id_rol_por_monbre("inventory_manager"),
        module_id=obtener_id_modulo_por_nombre("inventory"),
        access=True,
        update=True,
        set_null=True,
        approve=True,
        bi=True,
        close=True,
        setup=True,
        view=True,
        create=True,
        edit=True,
        delete=False,
        import_=True,
        report=True,
        request=True,
        validate=True,
    )
    INVENTORY_AUXILIAR = RolesAccess(
        rol_id=obtener_id_rol_por_monbre("inventory_auxiliar"),
        module_id=obtener_id_modulo_por_nombre("inventory"),
        access=True,
        update=True,
        set_null=False,
        approve=False,
        bi=True,
        close=False,
        setup=False,
        view=True,
        create=True,
        edit=True,
        delete=False,
        import_=False,
        report=True,
        request=True,
        validate=False,
    )
    INVENTORY_USER = RolesAccess(
        rol_id=obtener_id_rol_por_monbre("inventory_user"),
        module_id=obtener_id_modulo_por_nombre("inventory"),
        access=True,
        update=False,
        set_null=False,
        approve=False,
        bi=False,
        close=False,
        setup=False,
        view=True,
        create=False,
        edit=False,
        delete=False,
        import_=False,
        report=False,
        request=True,
        validate=False,
    )
    HEAD_OF_TREASURY = RolesAccess(
        rol_id=obtener_id_rol_por_monbre("head_of_treasury"),
        module_id=obtener_id_modulo_por_nombre("cash"),
        access=True,
        update=True,
        set_null=True,
        approve=True,
        bi=True,
        close=True,
        setup=True,
        view=True,
        create=True,
        edit=True,
        delete=False,
        import_=True,
        report=True,
        request=True,
        validate=True,
    )
    JUNIOR_OF_TREASURY = RolesAccess(
        rol_id=obtener_id_rol_por_monbre("auxiliar_of_treasury"),
        module_id=obtener_id_modulo_por_nombre("cash"),
        access=True,
        update=True,
        set_null=False,
        approve=False,
        bi=True,
        close=False,
        setup=False,
        view=True,
        create=True,
        edit=True,
        delete=False,
        import_=False,
        report=True,
        request=True,
        validate=False,
    )
    USER_OF_TREASURY = RolesAccess(
        rol_id=obtener_id_rol_por_monbre("user_of_treasury"),
        module_id=obtener_id_modulo_por_nombre("cash"),
        access=True,
        update=False,
        set_null=False,
        approve=False,
        bi=False,
        close=False,
        setup=False,
        view=True,
        create=False,
        edit=False,
        delete=False,
        import_=False,
        report=False,
        request=True,
        validate=False,
    )
    SALES_MANAGER = RolesAccess(
        rol_id=obtener_id_rol_por_monbre("sales_manager"),
        module_id=obtener_id_modulo_por_nombre("sales"),
        access=True,
        update=True,
        set_null=True,
        approve=True,
        bi=True,
        close=True,
        setup=True,
        view=True,
        create=True,
        edit=True,
        delete=False,
        import_=True,
        report=True,
        request=True,
        validate=True,
    )
    SALES_AUXILIAR = RolesAccess(
        rol_id=obtener_id_rol_por_monbre("sales_auxiliar"),
        module_id=obtener_id_modulo_por_nombre("sales"),
        access=True,
        update=True,
        set_null=False,
        approve=False,
        bi=True,
        close=False,
        setup=False,
        view=True,
        create=True,
        edit=True,
        delete=False,
        import_=False,
        report=True,
        request=True,
        validate=False,
    )
    SALES_USER = RolesAccess(
        rol_id=obtener_id_rol_por_monbre("sales_user"),
        module_id=obtener_id_modulo_por_nombre("sales"),
        access=True,
        update=False,
        set_null=False,
        approve=False,
        bi=False,
        close=False,
        setup=False,
        view=True,
        create=False,
        edit=False,
        delete=False,
        import_=False,
        report=False,
        request=True,
        validate=False,
    )
    CONTROLLER = []
    for MODULO in MODULOS:
        CONTROLLER.append(
            RolesAccess(
                rol_id=obtener_id_rol_por_monbre("comptroller"),
                module_id=obtener_id_modulo_por_nombre(MODULO),
                access=True,
                update=False,
                set_null=False,
                approve=False,
                bi=False,
                close=False,
                setup=False,
                view=True,
                create=False,
                edit=False,
                delete=False,
                import_=False,
                report=True,
                request=False,
                validate=False,
            )
        )
    BI = []
    for MODULO in MODULOS:
        BI.append(
            RolesAccess(
                rol_id=obtener_id_rol_por_monbre("business_analyst"),
                module_id=obtener_id_modulo_por_nombre(MODULO),
                access=True,
                update=False,
                set_null=False,
                approve=False,
                bi=True,
                close=False,
                setup=False,
                view=True,
                create=False,
                edit=False,
                delete=False,
                import_=False,
                report=True,
                request=False,
                validate=False,
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
        if isinstance(permisos, list):
            for MODULO in permisos:
                database.session.add(MODULO)
                database.session.commit()
        else:
            database.session.add(permisos)
            database.session.commit()
