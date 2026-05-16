# Estado Actual del Proyecto - 2026-05-16

- **Merge Bancos remoto:** Integrada la rama `feat/banking-module-registers-16721791397278534001` con resolucion manual de conflictos, conservando funcionalidad existente en modulos no bancarios.
- **Bancos UX/Flujo:** Pagos, notas de debito/credito y transferencias internas ahora comparten formularios unificados con smart-select y payload JSON para captura rapida.
- **Compatibilidad de posting bancario:** Transferencias internas convierten cuentas bancarias origen/destino a cuentas GL (`paid_from_account_id`/`paid_to_account_id`) antes del posteo.
- **Documentos Operativos:** Detalles de Compras, Ventas e Inventario muestran moneda del registro, totales y lineas con codigo de moneda (`NIO 1,000.00`) y cantidades con 4 decimales (`10.0000`).
- **Comprobante Contable:** La moneda se muestra como codigo (`NIO`) y los importes `Debe`/`Haber` usan separador de miles con codigo de moneda (`NIO 1,000.00`) en tabla, panel y modal de detalle.
- **Comprobante Manual:** La leyenda `Comprobante manual` queda alineada bajo el numero del comprobante, igualando la cabecera de documentos operativos.
- **Validacion CI y Cobertura:** Workflow local equivalente en `venv` queda verde: build/twine, flake8, ruff, mypy, black, pytest completo con cobertura (`623 passed`, 83% total Python), `npm ci && npm test` (`21 passing`) y cobertura JavaScript con c8 (77% total).
- **Datos Demo de Terceros:** `Cliente Demo SA` y `Proveedor Demo SA` ahora se activan en `CompanyParty` para `cacao`, habilitando `smart-select` de clientes/proveedores filtrado por compania en Compras y Ventas.

- **Correccion UI Transaccional:** El modal compartido de detalle de linea inicializa sus `smart-select` solo cuando existe `modalLine`, conserva valores existentes y la secuencia se recarga automaticamente al cambiar compania.
- **Smart Select en Grids:** Los formularios transaccionales usan hidden inputs escalares como fuente de verdad; items filtran por compania y cargan descripcion, UOM predeterminada y UOMs permitidas.
- **Cabecera de Detalle:** Solicitud de Compra usa la misma estructura visual del comprobante manual: documento como titulo, tipo bajo el titulo, estado junto al numero, acciones a la derecha y datos dentro de la misma tarjeta.
- **Comprobante Manual:** El comprobante contable muestra `Comprobante manual` debajo del numero para mantener paridad visual con los documentos operativos.
- **Acciones en Borrador:** Solicitud de Compra en borrador muestra `Editar`, `Duplicar`, `Aprobar`, `Listado` y `Nuevo`; `Crear` permanece reservado para documentos aprobados.
- **Paridad Funcional Transaccional:** Compras, Ventas e Inventario incorporan rutas y acciones de `Editar` y `Duplicar` en documentos transaccionales, con edición restringida a borrador y duplicado disponible en borrador/aprobado.
- **Compras RFQ/SQ:** Se habilitaron rutas faltantes de `submit` y `cancel` para Solicitud de Cotización y Cotización de Proveedor; los botones del detalle ya no apuntan a endpoints inexistentes.
- **Actualizar Elementos:** Orden de Compra y Solicitud de Cotizacion pueden entrar desde Solicitud de Compra con origen precargado para traer lineas pendientes.
- **Framework Transaccional:** Estandarizado con soporte para `smart-select` en todos los niveles y layout uniforme.
- **Flujo Documental:** Soporta fusion de multiples fuentes con filtrado por Tercero y Compania.
- **Modulos Operativos:** Compras, Ventas e Inventario usan macros compartidas y ya tienen paridad de acciones en transaccionales; pendiente de consolidar cobertura y revisar casos limite en documentos maestros/no transaccionales.
- **Rutas de Inventario:** Renombradas a `inventory-issue` para mayor claridad semantica.
- **Pruebas:** Cobertura de mas de 600 tests unitarios/integracion y suite E2E Playwright basica para UI transaccional.
- **Verificación patch E2E/ULID:** Confirmado ajuste en `posting.py` para crear `StockBin` faltante y proteger `valuation_rate` con divisor `actual_qty > 0`. Se alinearon FKs de GL (`reversal_of`, `gl_entry_id`) a ULID de 26 caracteres y la suite de pruebas quedó en verde (`618 passed, 5 skipped`).
