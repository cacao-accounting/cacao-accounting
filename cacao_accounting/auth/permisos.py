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
from cacao_accounting.database import RolesUsuario, Roles, RolesPermisos, Modulos
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
        if self.valida_modulo(modulo) and usuario:
            self.modulo: Union[str, None] = modulo
            self.usuario: Union[str, None] = usuario
            self.administrador: Union[bool, None] = self.valida_usuario_tiene_rol_administrativo()
            self.roles: Union[list, None] = self.obtener_roles_de_usuario()
            if self.administrador:
                self.autorizado: Union[bool, None] = True
                self.actualizar: Union[bool, None] = True
                self.anular: Union[bool, None] = True
                self.autorizar: Union[bool, None] = True
                self.bi: Union[bool, None] = True
                self.cerrar: Union[bool, None] = True
                self.consultar: Union[bool, None] = True
                self.corregir: Union[bool, None] = True
                self.crear: Union[bool, None] = True
                self.editar: Union[bool, None] = True
                self.eliminar: Union[bool, None] = True
                self.importar: Union[bool, None] = True
                self.listar: Union[bool, None] = True
                self.reportes: Union[bool, None] = True
                self.validar: Union[bool, None] = True
            else:
                self.autorizado = self.__usuario_autorizado()
                self.actualizar = self.__actualizar()
                self.anular = self.__anular()
                self.autorizar = self.__autorizar()
                self.bi = self.__bi()
                self.cerrar = self.__cerrar()
                self.consultar = self.__consultar()
                self.corregir = self.__corregir()
                self.crear = self.__crear()
                self.editar = self.__editar()
                self.eliminar = self.__eliminar()
                self.importar = self.__importar()
                self.listar = self.__listar()
                self.reportes = self.__reportes()
                self.validar = self.__validar()
        else:
            self.modulo = None
            self.usuario = None
            self.administrador = False
            self.roles = None
            self.autorizado = False
            self.actualizar = False
            self.anular = False
            self.autorizar = False
            self.bi = False
            self.cerrar = False
            self.consultar = False
            self.corregir = False
            self.crear = False
            self.editar = False
            self.eliminar = False
            self.importar = False
            self.listar = False
            self.reportes = False
            self.validar = False

    def valida_modulo(self, modulo: Union[str, None]) -> bool:
        if modulo:
            LISTA_MODULOS_ACTIVOS = []
            CONSULTA = Modulos.query.filter_by(habilitado=True)
            if CONSULTA:
                for r in CONSULTA:
                    LISTA_MODULOS_ACTIVOS.append(r.id)
            return modulo in LISTA_MODULOS_ACTIVOS
        else:
            return False

    def obtener_roles_de_usuario(self):
        ROLES_USUARIO = RolesUsuario.query.filter_by(user_id=self.usuario)
        ROLES = [ROL.role_id for ROL in ROLES_USUARIO]
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

    def __corregir(self) -> bool:
        ACCESO = False
        if self.roles:
            for ROL in self.roles:
                CONSULTA_PERMISOS = RolesPermisos.query.filter(
                    RolesPermisos.rol_id == ROL, RolesPermisos.modulo_id == self.modulo
                )
                for PERMISO in CONSULTA_PERMISOS:
                    if PERMISO.corregir is True:
                        ACCESO = True
                        break
        return ACCESO

    def __editar(self) -> bool:
        ACCESO = False
        if self.roles:
            for ROL in self.roles:
                CONSULTA_PERMISOS = RolesPermisos.query.filter(
                    RolesPermisos.rol_id == ROL, RolesPermisos.modulo_id == self.modulo
                )
                for PERMISO in CONSULTA_PERMISOS:
                    if PERMISO.editar is True:
                        ACCESO = True
                        break
        return ACCESO

    def __eliminar(self) -> bool:
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

    def __importar(self) -> bool:
        ACCESO = False
        if self.roles:
            for ROL in self.roles:
                CONSULTA_PERMISOS = RolesPermisos.query.filter(
                    RolesPermisos.rol_id == ROL, RolesPermisos.modulo_id == self.modulo
                )
                for PERMISO in CONSULTA_PERMISOS:
                    if PERMISO.importar is True:
                        ACCESO = True
                        break
        return ACCESO

    def __listar(self) -> bool:
        ACCESO = False
        if self.roles:
            for ROL in self.roles:
                CONSULTA_PERMISOS = RolesPermisos.query.filter(
                    RolesPermisos.rol_id == ROL, RolesPermisos.modulo_id == self.modulo
                )
                for PERMISO in CONSULTA_PERMISOS:
                    if PERMISO.listar is True:
                        ACCESO = True
                        break
        return ACCESO

    def __reportes(self) -> bool:
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
        listar=True,
        importar=True,
        corregir=True,
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
        listar=True,
        importar=False,
        corregir=False,
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
        listar=True,
        importar=True,
        corregir=True,
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
        listar=True,
        importar=False,
        corregir=False,
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
        listar=True,
        importar=True,
        corregir=True,
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
        listar=True,
        importar=False,
        corregir=False,
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
        listar=True,
        importar=True,
        corregir=True,
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
        listar=True,
        importar=False,
        corregir=False,
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
        listar=True,
        importar=True,
        corregir=True,
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
        listar=True,
        importar=False,
        corregir=False,
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

    MODULOS = ["accounting", "cash", "buying", "inventory", "sales"]
    for MODULO in MODULOS:
        CONTROLLER = RolesPermisos(
            rol_id=obtener_id_rol_por_monbre("comptroller"),
            modulo_id=obtener_id_modulo_por_monbre(MODULO),
            acceso=True,
            actualizar=False,
            anular=False,
            autorizar=False,
            bi=False,
            cerrar=False,
            crear=False,
            consultar=True,
            editar=False,
            eliminar=False,
            reportes=True,
            validar=False,
            listar=True,
            importar=False,
            corregir=False,
        )
        db.session.add(CONTROLLER)
        db.session.commit()
        CONTROLLER = RolesPermisos(
            rol_id=obtener_id_rol_por_monbre("business_analyst"),
            modulo_id=obtener_id_modulo_por_monbre(MODULO),
            acceso=True,
            actualizar=False,
            anular=False,
            autorizar=False,
            bi=True,
            cerrar=False,
            crear=False,
            consultar=True,
            editar=False,
            eliminar=False,
            reportes=True,
            validar=False,
            listar=True,
            importar=False,
            corregir=False,
        )
        db.session.add(CONTROLLER)
        db.session.commit()
