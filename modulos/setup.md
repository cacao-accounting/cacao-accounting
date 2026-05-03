# Módulo: Configuración (Setup)

## Rol en el sistema

Módulo transversal que provee la infraestructura de configuración, identidad,
seguridad y maestros globales para todos los demás módulos.

---

## Principios de diseño

- Master data global es independiente de la compañía (`Party`, `Item`, catálogos).
- `CompanyParty` y el patrón de activación conectan master data con cada compañía.
- Roles y permisos siguen un modelo RBAC.
- Las series e identificadores son generados por el sistema, no editables manualmente.
- Multi-compañía: todo dato transaccional tiene `company`. El setup lo garantiza.

---

## Modelos disponibles en base de datos

### Identidad y Compañía

| Modelo | Tabla | Descripción |
|---|---|---|
| `Entity` | `entity` | Compañía / entidad legal. |
| `Unit` | `unit` | Unidad de negocio / sucursal. UniqueConstraint `(entity, code)`. |
| `Currency` | `currency` | Catálogo global de monedas. |
| `ExchangeRate` | `exchange_rate` | Tasas de cambio históricas. |
| `CacaoConfig` | `cacao_config` | Configuración clave/valor del sistema. |

### Usuarios y Seguridad

| Modelo | Tabla | Descripción |
|---|---|---|
| `User` | `user` | Usuario del sistema. |
| `Roles` | `roles` | Roles disponibles. |
| `RolesAccess` | `roles_access` | Permisos por rol y módulo. |
| `RolesUser` | `roles_user` | Asignación de roles a usuarios. |
| `Modules` | `modules` | Módulos del sistema (activo/inactivo). |

### Terceros (Master Data Global)

| Modelo | Tabla | Descripción |
|---|---|---|
| `Party` | `party` | Cliente o proveedor global. |
| `Contact` | `contact` | Contacto independiente reutilizable. |
| `Address` | `address` | Dirección independiente reutilizable. |
| `PartyContact` | `party_contact` | Relación N:M party ↔ contact con rol. |
| `PartyAddress` | `party_address` | Relación N:M party ↔ address con tipo. |
| `CompanyParty` | `company_party` | Activación del tercero en una compañía. |

### Inventario — Maestros Globales

| Modelo | Tabla | Descripción |
|---|---|---|
| `UOM` | `uom` | Unidades de medida globales. |
| `Item` | `item` | Ítem o servicio global. |
| `ItemUOMConversion` | `item_uom_conversion` | Conversiones de UOM por ítem. |

### Series e Identificadores

| Modelo | Tabla | Descripción |
|---|---|---|
| `NamingSeries` | `naming_series` | Formato lógico del identificador. |
| `Sequence` | `sequence` | Contador físico. |
| `SeriesSequenceMap` | `series_sequence_map` | Relación N:M series ↔ sequence. |
| `GeneratedIdentifierLog` | `generated_identifier_log` | Auditoría de identificadores generados. |
| `Serie` | `serie` | Serie simplificada (compatibilidad). |

### Contabilidad — Maestros por Compañía

| Modelo | Tabla | Descripción |
|---|---|---|
| `Accounts` | `accounts` | Catálogo de cuentas por entidad. |
| `Book` | `book` | Libro contable por entidad. |
| `FiscalYear` | `fiscal_year` | Año fiscal por entidad. |
| `AccountingPeriod` | `accounting_period` | Período contable. |
| `CostCenter` | `cost_center` | Centro de costos por entidad. |
| `Project` | `project` | Proyecto como dimensión analítica. |
| `DimensionType` | `dimension_type` | Tipo de dimensión analítica personalizada. |
| `DimensionValue` | `dimension_value` | Valores por tipo de dimensión. |
| `LedgerMappingRule` | `ledger_mapping_rule` | Reglas de diferencia entre libros. |
| `ItemAccount` | `item_account` | Mapeo de cuentas por ítem. |
| `PartyAccount` | `party_account` | Mapeo de cuentas por tercero. |
| `CompanyDefaultAccount` | `company_default_account` | Cuentas por defecto de la compañía. |
| `Tax` | `tax` | Definición de impuesto. |
| `TaxTemplate` | `tax_template` | Plantilla reutilizable de impuestos. |
| `TaxTemplateItem` | `tax_template_item` | Detalle de impuestos en plantilla. |
| `PriceList` | `price_list` | Lista de precios (buying/selling). |
| `ItemPrice` | `item_price` | Precio por ítem en lista. |

### Colaboración (modo Cloud)

