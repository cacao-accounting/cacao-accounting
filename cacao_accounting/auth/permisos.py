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
from flask_login import current_user
from cacao_accounting.database import Modulos, RolesUsuario, Roles, RolesPermisos
from cacao_accounting.registro import Registro


class RegistroPermisosRol(Registro):
    def __init__(self):

        self.tabla = RolesPermisos


class Acciones:

    administrador = False
    modulo = None
    usuario = None

    def actualizar(self) -> bool:
        if self.administrador:
            return True
        else:
            pass

    def anular(self) -> bool:
        if self.administrador:
            return True
        else:
            pass

    def autorizar(self) -> bool:
        if self.administrador:
            return True
        else:
            pass

    def bi(self) -> bool:
        if self.administrador:
            return True
        else:
            pass

    def cerrar(self) -> bool:
        if self.administrador:
            return True
        else:
            pass

    def crear(self) -> bool:
        if self.administrador:
            return True
        else:
            pass

    def consultar(self) -> bool:
        if self.administrador:
            return True
        else:
            pass

    def editar(self) -> bool:
        if self.administrador:
            return True
        else:
            pass

    def eliminar(self) -> bool:
        if self.administrador:
            return True
        else:
            pass

    def reportes(self) -> bool:
        if self.administrador:
            return True
        else:
            pass

    def validar(self) -> bool:
        if self.administrador:
            return True
        else:
            pass


class Permisos(Acciones):
    def __init__(self, modulo: Union[None, str] = None) -> None:
        self.modulo = modulo
        self.usuario = current_user
        if current_user.is_authenticated and modulo:
            self.administrador = self.valida_usuario_tiene_rol_administrativo()

    def obtener_roles_de_usuario(self) -> Union[tuple, None]:
        if self.usuario:
            return RolesUsuario.query.filter_by(user_id=self.usuario.id)
        else:
            return None

    def obtener_id_rol_administrador(self) -> str:
        ID_ROL_ADMIN = Roles.query.filter_by(name="admin").first()
        return ID_ROL_ADMIN.id

    def valida_usuario_tiene_rol_administrativo(self) -> bool:
        CONSULTA = RolesUsuario.query.filter(
            RolesUsuario.role_id == self.obtener_id_rol_administrador(), RolesUsuario.user_id == self.usuario.id
        ).first()
        return CONSULTA is not None

    def probar_acceso_segun_rol(self) -> bool:
        pass

    def usuario_autorizado(self) -> bool:
        if self.administrador:
            return True


def obtener_id_modulo(modulo) -> str:
    MODULO = Modulos.query.filter_by(modulo=modulo).first()
    return MODULO.id


def obtener_id_rol(rol) -> str:
    ROL = Roles.query.filter_by(name=rol).first()
    return ROL.id
