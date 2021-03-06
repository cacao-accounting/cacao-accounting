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

"""
Datos básicos para iniciar el sistema.
"""

from cacao_accounting.loggin import log
from cacao_accounting.modulos import _init_modulos

# pylint: disable=import-outside-toplevel


def registra_monedas(carga_rapida=False):
    from teritorio import Currencies
    from cacao_accounting.database import db, Moneda

    log.debug("Iniciando carga de base monedas a la base de datos.")
    if carga_rapida:
        from cacao_accounting.contabilidad.registros.moneda import RegistroMoneda

        nio = {"id": "NIO", "nombre": "Cordobas Oro", "codigo": 558, "decimales": 2}
        usd = {"id": "USD", "nombre": "Dolares de los Estados Unidos", "codigo": 559, "decimales": 2}
        r = RegistroMoneda()
        r.crear(nio)
        r.crear(usd)
    else:
        for moneda in Currencies():
            registro = Moneda(id=moneda.code, nombre=moneda.name, codigo=moneda.numeric_code, decimales=moneda.minor_units)
            db.session.add(registro)
    db.session.commit()
    log.debug("Monedas cargadas Correctamente")


def base_data(carga_rapida=False):
    """
    Definición de metodo para cargar información base al sistema.
    """
    log.debug("Iniciando carga de datos base al sistema.")
    registra_monedas(carga_rapida=carga_rapida)
    _init_modulos()
    log.debug("Batos base cargados en la base de datos.")
