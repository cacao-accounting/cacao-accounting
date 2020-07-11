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

app=create_app(configuracion)
# Ver: https://flask-sqlalchemy.palletsprojects.com/en/2.x/contexts/
app.app_context().push()

class Test_basicos():

    def test_dbschema(self):
        """Validamos que el esquema de la base de datos es valida"""

        from cacao_accounting.database import db, Usuario
        db.drop_all()
        db.create_all()

    def test_login(self):
        """Creamos un usuario y validamos su login"""
        from cacao_accounting.database import Usuario, db
        from cacao_accounting.auth import proteger_passwd
        acceso = "testpasswd123+"
        test_usuario = Usuario(id="utest",
        correo_e = "usuario@dominio.com",
        clave_acceso=proteger_passwd(acceso)
        )
        db.session.add(test_usuario)
        db.session.commit()
        from cacao_accounting.auth import validar_acceso
        assert True == validar_acceso("utest", "testpasswd123+")
