# Módulo: Configuración (Setup)
Rol: Infraestructura transversal, identidad y seguridad.

## Principios de Diseño
- Master data global independiente de compañía (`Item`, `Party`).
- Roles y Permisos basados en RBAC.
- Series e Identificadores generados por el sistema, no editables.

## Modelos Principales
- **Identidad:** `Entity`, `Unit`, `CacaoConfig`.
- **Seguridad:** `User`, `Roles`, `RolesAccess`, `RolesUser`.
- **Maestros Globales:** `Currency`, `UOM`, `Item`, `Party`.
- **Identificadores:** `NamingSeries`, `Sequence`, `GeneratedIdentifierLog`.

## Wizard de Inicio
1. Compañía → 2. Catálogo → 3. Libro → 4. Año Fiscal → 5. Período → 6. Admin.
