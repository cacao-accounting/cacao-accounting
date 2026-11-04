# Instrucción para retomar la auditoría de Cacao Accounting

Retoma la auditoría integral del código productivo y ejecutable de Cacao Accounting. Continúa el trabajo existente; no lo reinicies ni descartes hallazgos o evidencia anterior. Esta instrucción sirve para una sesión futura cuando el usuario solicite reanudar. La auditoría quedó pausada por petición del usuario.

## Reconstrucción obligatoria del estado

1. Lee íntegramente `AGENTS.md` y respeta sus reglas. Consulta `SESSIONS.md` como contexto cuando ayude a interpretar decisiones anteriores.
2. Lee `AUDIT_PENDING.md`, que contiene la cola vigente, y los checkpoints pertinentes de `AUDIT_PROGRESS.md`, que conserva el historial, evidencia e issues. La tabla de pendientes tiene las columnas `Archivo`, `Funcion/Clase` y `estatus`.
3. Comprueba rama, HEAD y cambios locales con Git antes de actuar. La referencia al preparar este documento es:
   - Rama: `estabilizacion`.
   - Commit: `4ab661bbee531d43238b69fe2abd2bc33faab54b`.
   - Cambios locales de auditoría existentes: `AUDIT_PROGRESS.md` modificado y `AUDIT_PENDING.md` nuevo; este `AUDIT_PROMT.md` también es nuevo. Consérvalos.
4. Si la rama o el commit cambiaron, compara los archivos con la referencia y las huellas registradas. Invalida únicamente la cobertura afectada por cambios y sus dependencias; no reinicies toda la auditoría. No reviertas trabajo ajeno ni fuerces un cambio de rama que lo ponga en riesgo.
5. Reconcilia el inventario con los archivos reales. El manifiesto histórico contiene 577 filas para 557 rutas únicas, incluidas 20 filas repetidas. Deduplica por ruta y consulta los checkpoints más recientes y las huellas actuales para resolver discrepancias. No sumes las filas repetidas como archivos ni aceptes un hash antiguo como vigente.

## Estado de referencia y límites de la cobertura

Al preparar esta instrucción hay 557 rutas únicas: 45 completas y 512 sin cierre completo. Las pendientes se distribuyen en 294 parciales, 212 pendientes, 3 deltas por revalidar y 3 sujetas a criterio. Recalcula estos números desde el estado actual; son una referencia, no una meta ni prueba de cobertura.

La columna `Funcion/Clase` de `AUDIT_PENDING.md` mezcla descripciones heredadas de cobertura parcial e inventarios de símbolos extraídos automáticamente. No constituye una lista exhaustiva y verificada de símbolos pendientes. Algunas celdas describen lo ya revisado y lo restante; contrástalas con los checkpoints y el código. Leer un archivo, enumerar sus símbolos o comprobar su hash no acredita una auditoría funcional completa.

`AUDIT_PROGRESS.md` incluye notas históricas contradictorias, especialmente algunos bloques llamados “Batch”. Conserva su evidencia, pero no adoptes sus afirmaciones de cierre, pruebas o cambios de componente sin verificarlas. El último checkpoint reconciliado mantiene **Persistencia**, con el subflujo **StockEntry**, como componente activo.

## Punto de continuación

Continúa en Persistencia/StockEntry. Antes de repetir una revisión, busca su evidencia en la bitácora y verifica si el contenido sigue igual.

Archivos y dependencias relevantes que siguen parciales o requieren revalidación:

- `cacao_accounting/database/__init__.py`: modelos, constraints, listeners append-only y consumidores; el archivo completo aún no está cerrado.
- `cacao_accounting/contabilidad/posting_service.py`: posting y cancelación de StockEntry, SLE/SVL/FIFO, StockBin, atomicidad, idempotencia y contratos de libros/monedas; conserva estado de revalidación de delta.
- `cacao_accounting/contabilidad/cancellation_service.py`: política de fecha/período, actor, motivo, dependencias y transiciones.
- `cacao_accounting/inventario/services.py`, `inventario/service.py`, `inventario/routes.py` e `inventario/forms.py`: guardar, editar, publicar, duplicar, anular y validar compañía/bodega/UOM/lote/serie.
- `inventario/templates/inventario/entrada.html`, `entrada_lista.html`, `entrada_nuevo.html` y `stock_reconciliation_nuevo.html`, junto con `templates/macros.html`, `detail_view_macros.html`, `transaction_form_macros.html`, `static/js/transaction-form.js`, `document-flow-tree.js` y sus endpoints compartidos.

Siguiente trabajo concreto:

