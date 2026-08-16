# Code Review — Logística y Landed Costs en Compras y Ventas

## Resumen

Implementación de metadatos logísticos (Incoterm, fecha/lugar de entrega,
términos) y snapshots de landed costs estimados a lo largo de la cadena de
documentos comerciales: RFQ → cotización de proveedor → orden de compra →
recepción → factura. El mismo patrón se extiende a ventas
(cotización → orden → entrega → factura) usando `sales_terms`.

La funcionalidad se implementó en dos commits:
1. **`4d03e8b`** — *feat: add logistics metadata to purchase and sales flows*
2. **`de967cf`** — *refactor: centralize logistics validation and catalog*

---

## Estado de calidad automatizada

| Herramienta        | Estado                              |
|--------------------|-------------------------------------|
| **Black**          | ✅ Todos los archivos Python limpios (HTML ignorado) |
| **Ruff**           | ✅ All checks passed                |
| **Mypy**           | ✅ Success — no issues found       |
| **Pytest**         | ✅ 8/8 pruebas pasan en 7.07s       |

---

## Nota sobre arquitectura de migraciones

**Descartado (no es problema):** El proyecto utiliza `create_all` para crear el
esquema de base de datos, y el baseline de alembic (`20260809_0001_baseline.py`)
es un no-op. Los archivos de migración incrementales históricos fueron
eliminados y **las nuevas columnas logísticas se definen directamente en los
modelos de `database/__init__.py`**, por lo que `create_all` las crea
correctamente. No existe un problema operativo con la ausencia de migraciones.

---

## 🟢 Mejoras del refactor (`de967cf`)

El commit de refactor aborda proactivamente problemas identificados en el
review original:

| Problema original | Resolución |
|---|---|
| Duplicación ~90% entre compras y ventas | ✅ **Nuevo módulo `cacao_accounting/logistics.py`** con `logistics_values()`, `copy_logistics()`, `validate_incoterm()`, `incoterm_options()` |
| Incoterms hardcoded en template | ✅ La macro `logistics_section()` ahora itera sobre `incoterm_options` poblado desde la BD |
| Sin validación de Incoterm | ✅ `validate_incoterm()` rechaza códigos inactivos y versiones ≠ 2020 |

---

## 🔴 BUG funcional crítico

### Macro `logistics_section` hardcodea `purchase_terms` para ventas

La macro `logistics_section()` en `transaction_form_macros.html` **siempre** usa
`name="purchase_terms"` y `x-model="header.purchase_terms"`, pero se comparte
entre templates de compras **y** ventas:

```jinja
{# Ventas — orden_venta_nuevo.html, cotizacion_nuevo.html, etc. #}
{{ tf_macros.logistics_section() }}

{# Compras — orden_compra_nuevo.html, etc. #}
{{ tf_macros.logistics_section(include_landed_costs=true) }}
```

Los modelos de ventas usan el campo `sales_terms`, **no** `purchase_terms`.

**Consecuencia:** El formulario de ventas envía `purchase_terms` (un campo que el
modelo `SalesOrder` ignora), pero **nunca envía `sales_terms`**. Los términos
comerciales introducidos por el usuario en órdenes, cotizaciones, entregas y
facturas de venta **se pierden silenciosamente**.

**Fix:** Parametrizar el nombre del campo en la macro:

```jinja
{% macro logistics_section(include_landed_costs=false, terms_field="purchase_terms") %}
  ...
  <textarea name="{{ terms_field }}" ... x-model="header.{{ terms_field }}">
  ...
{% endmacro %}
```

Y en templates de ventas:
```jinja
{{ tf_macros.logistics_section(terms_field="sales_terms") }}
```

---

## 🟡 Consideraciones de diseño

### `validate_incoterm()` requiere contexto de sesión activa

```python
def validate_incoterm(values: dict[str, Any]) -> None:
    code = values.get("incoterm_code")
    if not code:
        return
    ...
    active = database.session.execute(
        database.select(Incoterm.code).where(Incoterm.is_active.is_(True))
    ).all()
    allowed = {row[0] for row in active} if active else set(INCOTERM_CODES)
```

