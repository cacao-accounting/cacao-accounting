Estado 2026-05-12 (Finalizado): Todos los issues listados han sido resueltos y verificados.
- Se ha unificado el UX en todo el módulo contable siguiendo el "Voucher Pattern".
- Se implementaron las funcionalidades de Comprobantes Recurrentes y Asistente de Cierre Mensual.
- Se agregaron filtros de búsqueda en las vistas de listado del módulo contable.
- Se limpiaron los formularios de Cuentas y Centros de Costos (eliminando campos redundantes).
- Se implementó la edición para Cuentas y Unidades de Negocio.
- Se habilitó `smartSelect` para Cuentas Padre filtrado por entidad y clasificación.
- Se aseguró la creación automática de Centro de Costos "MAIN" al crear una entidad.
- Se corrigieron errores de linting (E501) que bloqueaban el CI.

Issues remanentes:
- Los módulos de Compras, Ventas y Bancos aún no cuentan con filtros de búsqueda en sus listas y algunos formularios no siguen el "Voucher Pattern" completamente.
- Las acciones "Crear desde..." en documentos operativos están implementadas en el backend pero no todas tienen botones visibles en la UI de detalle.
