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

from typing import Union
from cacao_accounting.database import RolesUsuario, Roles, RolesPermisos
from cacao_accounting.database.helpers import obtener_id_modulo_por_monbre, obtener_id_rol_por_monbre
from cacao_accounting.loggin import log
from cacao_accounting.registro import Registro


class RegistroPermisosRol(Registro):
    def __init__(self):

        self.tabla = RolesPermisos


class Permisos:
    """
    Administración de Permisos
    ==========================

    Los permisos en Cacao Accounting se basan en los siguientes conceptos:

     - Usuario: Una persona con acceso al sistema identificado por su id y contraseña.

     - Rol: Los usuarios pueden tener uno o mas roles asignados, los permisos se definen a nivel de rol
      nunca a nivel de usuario.

     - Roles de Usuario: Esta tabla mapea los roles asignados a cada usuario.

     - Permisos Roles: Lista de permisos que otorga un Rol en un modulo determinado.

     - Acción: Es un acto realiado por un usuario que cambia el estado de una transacción, se han definido
     las siguientes acciones: actualizar, anular, autorizar, bi, cerrar, consultar, crear, consultar, editar,
     eliminar, reportes, validar.

    Los permisos de validad por usuario y por modulo, para inicializar la clase se debe inicializar pasando
    como parametros un UUID valido de usuario y un UUID valido de modulo.

    Para cada acción se valida que el usuario posee un rol que da acceso a la apción determinada en el modulo
    especificado, si uno de los roles del usuario otorga permiso se aprueba como valido.
    """

    def __init__(self, modulo: Union[None, str] = None, usuario: Union[None, str] = None) -> None:
        self.modulo = modulo
        if usuario:
            self.usuario = usuario
            self.administrador = self.valida_usuario_tiene_rol_administrativo()
            self.roles = self.obtener_roles_de_usuario()
            self.autorizado = self.__usuario_autorizado()
            self.actualizar = self.__actualizar()
            self.anular = self.__anular()
            self.autorizar = self.__autorizar()
            self.bi = self.__bi()
            self.cerrar = self.__cerrar()
            self.consultar = self.__consultar()
            self.crear = self.__crear()
            self.consultar = self.__consultar()
            self.editar = self.__editar()
            self.eliminar = self.__eliminar()
            self.reportes = self.__reportes()
            self.validar = self.__validar()
        else:
            self.usuario = None
            self.administrador = False
            self.roles = None
            self.actualizar = False
            self.anular = False
            self.autorizar = False
            self.bi = False
            self.cerrar = False
            self.consultar = False
            self.crear = False
            self.consultar = False
            self.editar = False
            self.eliminar = False
            self.reportes = False
            self.validar = False

    def obtener_roles_de_usuario(self) -> Union[list, None]:
        ROLES_USUARIO = RolesUsuario.query.filter_by(user_id=self.usuario)
        ROLES = []
        for ROL in ROLES_USUARIO:
            ROLES.append(ROL.role_id)
            return ROLES

    def obtener_id_rol_administrador(self) -> str:
        ID_ROL_ADMIN = Roles.query.filter_by(name="admin").first()
        return ID_ROL_ADMIN.id

    def valida_usuario_tiene_rol_administrativo(self) -> bool:
        CONSULTA = RolesUsuario.query.filter(
            RolesUsuario.role_id == self.obtener_id_rol_administrador(), RolesUsuario.user_id == self.usuario
        ).first()
        return CONSULTA is not None

    def __usuario_autorizado(self) -> bool:
        if self.administrador:
            return True
        else:
            ACCESO = False
            if self.roles:
                for ROL in self.roles:
                    CONSULTA_PERMISOS = RolesPermisos.query.filter(
                        RolesPermisos.rol_id == ROL, RolesPermisos.modulo_id == self.modulo
                    )
                    for PERMISO in CONSULTA_PERMISOS:
                        if PERMISO.acceso is True:
                            ACCESO = True
                            break
        return ACCESO

    def __actualizar(self) -> bool:
        if self.administrador:
            return True
        else:
            ACCESO = False
            if self.roles:
                for ROL in self.roles:
                    CONSULTA_PERMISOS = RolesPermisos.query.filter(
                        RolesPermisos.rol_id == ROL, RolesPermisos.modulo_id == self.modulo
                    )
                    for PERMISO in CONSULTA_PERMISOS:
                        if PERMISO.actualizar is True:
                            ACCESO = True
                            break
        return ACCESO

    def __anular(self) -> bool:
        if self.administrador:
            return True
        else:
            ACCESO = False
            if self.roles:
                for ROL in self.roles:
                    CONSULTA_PERMISOS = RolesPermisos.query.filter(
                        RolesPermisos.rol_id == ROL, RolesPermisos.modulo_id == self.modulo
                    )
                    for PERMISO in CONSULTA_PERMISOS:
                        if PERMISO.anular is True:
                            ACCESO = True
                            break
        return ACCESO

    def __autorizar(self) -> bool:
        if self.administrador:
            return True
        else:
            ACCESO = False
            if self.roles:
                for ROL in self.roles:
                    CONSULTA_PERMISOS = RolesPermisos.query.filter(
                        RolesPermisos.rol_id == ROL, RolesPermisos.modulo_id == self.modulo
                    )
                    for PERMISO in CONSULTA_PERMISOS:
                        if PERMISO.autorizar is True:
                            ACCESO = True
                            break
        return ACCESO

    def __bi(self) -> bool:
        if self.administrador:
            return True
        else:
            ACCESO = False
            if self.roles:
                for ROL in self.roles:
                    CONSULTA_PERMISOS = RolesPermisos.query.filter(
                        RolesPermisos.rol_id == ROL, RolesPermisos.modulo_id == self.modulo
                    )
                    for PERMISO in CONSULTA_PERMISOS:
                        if PERMISO.bi is True:
                            ACCESO = True
                            break
        return ACCESO

    def __cerrar(self) -> bool:
        if self.administrador:
            return True
        else:
            ACCESO = False
            if self.roles:
                for ROL in self.roles:
                    CONSULTA_PERMISOS = RolesPermisos.query.filter(
                        RolesPermisos.rol_id == ROL, RolesPermisos.modulo_id == self.modulo
                    )
                    for PERMISO in CONSULTA_PERMISOS:
                        if PERMISO.cerrar is True:
                            ACCESO = True
                            break
        return ACCESO

    def __crear(self) -> bool:
        if self.administrador:
            return True
        else:
            ACCESO = False
            if self.roles:
                for ROL in self.roles:
                    CONSULTA_PERMISOS = RolesPermisos.query.filter(
                        RolesPermisos.rol_id == ROL, RolesPermisos.modulo_id == self.modulo
                    )
                    for PERMISO in CONSULTA_PERMISOS:
                        if PERMISO.crear is True:
                            ACCESO = True
                            break
        return ACCESO

    def __consultar(self) -> bool:
        if self.administrador:
            return True
        else:
            ACCESO = False
            if self.roles:
                for ROL in self.roles:
                    CONSULTA_PERMISOS = RolesPermisos.query.filter(
                        RolesPermisos.rol_id == ROL, RolesPermisos.modulo_id == self.modulo
                    )
                    for PERMISO in CONSULTA_PERMISOS:
                        if PERMISO.consultar is True:
                            ACCESO = True
                            break
        return ACCESO

    def __editar(self) -> bool:
        if self.administrador:
            return True
        else:
            ACCESO = False
            if self.roles:
                for ROL in self.roles:
                    CONSULTA_PERMISOS = RolesPermisos.query.filter(
                        RolesPermisos.rol_id == ROL, RolesPermisos.modulo_id == self.modulo
                    )
                    for PERMISO in CONSULTA_PERMISOS:
                        if PERMISO.consultar is True:
                            ACCESO = True
                            break
        return ACCESO

    def __eliminar(self) -> bool:
        if self.administrador:
            return True
        else:
            ACCESO = False
            if self.roles:
                for ROL in self.roles:
                    CONSULTA_PERMISOS = RolesPermisos.query.filter(
                        RolesPermisos.rol_id == ROL, RolesPermisos.modulo_id == self.modulo
                    )
                    for PERMISO in CONSULTA_PERMISOS:
                        if PERMISO.eliminar is True:
                            ACCESO = True
                            break
        return ACCESO

    def __reportes(self) -> bool:
        if self.administrador:
            return True
        else:
            ACCESO = False
            if self.roles:
                for ROL in self.roles:
                    CONSULTA_PERMISOS = RolesPermisos.query.filter(
                        RolesPermisos.rol_id == ROL, RolesPermisos.modulo_id == self.modulo
                    )
                    for PERMISO in CONSULTA_PERMISOS:
                        if PERMISO.reportes is True:
                            ACCESO = True
                            break
        return ACCESO

    def __validar(self) -> bool:
        if self.administrador:
            return True
        else:
            ACCESO = False
            if self.roles:
                for ROL in self.roles:
                    CONSULTA_PERMISOS = RolesPermisos.query.filter(
                        RolesPermisos.rol_id == ROL, RolesPermisos.modulo_id == self.modulo
                    )
                    for PERMISO in CONSULTA_PERMISOS:
                        if PERMISO.validar is True:
                            ACCESO = True
                            break
        return ACCESO


