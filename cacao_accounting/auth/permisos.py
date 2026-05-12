# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Administración de permisos de usuario."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------
from sqlalchemy import select

from cacao_accounting.database import Modules, Roles, RolesAccess, RolesUser, User, database
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

    PERMISSION_FIELDS = {
        "access": "access",
        "actualizar": "update",
        "anular": "set_null",
        "autorizar": "approve",
        "bi": "bi",
        "cerrar": "close",
        "configurar": "setup",
        "consultar": "view",
        "corregir": "update",
        "crear": "create",
        "editar": "edit",
        "eliminar": "delete",
        "importar": "import_",
        "reportes": "report",
        "solicitar": "request",
        "validar": "validate",
    }

    access: bool
    actualizar: bool
    anular: bool
    autorizar: bool
    bi: bool
    cerrar: bool
    configurar: bool
    consultar: bool
    corregir: bool
    crear: bool
    editar: bool
    eliminar: bool
    importar: bool
    reportes: bool
    solicitar: bool
    validar: bool

    def __init__(self, modulo: str | None = None, usuario: str | None = None) -> None:
        """Inicia la clase permisos."""
        self.modulo = modulo
        self.usuario = usuario
        self.__init_valido: bool = bool(self.valida_modulo(modulo) and usuario)

        self.usuario_model: User | None = None
        if usuario:
            self.usuario_model = database.session.get(User, usuario)

        if self.__init_valido:
            self.administrador: bool = self.valida_usuario_tiene_rol_administrativo()
            self.roles: list[str] = self.obtener_roles_de_usuario()
            self.permisos_usuario: list[RolesAccess] = self.obtiene_lista_de_permisos()
        else:
            self.administrador = False
            self.roles = []
            self.permisos_usuario = []

        if self.administrador:
            self.autorizado = True
            for permiso_nombre in self.PERMISSION_FIELDS:
                setattr(self, permiso_nombre, True)
        elif self.__init_valido:
            for permiso_nombre in self.PERMISSION_FIELDS:
                setattr(self, permiso_nombre, self._tiene_permiso(self.PERMISSION_FIELDS[permiso_nombre]))
            self.autorizado = self.access
        else:
            self.autorizado = False
            for permiso_nombre in self.PERMISSION_FIELDS:
                setattr(self, permiso_nombre, False)

    def valida_modulo(self, modulo: str | None) -> bool:
        """Verifica si un modulo se encuentra activo por su id."""
        if not modulo:
            return False

        modulos_activos = database.session.execute(select(Modules.id).filter_by(enabled=True)).scalars().all()

        return modulo in modulos_activos

    def obtener_roles_de_usuario(self) -> list[str]:
        """Devuelve una lista con los roles del usuario."""
        return [rol.role_id for rol in RolesUser.query.filter_by(user_id=self.usuario)]

    def obtener_id_rol_administrador(self) -> str | None:
        """Devuelve el UUID asignado al rol administrador."""
        administrador = Roles.query.filter_by(name="admin").first()
        return administrador.id if administrador else None

    def valida_usuario_tiene_rol_administrativo(self) -> bool:
        """Retorna verdadero si el usuario tiene rol administrador o clasificación admin."""
        if self.usuario_model and getattr(self.usuario_model, "classification", None) == "admin":
            return True

        admin_role_id = self.obtener_id_rol_administrador()
        if not admin_role_id or not self.usuario:
            return False
        return RolesUser.query.filter_by(role_id=admin_role_id, user_id=self.usuario).first() is not None

    def obtiene_lista_de_permisos(self) -> list[RolesAccess]:
        """Devuelve todos los permisos del usuario para el modulo actual."""
        if not self.roles or not self.modulo:
            return []
        return RolesAccess.query.filter(
            RolesAccess.rol_id.in_(self.roles),
            RolesAccess.module_id == self.modulo,
        ).all()

    def _tiene_permiso(self, permission_field: str) -> bool:
        """Verifica si alguno de los roles del usuario tiene el permiso solicitado."""
        if not self.__init_valido or not self.permisos_usuario:
            return False
        for permiso in self.permisos_usuario:
            if getattr(permiso, permission_field, False) is True:
                return True
        return False


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