La validación ejecuta una query a la BD en tiempo real. Si se llama fuera de
contexto de sesión (por ejemplo en tests con `SimpleNamespace` o en scripts CLI),
el fallback a `INCOTERM_CODES` salva el caso, pero significa que:

- **En producción**, la validación requiere una sesión de BD activa, creando un
  acoplamiento fuerte entre la lógica de negocio y la capa de persistencia.
- **En tests**, el fallback oculta el comportamiento real.

**Recomendación:** Considerar pasar el set de Incoterms permitidos como parámetro,
o usar un manejador que permita inyección de dependencias.

### `terms_field` como keyword-only pero sin validación

```python
def copy_logistics(target: Any, source: Any = None, form: Any = None, *, terms_field: str) -> None:
```

El parámetro es keyword-only y requerido, pero no hay validación de que el valor
sea uno de los campos esperados (`purchase_terms`, `sales_terms`). Un valor
inválido propagaría silenciosamente a `logistics_values()`.

---

## 🟢 Lo que funciona bien

1. **Validación estricta de landed costs:** `_landed_cost_snapshot()` rechaza
   JSON no-lista, elementos sin `concept`, montos no-parseables como `Decimal`,
   y valores negativos.
2. **Propagación RFQ → cotización → orden:** `_copy_logistics()` preserva los
   datos a través de creación directa, adjudicación, duplicado y comparativo.
3. **Rechazo de cotizaciones con logística incompatible:** El servicio de
   comparativo valida firmas logísticas antes de crear órdenes múltiples.
4. **Alpine.js colapsado por defecto:** La sección logística está colapsada,
   manteniendo una interfaz limpia.
5. **Snapshot read-only en `orden_compra.html`:** La vista de lectura muestra
   los metadatos logísticos en un `<details>` colapsado.
6. **Landed costs separados del total comercial:** Los snapshots JSON no modifican
   el total ni generan contabilidad, como se documenta en `SESSIONS.md`.
7. **Incoterm como catálogo BD:** Modelo con `code` + `version` como PK compuesta,
   `is_active` indexado, versiones manejables.
8. **Cobertura de pruebas:** 8 pruebas cubriendo normalización, herencia,
   snapshot, validación de Incoterm, y propagación.

---

## Cobertura de pruebas

| Archivo | Pruebas | Cobertura |
|---|---|---|
| `tests/test_purchase_logistics.py` | 7 | ✅ Normalización, herencia, snapshot, validación |
| `tests/test_sales_logistics.py` | 1 | ✅ Herencia de logística en ventas |

**Falta cobertura:**
- Pruebas de integración para la propagación completa (RFQ → cotización → orden →
  recepción → factura).
- Pruebas para la validación de incompatibilidad en el comparativo de
  cotizaciones.
- Pruebas para el bug del campo `sales_terms` en templates de ventas (debido al
  bug descrito arriba, no hay cobertura de que los términos de venta se
  persisten correctamente).

---

## Tabla de resumen

| Severidad | Hallazgo |
|---|---|
| 🔴 Crítico | Macro `logistics_section` hardcodea `purchase_terms` → **ventas pierden términos comerciales** |
| 🟡 Medio | `validate_incoterm()` requiere sesión BD (acoplamiento persistencia-negocio) |
| 🟡 Medio | `terms_field` sin validación de valores permitidos |
| 🟢 Bajo | Falta cobertura de integración para propagación completa |

## Veredicto

La arquitectura de centralización logística en `cacao_accounting/logistics.py`
es una mejora arquitectónica sólida. Sin embargo, **existe un bug funcional
crítico** que afecta a **todos los documentos de ventas**: la macro compartida
no parametriza el nombre del campo `terms`, por lo que los términos comerciales
introducidos en órdenes, cotizaciones, entregas y facturas de venta se pierden
al guardarse en `purchase_terms` (campo que el modelo ignora) en lugar de
`sales_terms`.

**Recomendación:** No aprobar hasta corregir el bug de la macro parametrizando
el nombre del campo `terms_field`.