# <------------------------------------------------------------------------------------------------------------------------> #
# Permisos Predeterminados


def cargar_permisos_predeterminados() -> None:
    from cacao_accounting.database import db

    log.debug("Inicia craga permisos predeterminados.")
    PURCHASING_MANAGER = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("purchasing_manager"),
        modulo_id=obtener_id_modulo_por_monbre("buying"),
        acceso=True,
        actualizar=True,
        anular=True,
        autorizar=True,
        bi=True,
        cerrar=True,
        crear=True,
        consultar=True,
        editar=True,
        eliminar=True,
        reportes=True,
        validar=True,
    )
    PURCHASING_AUXILIAR = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("purchasing_auxiliar"),
        modulo_id=obtener_id_modulo_por_monbre("buying"),
        acceso=True,
        actualizar=True,
        anular=False,
        autorizar=False,
        bi=True,
        cerrar=False,
        crear=True,
        consultar=True,
        editar=True,
        eliminar=False,
        reportes=True,
        validar=False,
    )
    ACCOUNTING_MANAGER = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("accounting_manager"),
        modulo_id=obtener_id_modulo_por_monbre("accounting"),
        acceso=True,
        actualizar=True,
        anular=True,
        autorizar=True,
        bi=True,
        cerrar=True,
        crear=True,
        consultar=True,
        editar=True,
        eliminar=True,
        reportes=True,
        validar=True,
    )
    ACCOUNTING_AUXILIAR = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("accounting_auxiliar"),
        modulo_id=obtener_id_modulo_por_monbre("accounting"),
        acceso=True,
        actualizar=True,
        anular=False,
        autorizar=False,
        bi=True,
        cerrar=False,
        crear=True,
        consultar=True,
        editar=True,
        eliminar=False,
        reportes=True,
        validar=False,
    )
    INVENTORY_MANAGER = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("inventory_manager"),
        modulo_id=obtener_id_modulo_por_monbre("inventory"),
        acceso=True,
        actualizar=True,
        anular=True,
        autorizar=True,
        bi=True,
        cerrar=True,
        crear=True,
        consultar=True,
        editar=True,
        eliminar=True,
        reportes=True,
        validar=True,
    )
    INVENTORY_AUXILIAR = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("inventory_auxiliar"),
        modulo_id=obtener_id_modulo_por_monbre("inventory"),
        acceso=True,
        actualizar=True,
        anular=False,
        autorizar=False,
        bi=True,
        cerrar=False,
        crear=True,
        consultar=True,
        editar=True,
        eliminar=False,
        reportes=True,
        validar=False,
    )
    HEAD_OF_TREASURY = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("head_of_treasury"),
        modulo_id=obtener_id_modulo_por_monbre("cash"),
        acceso=True,
        actualizar=True,
        anular=True,
        autorizar=True,
        bi=True,
        cerrar=True,
        crear=True,
        consultar=True,
        editar=True,
        eliminar=True,
        reportes=True,
        validar=True,
    )
    JUNIOR_OF_TREASURY = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("junior_of_treasury"),
        modulo_id=obtener_id_modulo_por_monbre("cash"),
        acceso=True,
        actualizar=True,
        anular=False,
        autorizar=False,
        bi=True,
        cerrar=False,
        crear=True,
        consultar=True,
        editar=True,
        eliminar=False,
        reportes=True,
        validar=False,
    )
    SALES_MANAGER = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("sales_manager"),
        modulo_id=obtener_id_modulo_por_monbre("sales"),
        acceso=True,
        actualizar=True,
        anular=True,
        autorizar=True,
        bi=True,
        cerrar=True,
        crear=True,
        consultar=True,
        editar=True,
        eliminar=True,
        reportes=True,
        validar=True,
    )
    SALES_AUXILIAR = RolesPermisos(
        rol_id=obtener_id_rol_por_monbre("sales_auxiliar"),
        modulo_id=obtener_id_modulo_por_monbre("sales"),
        acceso=True,
        actualizar=True,
        anular=False,
        autorizar=False,
        bi=True,
        cerrar=False,
        crear=True,
        consultar=True,
        editar=True,
        eliminar=False,
        reportes=True,
        validar=False,
    )
    PERMISOS_PREDETERMINADOS = [
        PURCHASING_MANAGER,
        PURCHASING_AUXILIAR,
        ACCOUNTING_MANAGER,
        ACCOUNTING_AUXILIAR,
        INVENTORY_MANAGER,
        INVENTORY_AUXILIAR,
        HEAD_OF_TREASURY,
        JUNIOR_OF_TREASURY,
        SALES_MANAGER,
        SALES_AUXILIAR,
    ]
    for PERMISOS in PERMISOS_PREDETERMINADOS:
        db.session.add(PERMISOS)
        db.session.commit()