1. Completa los contratos pendientes de cancelación y reversa de StockEntry: idempotencia, tombstone monotónico de SLE, correspondencia exacta de capas, lote/serie, límites, aislamiento y atomicidad. Usa los checkpoints para evitar repetir las reproducciones ya acreditadas.
2. Valida el candidato de importes sin moneda en el listado. `entrada_lista.html` imprime `total_amount` sin moneda; el detalle sí usa el formateador con moneda. El patrón también aparece en listados de compras y ventas. Revisa alcance y causa compartida antes de reportarlo. #1427 trata una superficie similar en conciliación de compras; #1016 trata precios comerciales, por lo que no son automáticamente duplicados.
3. Hay una hipótesis adicional, todavía sin reproducción ni issue: `_validate_stock_reversal_capacity()` consulta StockBin sin lock; posteriormente `_upsert_stock_bin()` usa `FOR UPDATE` sin `populate_existing`. Investiga si una publicación concurrente puede dejar una lectura obsoleta entre validación y actualización. No la presentes como defecto confirmado; requiere evidencia con dos sesiones y un motor adecuado, particularmente PostgreSQL.
4. Termina las expresiones y dependencias frontend/backend restantes del subflujo. Después continúa los contratos de modelos/DDL/consumidores pendientes de `database/__init__.py`; no declares Persistencia cerrada ni avances a otro componente por haber terminado solo StockEntry. Consulta el orden previo antes de abordar `database/helpers.py`.

## Hallazgos que deben conservarse y deduplicarse

Consulta el estado y contenido actual de los issues antes de ampliarlos o abrir otro:

- #761: fecha y período de anulaciones/reversiones; el servidor admite fecha posterior en el mismo período, aunque la política exige la fecha original.
- #1728: ruta de cancelación ignora el resultado de la solicitud al ApprovalEngine.
- #1811: formulario de conciliación de inventario omite moneda exigida por el servicio.
- #1854: duplicación de StockEntry en Desktop omite evidencia de creación en AuditTrail.
- #1857: cancelación de conciliación con líneas repetidas depende del orden de movimientos al validar capacidad.
- #1858: reversas FIFO no preservan composición/asignación exacta de capas; incluye salidas multicapa y entradas idénticas repetidas.

Las reproducciones y relaciones históricas están en `AUDIT_PROGRESS.md` y los issues. No crees duplicados ni supongas que siguen abiertos o sin cambios sin comprobarlo.

## Alcance y método

Audita todo el código productivo y ejecutable, independientemente de extensión: Python, JavaScript, Alpine.js, Jinja2/HTML con lógica, scripts embebidos, SQL, migraciones y configuración que afecte comportamiento, seguridad o integridad. Excluye únicamente dependencias externas, archivos generados y recursos estáticos sin lógica funcional.

Agrupa por flujo de negocio y mantén un único componente principal activo. Sigue sus piezas de backend, frontend, plantillas y APIs en conjunto. Revisa cada función, clase, método, endpoint y expresión relevante; permisos del servidor, validaciones, transiciones, errores y casos límite. Examina concurrencia, atomicidad, idempotencia, anulaciones/reversiones, aislamiento entre compañías y coherencia multilibro/multimoneda. Evalúa estados Alpine, eventos, peticiones asíncronas, DOM, valores nulos y exposición de información en plantillas. El frontend nunca sustituye validaciones ni autorización del servidor.

Antes de abrir un issue, confirma el defecto, identifica resultado esperado y observado, aporta reproducción o evidencia técnica verificable con archivos/símbolos/líneas, impacto y severidad, busca duplicados y analiza causas compartidas. Mantén los candidatos no confirmados pendientes de validación. Usa los issues asociados como bitácora y el formato `Refs: #NNN` conforme a `AGENTS.md`.

## Restricciones y actualización del seguimiento

- Auditoría de solo lectura sobre producto. No implementes correcciones ni modifiques pruebas, workflows o reglas de negocio.
- Las modificaciones autorizadas son los documentos de seguimiento `AUDIT_PROGRESS.md` y `AUDIT_PENDING.md`; modifica esta instrucción solo si el usuario lo pide o autoriza. No hagas commits ni push sin autorización.
- Respeta el trabajo local de terceros. No borres, restaures ni sobrescribas cambios ajenos.
- No ejecutes la suite completa por rutina. Las comprobaciones deben ser necesarias para validar un hallazgo y ajustarse a las instrucciones vigentes; las sondas manuales anteriores usaron datos efímeros y no equivalen a una ejecución de tests.
- No delegues a subagentes por iniciativa propia; sigue las instrucciones vigentes de la sesión.
- Después de cada archivo, registra en `AUDIT_PROGRESS.md` los símbolos/expresiones revisados, contratos y dependencias comprobados, evidencia, hallazgos, límites y siguiente punto exacto. Distingue parcial, completo e invalidado por cambios posteriores.
- Mantén `AUDIT_PENDING.md` exclusivamente con lo aún no cerrado, en una tabla `Archivo | Funcion/Clase | estatus`. Actualiza las funciones realmente pendientes cuando exista evidencia suficiente y retira una fila solo al cerrar todo su alcance con evidencia en la bitácora.
- Recalcula el progreso por rutas únicas del inventario completo, no por archivos Python ni estimaciones. Conserva las huellas de referencia y señala los cambios posteriores a la última revisión.
- Al cerrar un componente, documenta archivos/superficies cubiertos, contratos, casos límite, riesgos, causas compartidas, issues y pendientes. Si queda cobertura requerida sin verificar, el componente permanece abierto.

Comienza comprobando el estado actual y continúa desde el primer punto no acreditado de Persistencia/StockEntry. No declares terminada la auditoría hasta que todo el inventario ejecutable tenga evidencia suficiente de revisión y todos los hallazgos estén documentados o vinculados.
