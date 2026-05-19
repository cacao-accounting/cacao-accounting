# FIXME

## 2026-05-19 - Issues fiscales resueltos

- [x] `fiscal_preview_service.py`: el recálculo de preview fiscal vuelve a cargar reglas canónicas desde `TaxRule` cuando existen reglas persistidas, evitando que una respuesta previa incompleta reemplace metadatos como cascadas, conceptos incluidos/excluidos y orden original.
- [x] `transaction-form.js`: el auto-preview se omite para tipos documentales fuera de la matriz fiscal, evitando errores 400 en flujos como cotizaciones.
- [x] `fiscal_preview_service.py`: `payment_entry` con `payment_type="receive"` usa perfil de cobro (`applies_to="sales"`, `recognition_event="collection_confirmed"`).
- [x] `fiscal_persistence_service.py`: `account_id` vacío en líneas fiscales se normaliza a `NULL` antes de persistir el snapshot.

