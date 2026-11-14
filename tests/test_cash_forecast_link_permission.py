# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 William José Moreno Reyes

"""#2025: el enlace a pronósticos del dashboard de caja exige ``consultar``.

En bancos.html el bloque "Proyección de Flujo de Caja" emite los enlaces a
cash-forecast solo cuando ``acceso.consultar`` es verdadero y el badge usa el
mismo permiso. Un usuario con acceso al módulo de caja pero sin ``consultar``
no debe ver ningún enlace a cash-forecast.
"""

from __future__ import annotations


from cacao_accounting.auth import proteger_passwd
from cacao_accounting.database import (
    Modules,
    Roles,
    RolesAccess,
    RolesUser,
    User,
    UserCompanyAccess,
    database,
)

CLAVE = "caja-sin-consulta-2026"


def _crear_usuario_de_caja_sin_consulta(app, sufijo: str) -> str:
    """Usuario con access=True y consultar (view) sobre el módulo de caja."""
    nombre = f"caja-lectura-{sufijo}"
    with app.app_context():
        if database.session.execute(database.select(User).filter_by(user=nombre)).scalar_one_or_none() is None:
            module_id = database.session.execute(database.select(Modules.id).filter_by(module="cash")).scalar_one()
            rol = Roles(name=f"caja-sin-consulta-{sufijo}", note="Acceso a caja sin consultar")
            database.session.add(rol)
            database.session.flush()
            database.session.add_all(
                [
                    User(
                        id=nombre[:26],
                        user=nombre,
                        name="Caja sin consultar",
                        password=proteger_passwd(CLAVE),
                        active=True,
                        classification="user",
                    ),
                    RolesAccess(rol_id=rol.id, module_id=module_id, access=True, view=False),
                    RolesUser(user_id=nombre[:26], role_id=rol.id, active=True),
                    UserCompanyAccess(user_id=nombre[:26], company_code="cacao"),
                ]
            )
        database.session.commit()
    return nombre


def _iniciar_sesion(client, usuario: str) -> None:
    """Inicia sesión con el formulario real de la aplicación."""
    respuesta = client.post("/login", data={"usuario": usuario, "acceso": CLAVE}, follow_redirects=True)
    assert respuesta.status_code == 200
