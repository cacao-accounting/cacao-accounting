#!/usr/local/bin/python3

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


from os import environ
from waitress import serve
from cacao_accounting import create_app
from cacao_accounting.loggin import log


log.info("Iniciando ejecución de imagen")


configuracion = {
    "SQLALCHEMY_DATABASE_URI": environ["CACAO_DB"],
    "SECRET_KEY": environ["CACAO_KEY"],
    "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    "DESKTOPMODE": False,
    "ENV": "production",
}

dockerapp = create_app(configuracion)
dockerapp.config["ENV"] = "production"
dockerapp.config

with dockerapp.app_context():
    from cacao_accounting import db_migrate
    from cacao_accounting.database import db
    from cacao_accounting.datos import base_data

    try:
        db.create_all()
        base_data()
    except:
        pass
    db_migrate()

serve(dockerapp, listen="127.0.0.1:8080 [::1]:8080")
