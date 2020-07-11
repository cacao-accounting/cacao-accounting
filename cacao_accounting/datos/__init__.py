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

from cacao_accounting import create_app
from cacao_accounting.conf import configuracion


def _demo_usuarios():
    from cacao_accounting.database import Usuario, db
    from cacao_accounting.auth import proteger_passwd
    acceso1 = "cacao"
    usuario1 = Usuario(
        id="cacao",
        correo_e="usuario1@cacao:accounting.io",
        clave_acceso=proteger_passwd(acceso1)
        )
    db.session.add(usuario1)
    db.session.commit()


def cargar_datos():
    pass


def demo_data():
    _demo_usuarios()
