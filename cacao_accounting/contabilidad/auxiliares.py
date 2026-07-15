# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

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
from cacao_accounting.database import database


def obtener_lista_entidades_por_id_razonsocial():
    """Devuelve la lista de unidades registrada en la base de datos."""
    from cacao_accounting.database import Entity

    _entidades = []
    _entidades.append(("", ""))
    consulta = database.session.execute(database.select(Entity)).all()
    for i in consulta:
        _entidad = (i[0].code, i[0].name)
        _entidades.append(_entidad)
    return _entidades


def obtener_catalogo_base(entidad_=None):
    """Utilidad para devolver el catalogo de cuentas."""
    from cacao_accounting.database import database, Accounts, Entity

    if entidad_:
        ctas_base = database.session.execute(
            database.select(Accounts).filter(Accounts.parent == None, Accounts.entity == entidad_)  # noqa: E711
        ).all()
    else:
        ctas_base = database.session.execute(
            database.select(Accounts).join(Entity).filter(Accounts.parent == None, Entity.status == "default")  # noqa: E711
        ).all()

    return ctas_base


def obtener_catalogo_centros_costo_base(entidad_=None):
    """Utilidad para devolver el catalogo de centros de costos."""
    from cacao_accounting.database import CostCenter, Entity

    if entidad_:
        ctas_base = database.session.execute(
            database.select(CostCenter).filter(CostCenter.parent == None, CostCenter.entity == entidad_)  # noqa: E711
        ).all()
    else:
        ctas_base = database.session.execute(
            database.select(CostCenter)
            .join(Entity)
            .filter(CostCenter.parent == None, Entity.status == "default")  # noqa: E711
        ).all()

    return ctas_base


def obtener_catalogo(entidad_=None):
    """Utilidad para devolver el catalogo de cuentas."""
    from cacao_accounting.database import Accounts, Entity

    if entidad_:
        ctas = database.session.execute(
            database.select(Accounts).filter(Accounts.parent != None, Accounts.entity == entidad_)  # noqa: E711
        ).all()
    else:
        ctas = database.session.execute(
            database.select(Accounts).join(Entity).filter(Accounts.parent != None, Entity.status == "default")  # noqa: E711
        ).all()

    return ctas


def obtener_centros_costos(entidad_=None):
    """Utilidad para devolver el catalogo de centros de costos."""
    from cacao_accounting.database import CostCenter, Entity

    if entidad_:
        return database.session.execute(database.select(CostCenter).filter(CostCenter.entity == entidad_)).all()
    else:
        return database.session.execute(database.select(CostCenter).join(Entity).filter(Entity.status == "default")).all()


def obtener_entidades():
    """Utilidad para obtener listado de entidades."""
    from cacao_accounting.database import Entity

    _entidades = database.session.execute(database.select(Entity)).all()
    return _entidades


def obtener_entidad(ent=None):
    """Obtiene la entidad actual o la entidad predeterminada."""
    from cacao_accounting.database import Entity

    if ent:
        _entidad = database.session.execute(database.select(Entity).filter(Entity.code == ent)).first()
    else:
        _entidad = database.session.execute(database.select(Entity).filter(Entity.status == "default")).first()
    return _entidad


def obtener_arbol_cuentas(entidad_=None):
    """Devuelve todas las cuentas contables como objetos modelo para rendering de árbol."""
    from cacao_accounting.database import Accounts, Entity

    if entidad_:
        return list(
            database.session.execute(
                database.select(Accounts).filter(Accounts.entity == entidad_).order_by(Accounts.code)
            ).scalars()
        )
    return list(
        database.session.execute(
            database.select(Accounts).join(Entity).filter(Entity.status == "default").order_by(Accounts.code)
        ).scalars()
    )


def obtener_arbol_ccostos(entidad_=None):
    """Devuelve todos los centros de costo como objetos modelo para rendering de árbol."""
    from cacao_accounting.database import CostCenter, Entity

    if entidad_:
        return list(
            database.session.execute(
                database.select(CostCenter).filter(CostCenter.entity == entidad_).order_by(CostCenter.code)
            ).scalars()
        )
    return list(
        database.session.execute(
            database.select(CostCenter).join(Entity).filter(Entity.status == "default").order_by(CostCenter.code)
        ).scalars()
    )


def obtener_arbol_unidades(entidad_=None):
    """Devuelve todas las unidades de negocio como objetos modelo para rendering de árbol."""
    from cacao_accounting.database import Unit, Entity

    if entidad_:
        return list(
            database.session.execute(database.select(Unit).filter(Unit.entity == entidad_).order_by(Unit.code)).scalars()
        )
    return list(
        database.session.execute(
            database.select(Unit).join(Entity).filter(Entity.status == "default").order_by(Unit.code)
        ).scalars()
    )


def obtener_arbol_proyectos(entidad_=None):
    """Devuelve todos los proyectos como objetos modelo para rendering de árbol."""
    from cacao_accounting.database import Project, Entity

    if entidad_:
        return list(
            database.session.execute(
                database.select(Project).filter(Project.entity == entidad_).order_by(Project.code)
            ).scalars()
        )
    return list(
        database.session.execute(
            database.select(Project).join(Entity).filter(Entity.status == "default").order_by(Project.code)
        ).scalars()
    )


def build_tree_data(nodes, parent_field, id_field, get_url_func, get_badges_func=None):
    """Convierte una lista plana de nodos en estructura de árbol para el template.

    Returns:
        roots: lista de nodos raíz (donde parent_field es None)
        all_nodes: lista de dicts con 'obj', 'url', 'badges' para cada nodo
    """
    all_items = []
    for node in nodes:
        item = {
            "obj": node,
            "code": getattr(node, "code"),
            "name": getattr(node, "name"),
            "parent": getattr(node, parent_field, None),
            "id": getattr(node, id_field),
            "url": get_url_func(node),
            "badges": get_badges_func(node) if get_badges_func else [],
        }
        all_items.append(item)

    roots = [item for item in all_items if item["parent"] is None]
    return roots, all_items


def obtener_lista_monedas():
    """Devuelve la lista de monedas disponibles en la base de datos."""
    from cacao_accounting.database import Currency

    monedas = []
    consulta = database.session.execute(database.select(Currency)).all()
    for i in consulta:
        moneda = (i[0].code, i[0].name)
        monedas.append(moneda)
    return monedas


def obtener_lista_monedas_activas():
    """Devuelve la lista de monedas activas en la base de datos."""
    from cacao_accounting.database import Currency

    monedas = []
    consulta = database.session.execute(database.select(Currency).filter(Currency.active.is_(True))).all()
    for i in consulta:
        moneda = (i[0].code, i[0].name)
        monedas.append(moneda)
    return monedas
