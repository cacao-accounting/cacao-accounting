---
applyTo: "**/templates/**/*.html"
---
# Report Interface Rules

Use the financial report pattern for all reporting interfaces in the system.

## Layout Structure
- **Container:** Use `.ca-report-layout` (flex container).
- **Filter Sidebar:** Use `.ca-report-filters` (sticky, collapsible). Include Apply and Clear buttons at both top and bottom of the filter list.
- **Results Section:** Use `.ca-report-results` (flex: 1).
- **Sticky Headers:** Table headers and totals should be sticky.

## Filter Patterns
- **Smart Select:** Use `smartSelect` for all entity filters (Account, Party, Project, etc.).
- **Dependencies:** Implement dependent filters (e.g., Ledger/Period depends on Company) using `filterSources` and `requiredFilters`.
- **Advanced Filters:** Use a toggleable block (`.ca-report-advanced-filters`) for secondary filters. Persist the open/closed state in a hidden input named `advanced`.
- **Saved Views:** Provide a "Saved View" input with Cargar/Guardar/Eliminar actions.

## Data Display
- **Context Summary:** Display a brief summary of active filters (Company, Ledger, Period) above the results.
- **Tables:** Use `.ca-table.ca-report-table` within a scrollable wrapper (`.ca-report-table-wrapper`).
- **Grouping:** Support grouped rows with subtotals. Use `ca-group-row` class for hierarchical styling.
- **Tree Navigation:** Implement expand/collapse logic for hierarchical data (like Chart of Accounts) using `data-code` and `data-parent` attributes.
- **Drill-down:** Provide links to detail reports or source documents where appropriate.

## Actions & Exports
- **Exports:** Provide "Exportar Excel" (XLSX) and "Exportar CSV" links at the top of the results section.
- **Column Selection:** Use a modal for selecting visible columns if the report supports dynamic columns.

## UX Standards
- **Responsive:** Stack filters on top of results for small screens (using media queries).
- **Loading States:** Show clear loading indicators during filter application or view switching.
- **No Data:** Handle the empty state gracefully with a "No hay registros" message.