| Modelo | Tabla | Descripción |
|---|---|---|
| `Comment` | `comment` | Comentarios en documentos. |
| `CommentMention` | `comment_mention` | Menciones en comentarios. |
| `Assignment` | `assignment` | Asignaciones de tareas. |
| `Workflow` | `workflow` | Definición de flujo de aprobación. |
| `WorkflowState` | `workflow_state` | Estados del flujo. |
| `WorkflowTransition` | `workflow_transition` | Transiciones permitidas. |
| `WorkflowInstance` | `workflow_instance` | Instancia activa de un workflow. |
| `WorkflowActionLog` | `workflow_action_log` | Historial de acciones del workflow. |
| `File` | `file` | Archivo subido al sistema. |
| `FileAttachment` | `file_attachment` | Adjunto vinculado a un documento vía reference pattern. |
| `AuditLog` | `audit_log` | Log de auditoría (before/after por campo). |

---

## Proceso de Setup Inicial (Wizard)

Flujo mínimo para dejar el sistema operativo:

```
1. Crear compañía (Entity)
   → moneda base
   → tipo de entidad

2. Crear catálogo de cuentas (Accounts)
   → jerarquía de cuentas
   → cuentas por defecto (CompanyDefaultAccount)

3. Crear libro contable (Book)
   → libro primario (is_primary=True)
   → moneda del libro

4. Crear año fiscal (FiscalYear)
   → fechas inicio/fin

5. Crear primer período (AccountingPeriod)

6. Crear usuario administrador
   → asignar roles

7. Definir series (NamingSeries + Sequence)
   → por tipo de documento
   → con prefijo de compañía

8. Configurar cuentas por defecto
   → AR, AP, bancos, descuentos, impuestos

9. Configurar cuentas y políticas de anticipos
   → anticipo de clientes (pasivo)
   → anticipo a proveedores (activo)
   → reglas de aplicación parcial/total
   → permisos de aprobación

10. Configurar impuestos y cargos
   → impuestos fijos y porcentuales
   → cargos aditivos y deductivos
   → cuentas contables por tipo de impuesto/cargo
   → políticas de capitalización de costos
   → reglas de prorrateo para cargos capitalizables
```

---

## Multi-compañía

- `Entity.code` es único globalmente.
- Toda tabla transaccional tiene `company` con FK a `entity.code`.
- El módulo Setup controla que los maestros se activen por compañía antes de usarse.
- `CompanyParty` activa un `Party` global para uso en una compañía específica.

---

## Seguridad y Roles (RBAC)

- `Roles` define los roles del sistema.
- `RolesAccess` define qué módulos puede acceder cada rol.
- `RolesUser` asigna roles a usuarios.
- Toda vista y acción debe verificar permisos mediante `RolesAccess`.
- La creación y aplicación de anticipos fuera de tolerancia debe requerir rol autorizado.

---

## Configuración funcional de anticipos

- Definir cuenta contable de anticipo de cliente por compañía.
- Definir cuenta contable de anticipo a proveedor por compañía.
- Definir políticas de aplicación:
   - total
   - parcial
   - múltiples facturas por anticipo
   - múltiples anticipos por factura
- Definir controles de aprobación para:
   - anticipos superiores a umbral
   - aplicación cruzada entre documentos
   - devoluciones de remanentes

---

## Configuración funcional de impuestos y cargos

- Definir plantillas de impuestos/cargos por tipo de documento (compras/ventas).
- Permitir líneas con:
   - tipo de cálculo: fijo o porcentaje,
   - comportamiento: aditivo o deductivo,
   - cuenta contable obligatoria.
- Definir por línea si el cargo en compras:
   - capitaliza costo, o
   - va a gasto directo.
- Definir regla de prorrateo por defecto para cargos capitalizables.
- Definir tolerancias y aprobaciones para cambios manuales en impuestos/cargos.

---

## Series e Identificadores

- Los identificadores son generados por el sistema.
- El formato se define con `NamingSeries` usando tokens:
  - `*YYYY*` — año del `posting_date`.
  - `*MM*` — mes del `posting_date`.
  - `*MMM*` — mes abreviado del `posting_date`.
- El contador físico vive en `Sequence` con soporte de reset anual o mensual.
- Todo identificador generado queda registrado en `GeneratedIdentifierLog`.
- Documentos que impactan ledger llevan prefijo de compañía obligatorio.

---

## Modos de ejecución

| Modo | Descripción |
|---|---|
| Desktop (Single User) | Todas las tablas activas. Colaboración deshabilitada a nivel aplicación. |
| Cloud (Multi User) | Comentarios, workflow, asignaciones y archivos habilitados. |

La distinción se controla desde `CacaoConfig` y la variable de entorno `CACAO_ENV`.

---

## Reportería requerida

| Reporte | Descripción |
|---|---|
| Usuarios activos | Lista de usuarios con roles asignados. |
| Módulos activos | Estado de habilitación por compañía. |
| Series configuradas | NamingSeries con secuencias asociadas. |
| Identificadores generados | Log de identificadores (auditoría). |
| Catálogo de cuentas | Con jerarquía, tipo y clasificación. |
| Libros contables | Libros activos por compañía. |
| Períodos contables | Con estado abierto/cerrado. |
