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
from uuid import uuid4
from flask import current_app
from sqlalchemy import Column


def obtiene_texto_unico():
    """
    A partir de un código UUID unico aleatorio devuelve una cadena de texto unica
    que se puede usar como identificador interno.
    """
    return str(uuid4())


with current_app.app_context():
    if current_app.config.get("SQLALCHEMY_DATABASE_URI"):
        DB_URI: Union[str, None] = str(current_app.config["SQLALCHEMY_DATABASE_URI"])
    else:
        DB_URI = None

if DB_URI and DB_URI.startswith("postgresql"):
    from sqlalchemy.dialects.postgresql import UUID

    COLUMNA_UUID = Column(UUID(as_uuid=False), primary_key=True, nullable=True, index=True)

elif DB_URI and (DB_URI.startswith("mysql") or DB_URI.startswith("mariadb")):
    from sqlalchemy.dialects.mysql import VARCHAR

    COLUMNA_UUID = Column(VARCHAR(length=36), primary_key=True, nullable=True, index=True)

elif DB_URI and DB_URI.startswith("mssql"):
    from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER

    COLUMNA_UUID = Column(UNIQUEIDENTIFIER(),  primary_key=True, nullable=True, index=True)

else:
    from sqlalchemy.types import String

    COLUMNA_UUID = Column(String(36), primary_key=True, nullable=True, index=True, default=obtiene_texto_unico)
