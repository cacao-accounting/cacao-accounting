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

from cacao_accounting.loggin import logger as log
from cacao_accounting.modulos import _init_modulos


def monedas():
    try:
        from teritorio import Currencies
    except ImportError:
        Currencies = None
    from cacao_accounting.database import db, Moneda

    log.debug("Iniciando carga de base monedas a la base de datos.")
    if Currencies:
        for moneda in Currencies():
            registro = Moneda(id=moneda.code, nombre=moneda.name, codigo=moneda.numeric_code, decimales=moneda.minor_units)
            db.session.add(registro)
    else:
        log.debug("No se detecto libreria territorio, cargando solo monedas básicas.")
        nio = Moneda(id="NIO", nombre="Cordoba Oro", codigo=558, decimales=2)
        db.session.add(nio)
        usd = Moneda(id="USD", nombre="US Dollar", codigo=840, decimales=2)
        db.session.add(usd)
    db.session.commit()
    log.debug("Monedas cargadas Correctamente")


def base_data():
    log.debug("Iniciando carga de datos base al sistema.")
    monedas()
    _init_modulos()
    log.debug("Batos base cargados en la base de datos.")
