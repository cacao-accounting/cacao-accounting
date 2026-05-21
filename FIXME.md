


cacao_accounting/contabilidad/budget_import_service.py
                                    "business_unit_id": unit_id, "project_id": project_id, "amount": amount,
                                    "description": row.get("Descripción")
                                })
                                existing_lines.add(comb)
@chatgpt-codex-connector
chatgpt-codex-connector Bot
43 minutes ago
P2 Badge Defer duplicate-key reservation until row validation passes

This adds the combination key to existing_lines before the row is confirmed valid. If a row has validation errors (for example, invalid project/unit) but includes amounts, its key is still reserved, and a later valid row with the same dimensions can be incorrectly rejected as Duplicado. Only reserve keys after confirming the row has no errors.


cacao_accounting/contabilidad/templates/contabilidad/presupuestos/real_vs_budget.html
Comment on lines +41 to +43
        {{ smart_select_field("Centro de Costos", "cost_center_id", "cost_center", filters.cost_center_id or '', "report-cost-center", 1, {"company": {"selector": "#report-company"}}, ["#report-company"], ["company"]) }}
        {{ smart_select_field("Unidad de Negocio", "business_unit_id", "unit", filters.business_unit_id or '', "report-unit", 1, {"company": {"selector": "#report-company"}}, ["#report-company"], ["company"]) }}
        {{ smart_select_field("Proyecto", "project_id", "project", filters.project_id or '', "report-project", 1, {"company": {"selector": "#report-company"}}, ["#report-company"], ["company"]) }}
@chatgpt-codex-connector
chatgpt-codex-connector Bot
43 minutes ago
P1 Badge Align dimension filter values with ID-based report filters

The dimension selectors are wired to doctypes that return codes (cost_center, unit, project), but the report service filters and joins treat submitted values as IDs (BudgetLine.*_id and mapped GL IDs). In practice, choosing any of these filters makes comparisons miss and can empty the report even when matching data exists. Use ID-valued selectors (or translate posted codes to IDs before filtering) so dimension filters work correctly.


Como PM: **no está listo para merge**.

El parche publicado en el diff actual todavía tiene bloqueantes:

1. **Importación no es atómica**: `insert_lines()` hace `commit()` dentro del ciclo, así que puede dejar líneas parcialmente insertadas si falla a mitad del archivo. ([GitHub][1])

2. **El flujo de staging está inconsistente**: existen modelos `BudgetImport` y `BudgetImportLine`, y el template espera `staged_lines`, pero el `BudgetImportService` del diff actual no usa staging; `validate_import()` devuelve `validated_rows, errors`. ([GitHub][1])

3. **El template usa `row.row_index`, pero `BudgetImportLine` no tiene `row_index`**. ([GitHub][1])

4. **Sigue sin verse migración de base de datos** para `budget`, `budget_line`, `budget_import` y `budget_import_line`. El diff solo agrega modelos. ([GitHub][1])

5. **El reporte mejoró visualmente**, porque ya muestra centro de costo, unidad de negocio y proyecto, pero el servicio aún debe validar de forma fuerte que el presupuesto seleccionado pertenece a la compañía, libro y año fiscal filtrados. ([GitHub][1])

Comparado con la versión pegada en el archivo, esta URL parece una versión distinta/menos cerrada del parche: el archivo cargado sí mostraba una implementación más avanzada con staging real en `BudgetImportService`, mientras que el diff actual de GitHub no refleja eso de forma consistente. 

**Decisión:** solicitar cambios.

Mensaje para el PR:

```text
No aprobar todavía. El parche aún tiene bloqueantes en importación: insert_lines() no es atómico, el flujo de staging está inconsistente con los modelos/templates, falta row_index o ajuste del template, y no se incluye migración de BD. Cuando el diff publicado refleje la versión con staging real, commit único/rollback, migración y prueba de rollback, queda listo para una última revisión.
```

[1]: https://patch-diff.githubusercontent.com/raw/williamjmorenor/dev/pull/92.diff "patch-diff.githubusercontent.com"




