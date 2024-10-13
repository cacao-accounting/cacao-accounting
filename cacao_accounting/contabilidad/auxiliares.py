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

"""Funciones auxiliares para el modulo de contabilidad."""

# ---------------------------------------------------------------------------------------
# Libreria estandar
# --------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Librerias de terceros
# ---------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------
# Recursos locales
# ---------------------------------------------------------------------------------------


def obtener_lista_entidades_por_id_razonsocial():
    """Devuelve la lista de unidades registrada en la base de datos."""
    from cacao_accounting.database import Entidad

    _entidades = []
    _entidades.append(("", ""))
    consulta = Entidad.query.all()
    for i in consulta:
        _entidad = (i.entidad, i.razon_social)
        _entidades.append(_entidad)
    return _entidades


def obtener_catalogo_base(entidad_=None):
    """Utilidad para devolver el catalogo de cuentas."""
    from cacao_accounting.database import database, Accounts, Entity

    if entidad_:
        ctas_base = database.session.execute(
            database.select(Accounts).filter(Accounts.parent == None, Accounts.entity == entidad_)
        ).all()
    else:
        ctas_base = database.session.execute(
            database.select(Accounts).join(Entity).filter(Accounts.parent == None, Entity.status == "default")
        ).all()

    return ctas_base


def obtener_catalogo_centros_costo_base(entidad_=None):
    """Utilidad para devolver el catalogo de centros de costos."""
    from cacao_accounting.database import CentroCosto, Entidad

    if entidad_:
        ctas_base = CentroCosto.query.filter(CentroCosto.padre == None, CentroCosto.entidad == entidad_).all()  # noqa: E711
    else:
        ctas_base = (
            CentroCosto.query.join(Entidad)
            .filter(CentroCosto.padre == None, Entidad.status == "predeterminado")  # noqa: E711
            .all()
        )

    return ctas_base


def obtener_catalogo(entidad_=None):
    """Utilidad para devolver el catalogo de cuentas."""
    from cacao_accounting.database import database, Accounts, Entity

    if entidad_:
        ctas = database.session.execute(
            database.select(Accounts).filter(Accounts.parent != None, Accounts.entity == entidad_)
        ).all()
    else:
        ctas = database.session.execute(
            database.select(Accounts).join(Entity).filter(Accounts.parent != None, Entity.status == "default")
        ).all()

    return ctas


def obtener_centros_costos(entidad_=None):
    """Utilidad para devolver el catalogo de centros de costos."""
    from cacao_accounting.database import CentroCosto, Entidad

    if entidad_:
        return CentroCosto.query.filter(CentroCosto.entidad == entidad_).all()
    else:
        return CentroCosto.query.join(Entidad).filter(Entidad.status == "predeterminado").all()


def obtener_entidades():
    """Utilidad para obtener listado de entidades."""
    from cacao_accounting.database import database, Entity

    _entidades = database.session.execute(database.select(Entity)).all()
    return _entidades


def obtener_entidad(ent=None):
    """Obtiene la entidad actual o la entidad predeterminada."""
    from cacao_accounting.database import database, Entity

    if ent:
        _entidad = database.session.execute(database.select(Entity).filter(Entity.code == ent)).first()
    else:
        _entidad = database.session.execute(database.select(Entity).filter(Entity.status == "default")).first()
    return _entidad


def obtener_lista_monedas():
    """Devuelve la lista de monedas disponibles en la base de datos."""
    from cacao_accounting.database import database, Currency

    monedas = []
    consulta = database.session.execute(database.select(Currency)).all()
    for i in consulta:
        moneda = (i[0].code, i[0].name)
        monedas.append(moneda)
    return monedas
