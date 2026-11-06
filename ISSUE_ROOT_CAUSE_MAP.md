# Mapa provisional de issues abiertos por causa raíz
**Estado al 2026-11-06:** cotejado con `gh issue list --state open`: 1044 issues abiertos (24 root/1020 code); las relaciones causales siguen provisionales y la asignación integral no está validada.
**Fuente:** `ISSUE.md` contiene los mismos 1044 IDs abiertos, cotejados con GitHub el 2026-11-06; la agrupación causal en este mapa continúa parcial y requiere validar mecanismos.
**Uso:** proponer una agrupación solo cuando el mecanismo causal coincide; proximidad de módulo o síntoma no basta. `needs-review` conserva el criterio pendiente y no autoriza una solución.

## Índice de paraguas abiertos

La instantánea vigente tiene 24 issues clasificados `root` y 1020 `code` (1044 issues abiertos en total). Este índice enumera los paraguas y sus etiquetas actuales; no demuestra que todos los 1020 issues `code` estén asignados. La tabla de relaciones de abajo sigue siendo una muestra parcial por mecanismos ya revisados.

| Issue root | Descripción | Estatus |
|---|---|---|
| [#1719](https://github.com/cacao-accounting/cacao-accounting/issues/1719) | [ROOT CAUSE][DOCUMENT FLOW] Contrato del árbol documental: tipos de nodo, límites, búsqueda y cierre | needs-review |
| [#1718](https://github.com/cacao-accounting/cacao-accounting/issues/1718) | [ROOT CAUSE][IMPORTS] Paridad de validación y ciclo de vida de lotes de importación | needs-review |
| [#1717](https://github.com/cacao-accounting/cacao-accounting/issues/1717) | [ROOT CAUSE][VALIDACIÓN] Validación server-side de dominio en escrituras (formularios CRUD y enums) | needs-review |
| [#1716](https://github.com/cacao-accounting/cacao-accounting/issues/1716) | [ROOT CAUSE][TRANSVERSAL] Guard de vigencia: is_active verificado al usar, no solo al crear | needs-review |
| [#1715](https://github.com/cacao-accounting/cacao-accounting/issues/1715) | [ROOT CAUSE][INVENTARIO] Contrato de valoración: rebuild no destructivo, costos capitalizados y capas en fecha | needs-review |
| [#1714](https://github.com/cacao-accounting/cacao-accounting/issues/1714) | [ROOT CAUSE][AR/AP] Contrato canónico de open items: subtipo, línea, dirección y corte | needs-review |
| [#1713](https://github.com/cacao-accounting/cacao-accounting/issues/1713) | [ROOT CAUSE][TRANSVERSAL] Identidad de línea: DocumentRelation y consumo pendiente como única fuente de matching | needs-review |
| [#1712](https://github.com/cacao-accounting/cacao-accounting/issues/1712) | [ROOT CAUSE][FRONTEND] Invalidación de respuestas async: request-id/snapshot en todos los flujos | needs-review |
| [#1711](https://github.com/cacao-accounting/cacao-accounting/issues/1711) | [ROOT CAUSE][FRONTEND] Contratos de interfaz: i18n, Alpine, endpoints y CSRF | needs-review |
| [#1710](https://github.com/cacao-accounting/cacao-accounting/issues/1710) | [ROOT CAUSE][AUTH] Ciclo de vida de credenciales y mensajería: revocación, fail-safe e idempotencia | needs-review |
| [#1709](https://github.com/cacao-accounting/cacao-accounting/issues/1709) | [ROOT CAUSE][R2R] Contrato de cortes históricos: fecha efectiva as-of, reversas y saldo de apertura | needs-review |
| [#1708](https://github.com/cacao-accounting/cacao-accounting/issues/1708) | [ROOT CAUSE][TRANSVERSAL] Unificar máquina de estados documental: aprobaciones, anulaciones y transiciones | needs-review |
| [#1707](https://github.com/cacao-accounting/cacao-accounting/issues/1707) | [ROOT CAUSE][FISCAL] Contrato canónico del motor fiscal: una sola base para preview, persistencia y posteo | needs-review |
| [#1706](https://github.com/cacao-accounting/cacao-accounting/issues/1706) | [ROOT CAUSE][TRANSVERSAL] Extender garantías append-only e inmutabilidad a toda la evidencia | needs-review, fix-proposed |
| [#1658](https://github.com/cacao-accounting/cacao-accounting/issues/1658) | Consolidación causa-raíz: features a medias (integrar o retirar en una pasada) | needs-review |
| [#1657](https://github.com/cacao-accounting/cacao-accounting/issues/1657) | Consolidación causa-raíz: saldos derivados desincronizados en transiciones de documento | needs-review |
| [#1656](https://github.com/cacao-accounting/cacao-accounting/issues/1656) | Consolidación causa-raíz: invariantes del ciclo fiscal (año/período/cierre) | needs-review |
| [#1655](https://github.com/cacao-accounting/cacao-accounting/issues/1655) | Consolidación causa-raíz: resolver único de moneda y tasa histórica | needs-review |
| [#1654](https://github.com/cacao-accounting/cacao-accounting/issues/1654) | Consolidación causa-raíz: lecturas de saldo sin filtro de libro (multilibro) | needs-review |
| [#1653](https://github.com/cacao-accounting/cacao-accounting/issues/1653) | Consolidación causa-raíz: atomicidad/idempotencia en read-then-post | fix-proposed |
| [#1652](https://github.com/cacao-accounting/cacao-accounting/issues/1652) | Consolidación causa-raíz: contrato de lectura tabular en imports | needs-review |
| [#1651](https://github.com/cacao-accounting/cacao-accounting/issues/1651) | Consolidación causa-raíz: canonización de UOM y cantidad base entre flujos | needs-review |
| [#1650](https://github.com/cacao-accounting/cacao-accounting/issues/1650) | Consolidación causa-raíz: coerción de Decimals en la frontera de entrada | needs-review |
| [#1649](https://github.com/cacao-accounting/cacao-accounting/issues/1649) | Consolidación causa-raíz: alcance de compañía/ACL por endpoint y payload | needs-review |

## Persistencia / upgrades

| Issue hijo | Root candidato | Confianza | Mecanismo/nota |
|---|---:|---|---|
| #1898 | Sin root actual | — | Comparte con #1848 el guard de existencia de `User`, pero pide política de upgrade distinta; QA añadió que helper `batch_id` no instala FK y no revalida índice cuando la columna existe. No se asigna a root hasta acordar si los helpers/alteraciones son soporte legacy o migraciones operativas. |
| #1848 | Sin root confirmado | — | El marcador de usuario no demuestra que el seed haya terminado; el comentario reciente extiende el mecanismo a `server.py`/`__main__.py`. Comparte contexto de startup con #1898, pero bootstrap parcial y contrato de upgrades son causas distintas; no fusionar sin decisión. |

## Helpers de base de datos

| Issue/candidato | Root candidato | Confianza | Mecanismo/nota |
|---|---:|---|---|
| #1731 | Sin root confirmado | Alta en defecto | Repro PostgreSQL 16.15/psycopg2: `db_version()` ejecuta `sqlite_version()` y falla; la vista admin propaga el error. Comentario agregado al issue. No encaja en los roots actuales sin forzar una agrupación. |
| `generate_identifier()` / `get_next_sequence_value()` | #1653 candidato | Media-alta en stale identity map | Repro PostgreSQL 16: una sesión cargó `Sequence.current_value=0`, otra conexión confirmó 5, y `SELECT FOR UPDATE` en la sesión vieja retornó/persistió 1. Falta reproducir dos requests completos y efecto en índice/posting; sin issue hijo nuevo. |
| #1922 | #1717 candidato; sin root confirmado | `needs-review` | Reset mensual con prefijo sin token de mes reinicia contador y repite identificador; colisión unique reproducida en SQLite. La política debe definirse antes de confirmar raíz. |

## Datos maestros / terceros / UOM

| Issue hijo | Root candidato | Confianza | Mecanismo/nota |
|---|---:|---|---|
| #1724 | #1717 | Media | Cambiar tipo de PartyGroup puede dejar asignaciones de Party incompatibles; el tratamiento de asociaciones existentes requiere decisión. |
| #1725 | Sin root actual | — | Formulario de cliente y upsert tratan una fila `CompanyParty` compartida entre roles como si fuera configuración exclusiva de cliente. |
| #1926 | #1649 candidato | `needs-review` | Usuario sin permiso de consulta alcanza listado/detalle UOM global; definir si el catálogo requiere permiso de Inventario o queda visible a usuarios autenticados. |
| #1927 | #1716 candidato | `needs-review` | UOM inactiva sigue visible en `_uom_choices()` para alta/edición de artículos; definir disponibilidad histórica y en nuevos usos. |
| #1741 | #1717 | Alta | `Item.standard_rate` negativa pasa CRUD y genera precio que la línea de ventas rechaza por constraint. |
| #1747 | #1711 | Alta | Selectores Jinja/Alpine de UOM envían códigos que WTForms no acepta porque las choices server-side quedan vacías. |
| #1034 | #1651 | Alta | Conversión directa de UOM omite validar factor positivo; issue ya agrupa ambos sentidos bajo canonización UOM. |
| #1902 | #1651 | Alta | La inicialización de edición sustituye una UOM comercial válida por la base sin convertir qty; la persistencia vuelve a calcular cantidad base con la UOM sustituida. |

## Evidencia append-only / inmutabilidad

| Issue hijo | Root candidato | Confianza | Mecanismo/nota |
|---|---:|---|---|
| #925 | #1706 | Alta | QA confirmó con sonda SQLite que cancelar SLE funciona y los intentos de reactivarla vía ORM y Core son rechazados; falta prueba permanente de esa transición monotónica. La cobertura existente prueba GLEntry, no SLE; issue documenta `is_cancelled=0`. Comentario: https://github.com/cacao-accounting/cacao-accounting/issues/925#issuecomment-6660152892. |
| `ExternalCounterAuditLog` | #1706 candidato | Media | `adjust_external_counter()` inserta el before/after/motivo, pero la tabla no pertenece a listas guardadas ORM/Core/SQL y no tiene listeners; extensión estática comentada en [#1706](https://github.com/cacao-accounting/cacao-accounting/issues/1706#issuecomment-6651376369), sin repro de mutación. #759 es issue hijo append-only, no raíz alternativa. |

## Manejo de errores de formularios

| Issue hijo | Root candidato | Confianza | Mecanismo/nota |
|---|---:|---|---|
| #1884, #1901 | Sin root confirmado | Media | Ambos handlers reconstruyen la edición desde datos persistidos tras rechazo y descartan el POST; mismo resultado de pérdida de corrección, pero falta auditar otros módulos y decidir si corresponde raíz nueva o un paraguas existente. |

## Impresión y navegación segura

| Issue | Root | Confianza | Mecanismo/nota |
|---|---|---|---|
| #1923 | Sin root actual | Alta | `_safe_return_url()` admite path con backslash inicial `/\\evil.example/path`; `build_print_html()` lo escapa como atributo, pero el parser URL WHATWG lo resuelve a origen externo. Issue de open redirect, distinto de CSS no seguro (#1563) y CSRF admin (#1761). |
| #1925 | Sin root actual | Alta | Tipo de documento de impresión no registrado causa HTTP 500: servicio lanza `ValueError`, ruta captura solo `PrintingError`; `PrintableDocumentNotRegisteredError` está declarado pero no tiene caller, posible integración. |
| #1928 | #1711 | Alta | Tres templates Jinja usan `block content`, pero base declara `contenido`; endpoints 200 no renderizan contenido propio. |
| #1929 | #1717 | Alta | Duplicado de plantilla genera código fijo `source_copy`; segundo POST colisiona unique y devuelve 500 sin manejar `IntegrityError`. |
| #1932 | #1711 | Alta | Etiquetas/status/document_type y errores visibles de printing se presentan raw/sin gettext. |

## Configuración y valores booleanos

| Issue | Root | Confianza | Mecanismo/nota |
|---|---|---|---|
| #1924 | Sin root actual | Alta | `CACAO_TEST=false`/`CI=false` se interpretan truthy y activan modo test; `SQLALCHEMY_TRACK_MODIFICATIONS='False'` también activa tracking ORM por tipo string. Causa común: usar cadenas de falso como booleanos efectivos. Sin paraguas existente que cubra estos consumidores/configuración; ambos síntomas en #1924, TLS permanece candidato sin contrato. |
| #1930 | #1658 candidato | `needs-review` | `paper_size/orientation` se guardan pero no se leen al renderizar PDF; decidir si se integra su efecto o se retiran las opciones. |
| #1931 | #1658 candidato | `needs-review` | Ruta consulta versiones pero no tiene link y template no renderiza `versions`; decidir integrar historial o retirar interfaz/código. |

## Interfaz / código sin consumidor

| Issue hijo | Root candidato | Confianza | Mecanismo/nota |
|---|---:|---|---|
| #1899 | #1658 | Alta | Tres hojas CSS legacy sin carga ni consumidores en plantillas; limpieza concreta bajo el paraguas de código sin consumidor. |
| #1916 | #1658 primario; #1706 secundario | Alta para ausencia de consumidor; inmutabilidad pendiente | Las cinco clases Workflow aparecen solo como declaraciones: no se hallaron CRUD, seed, reader, writer ni pruebas locales. La macro `workflow_buttons` activa trabaja con endpoints/docstatus y no usa estas tablas. #1916 needs-review pide decidir integrar o retirar preservando datos y migración; WorkflowActionLog declara inmutabilidad, pero tiene cascades y carece de guard. #1658 es candidato primario; #1706 secundario para la promesa append-only.
| #1938 | #1658 candidato | Alta para ausencia de persistencia/UI; decisión de alcance pendiente | Stubs de saved-view en `reportes/helpers.py`, sin callers directos para filtros/form-key y sin UI/persistencia/restauración; QA independiente confirma que solo hay selección textual `default`/query string. Decidir integrar o retirar.
| #1940 | #1658 candidato | Alta para ausencia de caller local; contrato externo pendiente | Dos WTForms sin campos y un `FormularioSecuencia` sin consumidor; la UI usa `FormularioNamingSeries`. No borrar antes de comprobar imports externos.
| #1941 | #1717 primario; #1656 secundario | Alta | Alta/edición persiste `AccountingPeriod` con `start > end`; ninguna fecha satisface el resolver y el período queda inutilizable. QA HTTP/SQLite independiente; #1155 es solo solapamiento entre rangos válidos.
| #1939 | #1711 candidato | Alta | Drilldown no propaga `period_from/period_to` cuando el padre es multi-período; QA Flask/SQLite confirma que el destino selecciona el rango actual predeterminado. #1709 trata otra causa (as-of/reversas).
| #1921 | #1711 | Alta | GET autenticado HTTP 200 renderiza formulario POST, pero no hay control submit; `@submit` solo prepara payload. QA independiente confirmó que todos los botones son enlace o `type=button`; la interfaz no permite guardar plantilla recurrente. |
| `cacao_accounting/api/templates/empy.html` | #1658 candidato | Media | Archivo 0 bytes y sin caller local; Blueprint declara template folder y MANIFEST lo distribuye. Falta contrato externo, no retirar automáticamente. Comentado en [#1658](https://github.com/cacao-accounting/cacao-accounting/issues/1658#issuecomment-6652496335). |

## Cache / invalidación de datos maestros

| Issue hijo | Root candidato | Confianza | Mecanismo/nota |
|---|---:|---|---|
| #1900 | Sin root actual | — | Import adapters confirman alta de terceros sin invalidar la generación del Smart Select; el resultado cacheado dura hasta el TTL. No asignar a #1679: indisponibilidad Redis en tokens es otro mecanismo. |

## Candidatos de código sin consumidor / atomicidad

| Candidato | Root candidato | Confianza | Mecanismo/nota |
|---|---:|---|---|
| `Warehouse.parent_warehouse`, `Warehouse.is_group` | #1658 | Media | Solo aparecen en declaración de modelo; search estático no halló callers. Criterio sobre eliminación de datos legacy pendiente. |
| `obtener_id_usuario_por_nombre()` | #1658 (candidato) | Media | Sin caller productivo local en HEAD `85eed67b`; retorna `str | None` pero `.id` sobre None si el nombre solicitado no existe. No confirma dead code: falta contrato de consumidores externos. Comentado en [#1658](https://github.com/cacao-accounting/cacao-accounting/issues/1658#issuecomment-6652213544). |
| `rebuild_stock_bins()` | #1658 | Media | Búsqueda no halló caller productivo externo; la función recompone bins y luego invoca `rebuild_stock_valuation_layers()`. Queda como helper sin ruta/CLI encontrada. |
| `_upsert_stock_bin(valuation_rate=...)` | #1658 | Alta | El helper no lee el argumento; calcula la tasa desde el valor y cantidad resultantes o fija cero. Los callers usan su propia tasa para SVL/SLE, sin efecto incorrecto confirmado fuera del parámetro muerto. |
| `ERROR1`, `ERROR3`, `ERROR4` en `exceptions/mensajes.py` | #1658 | Alta | Las tres constantes no tienen consumidores productivos ni tests; `ERROR2` sí se usa cuatro veces y permanece fuera del hallazgo. Comentado en #1658; decidir retirar las constantes huérfanas en la pasada coordinada de código sin consumidor. |
| `generate_identifier()` / `get_next_sequence_value()` | #1653 candidato | Media-alta en stale identity map | Repro PostgreSQL 16: sesión cargó `current_value=0`, conexión externa confirmó 5 y el `SELECT FOR UPDATE` en la sesión vieja retornó/persistió 1. Falta flujo de dos requests y demostrar impacto final en emisión/posting; no duplicar #1004/#1293/#1577, que son reset/backdate bajo #1656. |
| `create_document_relation()` / `save_relation()` | #1653 (candidato) | Media | Lee capacidad y `max(revision)` antes de insertar, sin serializar la línea fuente. El índice parcial de relación activa solo existe en SQLite/PostgreSQL y no limita consumo agregado. QA confirmó el patrón estático; sin reproducción concurrente. Comentado en el root, no issue hijo. |
| `create_purchase_quotation_award()` | #1653 (candidato) | Media | La ruta lee RFQ sin lock; chequea ausencia de award `finalized/used` y luego inserta, sin unique por RFQ/estado. Backend y QA confirman la ventana estática; falta repro concurrente PostgreSQL. Comentado en #1653, no issue hijo. |

## Valuación por lote / costos capitalizados (candidato)

| Candidato | Root candidato | Confianza | Mecanismo/nota |
|---|---:|---|---|
| Capa landed `qty=0` sin lote | #1715 | Media | `_create_valuation_layer_if_needed()` crea la capa sin `batch_id`; `_filter_batch_valuation_layers()` descarta capas qty cero y sin vínculo origen. La queue global sí incluye el ajuste. Sin reproducción runtime y sin criterio de asignación del landed cost a lotes; documentado en comentario actual del root, no issue hijo. |

## ImportLandedCost revisado (parcial)

| Hallazgo | Root candidato | Confianza | Mecanismo/nota |
|---|---:|---|---|
| #1903 | #1711 | Alta | Controles `company` y `posting_date` duplicados entre macro y formulario; el server lee la primera ocurrencia. Root provisional, revisar causa común antes de implementar. |
| #758 — moneda en landed cost | #1655 primario; #1711 candidato secundario solo para selector UI | Media | El contrato de moneda origen/destino pertenece a moneda/tasas (#1655); el subhallazgo de selector no consumido puede tocar interfaz (#1711), sin convertir #758 en root. Confirmar el contrato de moneda del landed cost antes de ampliar causas. |
| Bodega requerida no capturable | #1717 / #1711 | Media | Config y JS omiten `warehouse`, el writer guarda vacío y posting rechaza asignación capitalizable; decidir criterio de selección/herencia. |
| #1942 — moneda ausente en comparativos S2P | #1711 primario; #1655 secundario para base funcional | Media | Tres vistas S2P imprimen tarifas/importes/totales sin moneda; la solicitud se ordena por moneda funcional mientras expone tarifa nominal. Needs-review: acordar si mostrar importe transaccional, funcional y tasa/fecha. #1869 excluye comparativos. |
| #2015 — moneda ausente en comparación de pronósticos CTM | #1711 primario candidato; #1655 secundario candidato | Alta | `get_cash_forecast_matrix()` entrega saldos en moneda funcional, pero el template invoca el helper sin código; HTTP NIO mostró `800.00` sin `NIO`. Es una superficie paralela a #1942; confirmar en pase causal. |

## AR/AP / pagos revisados (parcial)

| Issue hijo | Root candidato | Confianza | Mecanismo/nota |
|---|---:|---|---|
| #1070, #1305, #1103 | #1657 | Alta | Reversar apertura y asignaciones actualiza mal el mismo cache `ARAPOpenItem`; la lectura cacheada presenta saldos de documentos cancelados. QA confirmó el mecanismo; existe hijo exacto. |
| #1207 | #1657 primario; #1714 secundario candidato | Alta en mecanismo actual | Confirmación de saldo vuelve a mostrar notas de crédito aplicadas por cálculo del saldo derivado. El body del issue referencia #1657; el cálculo de open item también roza #1714, sin reasignar a esa raíz. Agente reprodujo en `balance_confirmation.py`. |
| #1140 | #1714 | Media | Dos pagos en borrador reservan el mismo saldo y el segundo puede postear sin revalidar. Root candidato por contrato de saldo canónico; el resultado (rechazo o anticipo) sigue `needs-review`. |
| #1145 | #1653 | Alta | Payment callers bloquean la factura, pero `post_journal_ar_ap()` lee `ARAPOpenItem` sin lock; el helper luego satura cache sin revalidar. QA confirma la ruta de journal vs journal/pago; validar runtime SQLite aparte. |
| #1144 | #1653 | Alta | `AllocationPlanner` admite claves de idempotencia repetidas dentro del mismo plan, pero `AllocationExecutor` persiste solo una; total planeado difiere de saldo y persistencia. La ruta de test citada por el issue no está en el checkout actual. |
| #1545 | #1714 | Alta | Las aplicaciones posteriores valoran factura y pago a tasa de fecha de aplicación, en lugar de tasas históricas; política de diferencia cambiaria pendiente (`needs-review`). |
| #1585 | #1714 | Alta | El aging incluye devoluciones en el subledger pero descarta saldos firmados `<= 0`, por lo que omite créditos abiertos; la política de presentación de créditos en buckets sigue `needs-review`. |
| `documents.get_details` (candidato) | #1714 | Media | Serializa `document.outstanding_amount` cacheado mientras otros lectores calculan con el open-item canónico. No se reprodujo desincronización; comentado en #1714 para cotejar el contrato sin issue hijo. |

## Consulta de configuración / alcance de compañía (parcial)

| Hallazgo | Root candidato | Confianza | Mecanismo/nota |
|---|---:|---|---|
| `admin.configuration.list` puede devolver `budget_control_*` de otras compañías | #1649 | Media | Valida acceso al `company_id`, pero consulta claves `CacaoConfig` globales. Las claves son compañía-específicas (`budget_control_enabled_{company}`, `budget_control_action_{company}`); requiere confirmar contrato de admin limitado a una compañía. Comentado en el root `needs-review`; no issue hijo. |

## CTM / multilibro / moneda en query tools (parcial)

| Issue/hallazgo | Root candidato | Confianza | Mecanismo/nota |
|---|---:|---|---|
| #1251 | #1655 | Alta | El saldo GL suma moneda base del libro y lo etiqueta `BankAccount.currency`; el mismo mecanismo aparece en `query_tools/handlers/banking.py::get_banking_accounts`, comentado en #1251. |
| #1025 | #1654 | Alta | `_get_gl_balances()` omite el predicado si `primary_ledger_id()` devuelve None y agrega todos los libros; ya es el caller explícito del issue. |
| `max_date_range_months` sin validador | #1658 candidato | Media | Metadata de límite (12 meses) guardado en `QueryTool` pero no leído/publicado/aplicado internamente. QA confirma; ownership de validación del plugin externo sin definir, comentado en root `needs-review`, sin issue hijo. |

## R2R / query tools (parcial)

| Issue/hallazgo | Root candidato | Confianza | Mecanismo/nota |
|---|---:|---|---|
| #1341 | #1709 | Alta | `get_trial_balance` devuelve movimientos de rango sin apertura/cierre; misma causa que el reporte canónico de corte histórico. |
| #1582 | #1709 | Alta | Los cálculos de KPI/tendencias filtran reversas activas con `is_reversal=False`; query tools usa el mismo helper, comentado en #1582. |
| #1499, #1086 | #1709 | Alta | Los saldos y el flujo real de cash forecast excluyen reversas/cancelaciones; la query tool consume el mismo servicio, por lo que oculta el efecto contable de esos movimientos. |
| `ordinary_gl_scope()` excluye toda reversa y filtra originales por estado cancelado actual | #1709 / #1168 | Alta, probe FX real | `ExchangeRevaluationService.run(2026-10)` + `void(2026-11-01)` creó originales de octubre cancelados y dos reversas activas en noviembre. Detalle GL ordinario devolvió cero filas y P&L income=0, frente a 2 líneas/income=-60 al incluir; comportamiento comentado en #1168 y root #1709. Causa técnica confirmada; conservar `needs-review` en la política as-of/fecha efectiva y no abrir duplicado.
| #1130 | #1649 | Alta | `get_kpi_snapshot` puede resolver un libro por ID sin validar que pertenezca a la compañía solicitada; hijo ya agrupado bajo ACL/scope por compañía. |

## Query tools operacionales y calendario de tesorería (parcial)

| Issue/hallazgo | Root candidato | Confianza | Mecanismo/nota |
|---|---:|---|---|
| #1257, #1084 | Sin root confirmado | — | La comparación de forecast empareja periodos por nombre sin verificar calendario/periodicidad compatibles; ambos issues ya describen el contrato. |
| #1234 | Sin root confirmado | — | El maturity schedule elige `due_date` o `posting_date`; no deriva vencimiento de los términos de pago. Dedupe directo, falta auditar productor/criterio transversal. |
| #1085 | Sin root confirmado | — | Fallback de saldo legacy y tabla `document_relation` ocultada ya están descritos en el issue; esta pasada confirma el caller del maturity schedule. |
| #1126 | Sin root confirmado | — | `get_unapplied_payments` incluye pagos draft con saldo disponible; la visibilidad esperada de draft requiere criterio. Dedupe exacto, no issue hijo nuevo. |
| N+1 de `get_unapplied_payments` y `get_maturity_schedule` (candidato) | Sin root confirmado | Media | Ambos handlers cargan documentos y calculan saldos antes de paginar. No hay medición ni issue exacto; confirmar volumen/contrato antes de promover. |

## Query tools: límites para clasificación de código sin consumidor

`query_tools` es una API pública para plugins externos y está excluida como categoría de dead code en #1841. `COMPANIES_LIST_PARAMS/RESPONSE` y esquemas CxP/CxC no tienen referencias Python locales, pero no se clasifican aquí como muertos sin resolver el alcance público de esos módulos/esquemas. Los handlers sí tienen contratos y se auditan por funcionalidad.

| Issue | Root candidato | Confianza | Mecanismo/nota |
|---|---:|---|---|
| #1905 | Sin root actual | — | `server()` consume el `OSError` de Waitress y retorna éxito aparente; `cacaoctl serve` no puede propagar el fallo ni salir con estado no cero. Hallazgo estático, runtime/exit-code pendiente. |
| #1904 | #1717 candidato | Media | `PaginatedResult` está exportado públicamente y acepta `page_size=0`; `total_pages` divide por cero. Repro directa confirmó `ZeroDivisionError`; handlers internos usan `paginate()`, pero la clase pública no protege la construcción directa. Causa propuesta: validación de invariantes en la frontera de objeto público; asignación al paraguas aún provisional. |
| #1581 | #1658 candidato | Media | Cuatro handlers built-in requieren módulos `audit`/`documents` que no existen en `MODULOS_STANDAR`; una sonda reprodujo `MODULE_DISABLED` para `audit.get_user_activity_summary`. Los handlers están registrados: es un defecto de gate/registro de feature, no evidencia de dead code. El paraguas se considera candidato porque el módulo nunca queda integrado en la instalación estándar; comprobar si hay root más preciso antes de confirmar. |

## Inventario / StockEntry revisado

| Issue hijo | Root candidato | Confianza | Mecanismo/nota |
|---|---:|---|---|
| #1896 | #1711 | Media | Jinja/Alpine configura `initialHeader` incompleto; campos requeridos vacíos o valores de cabecera eliminados al guardar. El issue está abierto `needs-work`. |
| #1895 | #1713 | Baja | Payload de reuso pierde tracking por línea; la política de lote/serie requiere decisión `needs-review`. #1713 cubre identidad/relaciones de línea, no todo el ciclo Batch/Serial. |
| #1894 | #1713 | Alta | La precarga omite destino de flujo y no calcula saldo pendiente por línea. |
| #1893 | #1713 | Alta | Duplicación pierde `DocumentRelation` de origen y su límite de capacidad. Criterio de duplicación independiente/relacionada pendiente (`needs-review`). |
| #1892 | #1717 | Alta | Falta validar servidor la bodega requerida por propósito antes del posting. |
| #1891 | Sin root actual | — | Propósitos genérico/positivo/negativo duplicados; requiere criterio funcional antes de definir solución. No asignar a #1658 solo por ser auditoría. |
| #1890 | #1649 | Alta | Unit/Project de otra compañía aceptados desde payload; QA y backend confirman extensión a `cost_center_code` de otra compañía en alta/edición, cuya validación solo corre en conciliación. Comentado en #1890; requiere validar vía HTTP. |
| #1889 | #1711; secundario #1713 | Media | Vista no presenta destino/trazabilidad por línea; separar visibilidad de la integridad de relaciones. |
| #1888 | #1711 | Media | Controles visibles de línea no coinciden con los valores persistidos por el POST. |
| #1887 | #1711 | Alta | Selector de cuentas no actualiza su estado al cambiar compañía. |
| #1881 | #1653 | Media | Posible concurrencia de valuación al primer movimiento; confirmar bloqueo/serialización antes de asignar. |
| #1879 | #1655 | Alta | Descuadre de conversión de moneda en ajustes de solo valor; el issue ya referencia el resolver. |
| #1878 | #1715 | Baja | Límite de valor por lote requiere criterio antes de vincular con contrato de valuación. |
| #1877 | #1706 (candidato) | Media | El guard de evidencia en Cloud bloquea la conciliación de inventario; coincide con la superficie del root, aunque el hijo trata el rechazo de una transición interna permitida. Revalidar junto con el contrato de mutación derivada antes de ratificar. |
| #1876 | #1715 | Media | Reversa de cantidad por lote y contrato de valuación; revisar límite exacto común. |
| #1875 | #1711 | Alta | Código interno de propósito expuesto sin traducción. |
| #1874 | #1711 | Alta | Flujo source deja compañía/moneda vacías y bloqueadas por configuración incompleta de formulario. |
| #1873 | #1655 | Media | Ajuste de valor cero omite GL con cantidad registrada; relacionado con moneda/valor, no duplicado. |
| #1871 | #1711 | Media | Parser de filas y modelo de filas del formulario divergen tras hueco. |
| #1908 | #1711 (candidato) | Baja | Mensajes de fallo se muestran con estilo success: curl confirmó login y el flash de correo duplicado en `profile.html` (`6680316384`). |
| #1909 | #1658 (candidato) | Baja | `SetupConfirmationForm` y hidden `step` no tienen consumidor en el wizard actual; revisar y retirar residuos sin cambiar el flujo de sesión. |
| #1907 | #1711 (candidato) | Baja | La tabla de permisos de roles renderiza etiquetas de acciones hardcodeadas en español en la interfaz en inglés; revisión estática confirmada, falta render HTTP/browser. |
| #1911 | #1711 (candidato) | Baja | Tablas tributarias muestran enums y códigos internos sin etiquetas localizadas. |
| #1910 | Sin root de producto | — | Reproducción PostgreSQL confirma que fixture crea DB aislada pero `str(URL)` redacta password antes de `create_app()`, falla 28P01 durante `create_all`; raíz de test harness independiente, enlazado a #1653 solo para informar que bloquea su verificación dinámica. |
| #1870 | #1711 | Alta | Título visible de shortcut no usa el contrato i18n. |
| #1868 | #1653 | Alta | Carrera concurrente sobre StockBin ya ligada a raíz de atomicidad. |
| #1306, #1178 | #1653 | Alta | La lectura de `SerialNumber` valida `available` antes del lock de cantidad de `StockBin`; no hay revalidación serial al aplicar el movimiento. Ambos issues describen la misma carrera TOCTOU y ya apuntan al paraguas en comentarios. |
| #1867 | #1711 candidato | Media | XSS reflejado por dato interpolado en expresión JavaScript/Alpine; #1985 reproduce el mismo mecanismo de contexto en Caja Chica, con otra fuente/alcance. Confirmar si #1711 agrupa correctamente la serialización contextual; no asumir stored ni XSS cross-user. |
| #1985 | #1711 candidato; relacionado con #1867 | Media | `custodian_id` inválido se refleja en `x-data` tras error de POST; QA ejecutó la expresión después de decodificar atributo HTML. Alcance reflejado en sesión autenticada; root candidata, no confirmada. |
| #1865 | #1706; secundario #1713 | Alta | Edición intenta borrar evidencia inmutable; también omite identidad de línea origen al reconstruir. `needs-review`. |
| #1864 | #1717 | Alta | Validación decimal de payload en writer. |
| #1863 | Sin root actual | — | Snapshot de auditoría no incluye toda la cabecera modificada; distinto de inmutabilidad de evidencia. |
| #1862 | #1712 | Alta | Respuesta asíncrona obsoleta puede reemplazar snapshot actual. |
| #1861 | #1711; secundario #1655 | Media | Listado presenta valor sin moneda; la tasa no es la causa del formato omitido. |
| #1858 | #1715 | Alta | Cálculo FIFO/capas al cancelar inventario. |
| #1857 | Sin root exacto | — | Resultado depende del orden de movimientos al revertir; #1715/#1708 no capturan todavía el mecanismo con precisión. |
| #1854 | Sin root actual | — | Falta evento de creación en bitácora Desktop; no equivale a mutar/borrar evidencia (#1706). |
| #1850 | #1711 | Alta | Selector transmite identificador con contrato diferente al esperado. |
| #1847 | #1651 | Alta | Cantidad base/UOM divergente entre flujos. |
| #1838 | #1711 | Alta | Cadenas visibles sin gettext o traducción. |
| #1835, #1834 | #1711 | Media | Observaciones de conciliación no se conservan; verificar deduplicación entre ambos antes de vincular. |
| #1829 | #1717 | Media | Unicidad/ownership de serial validado tarde o incompletamente. |
| #1827 | Sin root exacto | — | Selección de cuenta depende de bodega origen/destino; #1717 sería demasiado genérico sin confirmar que la raíz sea validación de dominio. |
| #1826 | #1717 | Alta | Allowlist de tipos de cuenta contradice el catálogo válido. |
| #1825 | #1711 | Media | Formulario de artículo omite persistir cuenta; confirmar el contrato de datos concreto. |
| #1811 | #1711; secundario #1655 | Alta | Formulario de conciliación omite moneda requerida; interfaz y regla multimoneda interactúan. |
| #1810 | #1711 | Media | Contrato de vista/modelo roto (`item_name` ausente); no asumir que toda excepción de plantilla comparte raíz. |

## Aprobaciones y cancelaciones StockEntry revisadas

| Issue hijo | Root candidato | Confianza | Mecanismo/nota |
|---|---:|---|---|
| #1897 | #1708 | Media | Regla de elegibilidad de duplicar durante `Pending Cancellation`; `needs-review`, el paraguas no define esa política todavía. |
| #1872 | #1708; secundario #1657 | Alta | La transición de aprobación cancela el documento pero omite revertir relación/refrescar cache; #1657 cubre invalidez de estado derivado. |
| #1803 | #1708 | Alta | #1638 documenta el mismo query base vs `cancel_<doctype>`; #1803 añade StockEntry/detalle. Mantener ambos abiertos hasta que responsable decida consolidación. |
| #1728 | #1708 | Media | Solicitud `None` se anuncia como pendiente; el resultado de solicitud no gobierna estado/transición. Política de ausencia de matriz sigue `needs-review`. |
| Carrera candidata cancelación/request | #1653 | Baja | Falta repro de dos sesiones; no crear/vincular issue hasta comprobar intercalado. |
| `create_ledger_mapping_rule()` | #1653 candidato | Alta (repro PostgreSQL) | Dos altas sincronizadas pasan el SELECT de duplicado e insertan destinos distintos para la misma clave; `apply_ledger_mappings()` detecta ambigüedad y bloquea posting. Comentado en #1653; falta decisión de diseño y fix. |

## Clasificación ampliada de raíces 1712–1719 (bodies y issues consultados)

Estas asignaciones cotejan el mecanismo descrito en cada root con los issues abiertos que lo citan. Son agrupaciones para triaje, no aceptación de solución; cuando un hijo tiene otro mecanismo principal, el root se indica como secundario o queda sin asignar. Los duplicados y decisiones de negocio permanecen abiertos.

| Root | Issues agrupados por mecanismo | Confianza / límites |
|---|---|---|
| #1712 — respuestas async obsoletas | Request/snapshot tardío: #1213, #1591; importación que reemplaza contenido editado/validado: #1453, #1454, #1455, #1480, #1575; resultados de filtros anteriores: #1457; dashboard conserva datos previos tras error: #1609; conciliación guarda snapshot obsoleto: #1862. | Alta en los mecanismos reproducidos ya listados; #1480 está marcado duplicado de #1453; conservar separado solo para rastrear superficies/regresión. Preview de pago deduplicado en #1513 bajo root fiscal #1707; comentarios de triaje en este issue aclaran la corrección y la evidencia nueva. |
| #1713 — identidad de línea/consumo pendiente | Matching por artículo u ocurrencia equivocada: #1077, #1425, #1431, #1482; asignación/devolución omite línea fuente o admite repetidos: #1137, #1424, #1426, #1521; #1617 candidato: duplicar factura/remisión conserva origen pero omite `DocumentRelation` por línea que luego exige submit. | Alta para los mecanismos listados. #1482 duplica explícitamente #1431; #1137/#1521 se solapan y requieren dedupe. #1617 requiere confirmar que el root también cubra creación/preservación de relaciones al duplicar, no solo matching y consumo pendiente (comentario #6661648378). #1496 aparece en la lista del root pero trata tercero incompatible; posible #1717/#1649, baja confianza para #1713. |
| #1714 — open items AR/AP | Signo/doble conteo/referencia sin origen: #1113, #1116, #1570, #1616; dirección/tipo de pago: #1495, #1497; línea referenciada en ledger: #1573; créditos abiertos en aging: #1585; corte histórico: #1614; tasa en aplicación posterior: #1545; saldo no revalidado al postear: #1140; alias `debitnote/creditnote` diverge entre validación y writer (candidato `needs-review`, sin hijo). | Alta para saldo, subtipo, signo, dirección y corte. #1545 es principalmente #1655 (tasa histórica), secundario #1714; #1140 también #1653 (atomicidad); #1497 también #1717 (validación de dominio). |
| #1715 — valoración/capas inventario | Rebuild destructivo/composición/referencias: #651, #1335, #1336, #1415; FIFO/fecha/consumo/devolución: #1133, #1214, #1413; costos capitalizados al devolver: #1216, #1217, #1218, #1219; reversa FIFO: #1858. | Alta. #1413 duplica #1214. #1858 cita #1715 pero distingue #1336 como mecanismo distinto en sus repros. #1876 candidato medio/bajo según alcance de reversa por lote; #1878 necesita criterio de límite monetario por lote. |
| #1716 — vigencia de entidad/rol al usar | Cuenta/dimensión/banco inactivo o revocado: #1265, #1300, #1339, #1342, #1343, #1538, #2011; proveedor inactivo al aprobar: #1302; #1982 (numeración bancaria acepta referencias inactivas, candidato); #1919 candidato; #1927 candidato needs-review UOM. | Alta salvo #1300, cotejar semántica “no contabilizable” frente a jerarquía/tipo. #1720 solo candidato bajo: checkbox defectuoso al crear estado inactivo, no guard de uso. #1919 reproduce acceso de portal tras desactivar Party/CompanyParty y requiere decisión de vigencia histórica; #1927 exige decidir uso de UOM inactiva. |
| #1717 — validación server-side de dominio | POST continúa con formulario inválido: #1182, #1183, #1184, #1722 (los handlers de cliente/proveedor omiten ejecutar WTForms; `FormularioCliente.name` sí declara `DataRequired`), #1941 (intervalo AccountingPeriod invertido), #1974 (FiscalYear CRUD permite rango invertido), #1736 (UOM y bodega; POST vacío actual reproducido); dominio/enums/rangos/allowlist: #1225, #1258, #1362, #1568, #1668, #1764; inventario: #1212, #1754, #1826, #1829, #1864, #1892; duplicado único sin manejo #1929; grupo/estado/asociaciones: #1358, #1724, #1741; límites de campo del perfil #1913; tipo de cuenta de liquidación omitido de choices #1914; orden de línea JSON inválido escapa como `ValueError` #1933; clase paginadora pública sin validar `page_size` #1904, #1983 (numeración bancaria permite entity_type/counter_type incompatibles, candidato); #1992 (serie elegida en vale ignorada, needs-review); #2009 (casillas `is_selling`/`is_active` omitidas persisten True); #2010 (company/currency libres terminan en HTTP 500 con FK activas); #1978 (candidato: link_id de otro Party causa ValueError/HTTP 500 en deactivate aunque no muta). | Alta en validación omitida; #1722/#1736 por omisión reproducida y #1929 por código duplicado sin respuesta controlada. #1754 cubre SKU cruzado de Batch; la variante de devolución por lote origen sigue `needs-review`. #1724 requiere criterio sobre asociaciones previas; #1864 también #1650; #1829 medio (unicidad/ownership serial). #1904 es validación de una precondición pública, no input de posting; asignación tentativa. |
| #1718 — paridad y ciclo de vida imports | Montos/acumulados: #1204, #1205, #1398, #1439; mapeo/contexto ejecución: #1383, #1394, #1456, #1478, #1676; lotes/recuperación/cancelación/datos inválidos: #1031, #1032, #1374, #1393, #1395, #1661, #1674, #1675; rol/referencia/tipo de pago/cuentas: #1447, #1477, #1532, #1672. | Alta como paraguas de paridad/ejecución. #1477/#1532 probable duplicado; #1383 ya duplica #1048, pero su mecanismo pertenece al ciclo de imports. Revisión actual: POST acepta `record_type` fuera de allowlist HTML y JournalEntry omite validación ante RuntimeError; probe real CSV/ODS acepta fecha ISO, XLSX fecha tipada entrega datetime y falla `date.fromisoformat(str(value))`; XLS serial queda estático por falta de writer. Cabeceras heterogéneas ya tienen repro específico #1478; serial/cantidad #1629. No abrir duplicados. |
| #1719 — árbol y flujo documental | Tipos de nodo: #1408, #1615; aviso de límite: #1412, #1633; búsqueda/dedupe: #1464; fuentes/destinos permitidos: #1515, #1516; límites externos/recursión: #1517; validar origen al cerrar: #1552. | Alta por correspondencia con contratos del root. #1408/#1615 y #1412/#1633 describen pares solapados, requieren dedupe. |

## Clasificación ampliada de raíces 1657–1658 y 1706–1711

Esta muestra adicional parte de hijos explícitos en los bodies y los compara con la definición causal del root. La agrupación aún requiere reconciliar duplicados/solapamientos y validar por código los issues no auditados.

| Root | Issues agrupados por mecanismo | Confianza / límites |
|---|---|---|
| #1657 — saldos derivados desincronizados | AR/AP: #1305, #1103, #1070, #1310, #1255, #1127, #1102, #1458, #1404, #1387, #1391, #1068, #1459, #1143, #1304, #1146; conciliación/bancos: #1228, #1230, #1316; inventario/bin: #1073, #1414; órdenes: #1599, #1440. | Alta en cache/saldo/transición; media #1146, #1304, #1459/#1143. #1178 no pertenece aquí; su carrera de serial va a #1653. #1583 es corte histórico (#1709), no cache. |
| #1658 — features a medias/código sin consumidor | UI rota/funciones vacías: #937, #1935; duplicación incompleta que pierde campos persistidos: #1798, #1618 (candidatos); rutas/adapters legacy: #1046, #1071, #1074, #1199; ODS de catálogos sin caller/paquete #1915; links a endpoints inexistentes: #1092, #1485, #1647; código/helper/campos sin consumidor: #1100, #1119, #1131, #1260, #1283, #1308, #1314, #1361, #1683, #1684, #1909, #1938, #1940, #1973, #2045; config/feature desconectada: #1277, #1278, #1299, #1352, #1353, #1366, #1367, #1490, #1576, #1646, #1670; gate de módulos `audit`/`documents` no registrados #1581 (candidato, feature incompleta, no dead code); catálogo/semántica parcial: #1215, #1239, #1249, #1250, #1285, #1294, #1298, #1331; CSS sin uso #1899; límites dead-code de query tools #1841; impresión settings/historial #1930/#1931 (needs-review integrar/retirar). | Alta para no-callers, rutas rotas y funciones desconectadas; media para features/configuración con criterio pendiente. #1581 es provisional: handlers registrados con gate que impide uso estándar; confirmar que no haya root más preciso. Nuevo hallazgo de plantilla duplicada `cacao_accounting/templates/setup/setup.html`: sin caller local, mientras el Blueprint activo renderiza la ruta homónima bajo `setup/templates`; candidato dead/unwired, comentado en #1658 (`6684110507`), sin decisión sobre contrato externo. Nuevo candidato O2C #2045: `/sales-order/new` acepta `from_order`, carga y pasa `orden_origen/from_order_id`, pero el template y POST solo consumen solicitud/cotización; falta decidir integrar o retirar la rama. Se abrió `needs-review` bajo #1658; comentario root `6683906694`. Nuevo candidato `imports/adapters/purchase_order.py`: no caller local y registry usa homónimo en `transaction_documents.py`; contrato externo por confirmar, comentado en #1658. Recurrentes: `get_applicable_templates`, `_canonical_book_reference`, `_normalize_ledger_id_for_validation` y `admin.session_security_service.listar_dispositivos_usuario` sin callers locales; no borrar hasta confirmar plugins/API externos. Continuación Compras: `purchase_invoice_draft_service.py` no tiene callers/tests/docs aunque declara intake manual/import/Cloud futuro; acepta el alias de tipo `purchase` que UI/validador estándar no admiten (comentario #1658 `6679383280`); `source_references` es inerte y `create_purchase_order_comparison()` es una ruta de creación paralela sin caller, mientras rutas usan la API de rondas. Usuario define pre-lanzamiento sin soporte legacy: agruparlas aquí como flujo inactivo/duplicado que requiere retirar o integrar de forma sistemática, no conservar aliases por compatibilidad; evidencia de código comentada en #1658, sin eliminar unilateralmente en auditoría. #1313/#1273 son transición de cancelación (#1708), no dead code. Macros O2C `source_label` sin uso y `transaction_form_js()` sin caller local, contrato externo pendiente. |
| #1706 — append-only/inmutabilidad | #759, #923, #925, #1002, #1987 (candidato: reposición falla al actualizar vínculo de gasto posteado; requiere decisión de modelado append-only). | Alta según bodies/mecanismo del paraguas. En #759, el probe Desktop extendió ORM UPDATE aceptado de `StockEntry.remarks` a `DocumentTaxSummary.subtotal` y `DocumentTaxLine.amount` ligados a factura posteada; Cloud rechazó todos. #1877 es candidato inverso (guard bloquea conciliación legítima); verificar antes de añadir como hijo. |
| #1707 — motor fiscal canónico | #995, #996, #1008, #1009, #1011, #1015, #1023, #1026, #1236, #1274, #1275, #1276, #1436, #1437, #1441, #1513, #1549, #1634, #1635, #1637 (base fiscal de payload no confiable en snapshot de pago; probe adicional acepta retención manual Infinity en el mismo límite de pago), #1685, #1943 (secundario: contrato de errores de cálculo no propagado a la UI), #1686, #2020 (adapter por índice alinea resultado filtrado con la fila inactiva y desplaza base_mode). | Alta en divergencia de aplicabilidad/cálculo/representación/posting fiscal; #1513 recibió repro Chromium independiente donde preview tardío contamina payload con base 100 y total 111 cuando importe actual es 200 (fetch stub; snapshot de servicio sí persistió base/amount/total obsoletos; POST draft independiente creó PaymentEntry+snapshot, pero no surgió del browser y GL de retención no validado), comentarios `6682674119`/root `6682674396`; probe directo de persistencia SQLite guardó el snapshot viejo (base100/importe11/total111), comentarios `6682795488`/root `6682797773`; decisiones de aplicabilidad siguen `needs-review`. #1026 ya cubre base de gravamen con impuesto inclusivo y recibe extensión de probe legacy con varios inclusivos sobre `previous_total` (13.0435 devuelto frente a 13.4199 por interpretación secuencial); sin política/fix propuestos, conservar needs-review. |
| #1708 — estados/transiciones documentales | #761, #1017, #1022, #1027, #1043, #1082, #1090, #1106, #1107, #1166, #1170, #1186, #1209, #1210, #1211, #1221, #1222, #1232, #1273, #1364, #1365, #1367, #1375, #1422, #1430, #1432, #1503, #1553, #1565, #1566, #1593, #1605, #1606, #1613, #1621, #1638, #1642, #1701, #1702, #2008; extensiones #1803, #1807, #1872, #1897, #1520 (candidato: justificativo en blanco al confirmar adjudicación). | Alta para validación/transición/status; media #1807 por precondición y #1897 por política. #1872 tiene vínculo secundario a #1657 por cache/relaciones. #2008 reproduce rechazo no-op con solicitud abierta después de apagar Approval Engine y éxito HTTP aparente; #1728 se extendió al caller bancario: ausencia de matriz deja retorno None, no crea ApprovalRequest, pero ruta anuncia pendiente; `needs-review` de política. #1638 también se extendió a `pago.html`, donde la solicitud existente queda como Aprobado/anulable por usar solo docstatus. Hijos comentados a #1708; #2008 separado de #1017 (acción malformada). #1313 encaja aquí, no #1658. #1364 presenta evidencia de código contradictoria con el issue actual (guard de ronda en `validate_award_request`); no reasignar/cerrar hasta repro HTTP y revisar historial. |
| #1709 — cortes históricos/reversas | #1075, #1086, #1091, #1115, #1122, #1123, #1124, #1167, #1168, #1237, #1238, #1242, #1245, #1252, #1341, #1348, #1499, #1502, #1523, #1582, #1583, #1586, #1589, #1596. | Alta para as-of, apertura y reversa fechada. #1248 medio (filtro de periodo); #1237/#1238 límites presupuesto/periodo; #1561 agrupa periodo, no cut-off; revaluación retroactiva lee pagos/corridas futuras y budget excludes reversals sin corte, ambos candidatos `needs-review`. #1252 tiene conciliación como mecanismo principal. #1377 duplica #1585 y encaja mejor en #1714. |
| #1710 — credenciales/mensajería | #1018, #1020, #1028, #1109, #1110, #1354, #1355, #1356, #1360, #1442, #1443, #1444, #1548, #1602, #1641, #1693, #1695, #1696, #1917, #1958 (candidato), #2023 (candidato: el reset genera/activa token aunque falle el correo y consume el previo). | Alta en sesión/OTP/reset/secretos/reintentos; #1018/#1360/#1693 se confirman además por ejecución focal: servicio reenvía fila `sent` e incrementa attempts. #1958 es candidato separado: commit posterior al envío SMTP falla y revierte trazabilidad EmailQueue; root candidato, sin consolidar estrategia de outbox. #1917 confirma redirect mal formado al completar OTP. #1354 duplica #1020; #1444 #1028; además, `profile()` permite duplicado por case-variant y reproduce el mismo lookup ambiguo (comentario `6680369095`); #1360 #1018; #1548 se relaciona con #1109. #1735 es hijo candidato por fallo de configuración de seguridad de sesión si falta SMTP. Revisión SMTP adicional detectó login con credenciales por transporte sin TLS si `smtp_use_tls=false` (comentario #1710); no asignarlo como hijo ni definir política hasta decisión del desarrollador. #1762 se mantiene como candidato aparte: fallo secuencial de persistencia, cuyo mecanismo no está claramente expresado en el body de este root. #1920 no se asigna aquí: el mismatch entre role helper y route guard no comparte con #1710 la causa de vigencia/session/token/mensajería. |
| #1711 — contrato de interfaz | #1111, #1112, #1125, #1428, #1463, #1484, #1485, #1486, #1487, #1518, #1554, #1557, #1574, #1610, #1622, #1632, #1643, #1645, #1648, #1659, #1666, #1667; extensiones revisadas #1761, #1810, #1811, #1825, #1834, #1835, #1838, #1859, #1861, #1870, #1871, #1872, #1874, #1875, #1887, #1888, #1889, #1896, #1903, #1906, #1907, #1908, #1911, #1912, #1918, #1928, #1932, #1934, #1935, #1936, #1939, #1942, #1378, #1438, #1594, #1427, #1869, #1943, #1944, #1945, #1946, #1949, #1556, #1950, #1951, #1953, #1956, #1961, #1975, #1976, #1977 y #1990, #1992 (candidatos), #2021 (candidato), #2022 (candidato), #2031, #2032, #2033, #2035, #2036, #2037, #2038, #2039, #2040, #2041, #2042, #2043 (candidatos), #2044, #2046 (vacío I2F) y #2047 (vacío O2C; curl de siete rutas); #1955 es secundario a #1656. #1912 no se reproduce en HEAD, requiere reconciliar. | Alta cuando falla i18n/Alpine/URL/endpoint/CSRF o la vista contradice persistencia; #1936 reproduce control de período sin selector DOM requerido en report_table; #1939 reproduce pérdida de rango en URL del drilldown; #1942 queda needs-review por contrato de representación de moneda; #1378/#1438/#1594/#1427/#1869 son errores de contrato/formato de interfaz con #1655 secundario; #1943 cubre errores de preview no comunicados; #1944 reproduce por HTTP la categoría existente omitida de la columna visible, distinto de #1850 (selector/validación); presupuestos: #1487 falla al compilar por `format_currency` ausente y #1486 pide endpoint `lista` inexistente en paginación (ambos #1711, no #1652); pérdida de campos al responder a validación rechazada en #1951 (Cash Forecast) y #1956 (FX); mismo síntoma que #1884/#1901, mantener por flujo hasta validar una corrección común y no asignar root como confirmado; candidatos i18n en FX/import y diagnóstico AR/AP API; #1928 confirma cuerpo Jinja omitido por nombre de bloque distinto y #1932 reúne etiquetas/errores sin traducción. #1632 queda como mecanismo distinto de invalidación al cambiar compañía. Los issues con causa compartida de backend/estado siguen diferenciados. #1976 documenta selección Smart Select solo por mousedown; #1977 los doctypes de año fiscal no registrados en dos templates de presupuesto; se comentaron en #1711 (`6670866574`). Root sigue `needs-review`; asociaciones candidatas, no aprobación de causa. #1985 es candidato por serialización JavaScript no contextual (related #1867); comentario `6672306100`. |

## Clasificación ampliada de raíces 1649–1656

Mapeo de issues abiertos citados en bodies/comments de raíz y clasificados por mecanismo. Los cruces dudosos se separan para evitar que listas heredadas asignen issues a una causa incompatible.

| Root | Issues agrupados por mecanismo | Confianza / límites |
|---|---|---|
| #1649 — alcance compañía/ACL | #997, #998, #1021, #1095, #1096, #1097, #1104, #1120, #1130, #1169, #1173, #1175, #1176, #1181, #1192, #1247, #1253, #1254, #1256, #1261, #1280, #1282, #1284, #1286, #1301, #1320, #1321, #1322, #1327, #1328, #1329, #1330, #1332, #1338, #1376, #1388, #1399, #1407, #1409 (QA extiende fuga a formularios de origen de factura/remisión), #1410, #1411, #1416, #1417, #1418, #1433, #1445, #1462, #1467, #1468, #1488, #1511, #1515, #1524, #1525, #1526, #1527, #1540, #1541, #1542, #1543, #1546, #1558, #1562, #1572, #1588, #1590, #1595, #1598, #1600, #1601, #1608, #1640, #1665, #1700, #1705, #1971, #1986, #1988, #1989; #2044 (relacionado por el rechazo ACL devuelve 200); #1926 candidato. | Alta cuando el scope/ACL/company ownership es el mecanismo explícito; #1175 se confirmó por HTTP en lista, detalle y selector Batch (usuario cacao obtiene datos de secreta; lista/detalle tampoco exigen permiso); el propio issue ya fija filtrar actividad por compañías autorizadas. La visibilidad de metadatos del maestro Batch sin actividad no se evaluó. Listado `/exchange-revaluation` sin scope confirmado por dos revisores; #1338 queda confirmado por probes SQLite: validate_company_access acepta Entity disabled en allowlist y companies.list la devuelve; #1399 requiere confirmar el síntoma principal; #1926 requiere definir si el catálogo UOM global debe exigir permiso de consulta. `list_filters.company_choices_for_module()` también devuelve entidades deshabilitadas a administrador; reproducido en fixture y comentado al root. #1282 se confirma además por POST de rol sales_user de solo lectura que desactiva Contact; falta decidir autorización de datos de terceros compartidos y ajustar guards de acción/compañía, manteniéndolo bajo este paraguas ACL. #1649 conserva `needs-review`: definir si la opción aplica a lectura histórica, altas nuevas o ambas antes de etiquetarla como defecto. Query Tools admin.configuration.list también mostró clave budget_control_enabled de otra compañía al principal cacao (#1649), bajo comentario del root. DocumentTask: #1595/#1572 se extendieron por HTTP al revocar permission de módulo conservando membership, `/tasks/my` sigue mostrando título/ref; #1598 incluye miembro de compañía sin consulta en selector, backend rechaza al asignar; ACL de documento/acción y policy del directorio siguen por validar. #1321 se reprodujo por curl: sin RBAC y viewer sales/cacao reciben usuario activo de compañía secret desde `/api/search-select?doctype=user`; anon 302. Evidencia: comentario #1321 `6670674794`; issue ya bajo este root. Caja Chica: cinco list endpoints responden 200 vacío al usuario autenticado sin roles; `_cash_accessible_companies()` limita a ninguna compañía y no se observó fila ajena (#1649, comentario `6670146123`); decidir si política requiere 403 o vacío, por ahora no afirmar fuga. Bancos CTM: #1988 reproduce dimensiones de otra compañía persistidas en vale borrador (relacionado #1890), y #1989 reproduce metadatos de vale extranjero en GET directo de alta de gasto (relacionado #1971/#1986); ambos comentados en este root. curl confirmó anónimo 302 `/login`; sin RBAC, GET de conciliación, matching, conciliación de pagos, transacciones, pagos y transferencias responde 200 vacío; `company=other` y POST con CSRF válido sin permiso responden 403. No se observó fila ajena; política 403/vacío pendiente. Evidencia curl en comentario `6670522386`. #1971 es fuga de metadatos del origen `SalesRequest` en GET de alta de cotización (`from_request` cross-company), demostrada en HTTP 200; el POST válido conserva su guard y el probe no accedió a líneas. #1096 se confirmó de nuevo en Flask/SQLite: `/cash_management/payment/new?from_sales_invoice=secret-inv` devolvió `SECRET-INV-9` de otra compañía al usuario autenticado sin RBAC; el POST sin `cash.crear` hizo rollback y no persistió (#1096 comentario `6682575926`, root `6682577926`).
| #1650 — coerción numérica en frontera | #950, #1007, #1010, #1072, #1087, #1174, #1185, #1263, #1292, #1296, #1403, #1512, #1519, #1544, #1419, #1571, #1500, #1469, #1505, #1688, #1382, #1972, #1984. | Alta. #1984 reproduce `float_amount=abc` → `decimal.InvalidOperation`/HTTP 500 antes de persistir; #1505 también interactúa con import de extracto (#1652). AllocationPlanner permite `Decimal(NaN/Infinity)` y falla con `InvalidOperation` (#1650 confirmado por QA independiente); #1972 reproduce `Decimal('NaN')` no controlado al parsear monto de conciliación bancaria, sin alcanzar mutación/contabilización. |
| #1651 — canonización UOM/cantidad base | #947, #966, #1034, #1037, #1038, #1135, #1136, #1180, #1279, #1307, #1333, #1334, #1429, #1481, #1624, #1639. | Alta por factor/conversión/UOM y cantidad base. |
| #1652 — lectura tabular de imports | #1201, #1529, #1506, #1471, #1479, #1478, #1535, #1536, #1533, #1530, #1532, #1531, #1202, #1534, #1474, #1475, #1345, #1396, #1625, #1400, #1603, #1446, #1623, #1206, #1373, #1200, #1295, #1491, #1627, #1628, #1451, #1450, #1449, #1448, #1435, #1030, #1033, #1048, #1052, #1054, #1055, #1061, #1065, #1066, #1197, #1291, #1346, #1392, #1401, #1452, #1472, #1489, #1507, #1510, #1626, #1631, #1662, #1385 (candidato). | Alta para parsing/shape/normalización; media cuando el mecanismo es persistencia downstream. #1262/#1389/#1385 se mantienen `needs-review` por política de identidad/columnas desconocidas y validación HTTP; #1385 duplicó dos transacciones cuando `ImportService.execute()` recibió un grupo por `reference`, pero el flujo normal está bloqueado hoy por #1031. |
| #1653 — atomicidad/idempotencia | #1000, #1005, #1076, #1093, #1094, #1139, #1144, #1145, #1148, #1186, #1187, #1188, #1189, #1190, #1191, #1231, #1266, #1267, #1268, #1271, #1288, #1289, #1290, #1309, #1319, #1326, #1669, #1682, #1689, #1690, #1691, #1692, #1694, #1697, #1991 (candidato: commit GL durable seguido de fallo al insertar subledger), #2030 (candidato: reversión GL confirmada antes de mutar gasto/vale); además #1306 y #1178 (salida concurrente del mismo serial). | Alta para los read-then-write concurrentes; #1694 cubre unique con NULL y precheck concurrente. #1699 queda candidato secundario: preview validado queda stale frente a línea manual insertada antes de confirmar (sin concurrencia reproducida), mecanismo de revalidación/idempotencia cercano pero no idéntico. #1653 está `fix-proposed`, sin que esto cierre hijos ni decisión de idempotencia por Tier 1. |
| #1654 — lectura/saldo multilibro | #1025, #1035, #1243, #1244, #1269. | Alta. #1035 figura `fix-proposed`; raíz señala el fix, pero estado abierto requiere cotejar fix/aceptación. |
| #1655 — moneda y tasa histórica | #546, #758, #961, #1016, #1078, #1098, #1114, #1121, #1164, #1233, #1235, #1251, #1270, #1281, #1317, #1323, #1324, #1325, #1380, #1460, #1494, #1545, #1560, #1569, #1597, #1604, #1607, #1636, #1673, #1942 (presentación comparativa; secundario de #1711). | Alta para conversión/base/tasa; presentation-only issues se asignan primariamente a #1711; #1223/#1224 requieren root de flujo/enlace. |
| #1656 — ciclo fiscal/período | #1004, #1024, #1153, #1154, #1155, #1156, #1157, #1158, #1171, #1172, #1170, #1168, #1287, #1312, #1372, #1238, #1257, #1258, #1259, #1381, #1490, #1501, #1577, #1293, #1698, #1350/#1584 (candidatos: fallback silencioso al mes actual), #1952 secundario, #1974 secundario (CRUD persiste año invertido), #1954/#1955 (`needs-review` por alcance/duración fiscal); #1941 secundario (primary #1717). | Alta para período/año/fecha; media en ventanas/configuración presupuestaria. #1165 corresponde a vigencia de moneda (#1716), no a cierre fiscal. |

### Conflictos de asignación entre raíces 1649–1656

- #1192 corresponde a #1649 (ACL `cash.anular` frente a checker `editar`), no #1653; #1235 a #1655 (moneda de libro vs filtro), no #1654 (agregación de libros); #1270 a #1655 (reposición multimoneda), no #1653.
- #1341 corresponde a #1709 (saldo de apertura al corte), no #1649/#1654. #1477 corresponde a validación de dominio de import (#1717), no #1649/#1652. #1487 es un filtro Jinja ausente y #1486 un endpoint de paginación inexistente; ambos son errores de contrato de interfaz (#1711), no imports tabulares (#1652) ni períodos (#1656).
- #1488 corresponde a #1649 (lote importado no vinculado al company autorizado); #1505 a #1650, con #1652 secundario por la lectura de extracto. #1629 queda `needs-review` entre validación de dominio (#1717), UOM/cantidad (#1651) e import (#1652).
- #1163/#1386 tratan selección de libro al escribir un comprobante, no lectura agregada (#1654). #1236/#1406 requieren separar fiscal (#1707) de linaje (#1713); #1466 es falta de commit/unidad de trabajo, no read-then-post.
- No asignar a estas raíces por parecido superficial: #1165 (#1716), #1283 (#1658), #1341 (#1709), #1477 (#1717), #1602 (#1710), #1621 (#1708/#1719), #1077 (#1713), #1179 (tests), #1611 (#1716), #1031/#1032 (#1718), #1049 (#1708), #1050 (#1650), #1053 (#1713), #1455 (#1712), #547 no a #1716 (candidatos residuales #1718/#1717 y comentario conflictivo a #1652), #1161/#1177/#1194/#1272/#1273 (#1714/#1708/#1657), #1234 (CTM vencimiento), #1580 (prefijo externo), #1584 (fallback período), #1703 (ULID visible).

### Conflictos detectados en las listas de raíces

- #1178 pertenece a #1653 por salida concurrente de un serial; no a #1657 (el root AR/AP deriva explícitamente la carrera a #1653).
- #1213/#1591 son #1712 (respuestas async obsoletas), no #1657. #1583 es #1709 por reversa fechada, no saldo cacheado; #1377 figura duplicado de #1585 y su presentación de crédito encaja mejor en #1714.
- #1313/#1273 describen elegibilidad/transición de cancelación (#1708), no código muerto (#1658). #1147 trata identidad de open item (#1713), no saldo derivado (#1657).
- #1351: #1709 principal por corte del settlement posterior a cancelar; #1657 puede quedar secundario si se rastrea el efecto sobre saldo/cache. #1872: #1708 transición incompleta, #1657 secundario por relación/cache.
- #1824/#1817 citan #1707 (motor fiscal); #1761/#1859/#1838/#1870/#1871/#1874/#1875/#1887/#1888/#1889/#1896/#1903 citan o encajan en #1711 (contrato frontend), con mecanismos secundarios cuando aplican.
- No asignar por proximidad de módulo: #1801 (mensaje de éxito tras rollback), #1820 (reserva de órdenes cerradas) y #1827 (selección de cuenta por bodega) no comparten los mecanismos de #1713/#1716/#1717 consultados.

## Cotejo del lote #901–#1200 (2026-11-05)

Los 44 issues abiertos de este rango que no tenían mención en el mapa se consultaron individualmente con `gh` (título, body, labels y comments). Las asignaciones siguientes son candidatas cuando el enlace actual o el mecanismo es claro; la mención en comentarios no sustituye validación del código ni cambia labels del issue.

| Issues | Causa raíz candidata | Confianza / límite |
|---|---|---|
| #1160, #1159 | #1653 — transiciones read-then-post concurrentes | Alta; #1159 tiene fix-proposed, falta verificar en código y conservar vínculo al aceptar el fix. |
| #1152 | Sin root confirmado; #1656 candidato | Media; aplicación `pending` creada por paso parcial vuelve a enviarse y servicio no permite recuperación/no-op. El check marca éxito antes del posting; #1776 trata el mismo recorrido. #1653 es débil: el body exige carrera read-then-post concurrente, que este repro secuencial no prueba. No asignar #1708. |
| #1040 | #1708 primario; #1657 secundario | Alta; cancelación de factura deja relación/cache de la DN hija sin revertir. |
| #975 | Sin raíz única; #1713/#1655/#1714/#1711/#1712 candidatos por subhallazgo | Issue compuesto: serializer/campo, moneda de asignación y estado obsoleto tienen mecanismos distintos; no asignar solo a #1657. Considerar dividir alcance. |
| #1036 | Sin root confirmado | Fórmula de conciliación de caja vuelve a contar gastos ya reflejados en GL; no es saldo AR/AP derivado. |
| #1149, #1493 | #1658 candidato; duplicado causal confirmado | Servicio/formulario/template cotejados: `frequency` se persiste y presenta, pero descubrimiento y aplicación no consultan el valor; misma causa y política daily/weekly/monthly sigue `needs-review`. Fin de vigencia intraperíodo también puede dejar plantilla aprobada sin ocurrencia final. |
| #1132, #1134 | #1709 — consulta de saldos a fecha/corte | Media; validar que root cubre ambos contratos. |
| #1019 | #1649 — autorización y aislamiento por compañía/documento | Alta; comentarios actuales enlazan explícitamente. |
| #999, #1069 | #1714 — identidad/subtipo y dirección de open item | Alta para referencia/subtipo; #1069 conserva decisión `needs-review` por netting AP/AR. |
| #1039 | #1711/#1717 candidatos | Media; parser de filas descarta input con hueco de índice; validar si el contrato común es payload/UI o estructura server-side. |
| #1198 | #1718 primario; #1717 secundario candidato | Alta para adapter: busca `Item` por `code` usando dato importado y falla en validar warehouse; corregir la mención previa “alta de bodega fuera de importación”, que contradice el body. |
| #1196, #1064, #1063, #1060, #1062, #1057, #1058 | #1718 candidato; #1717 secundario en validación de dominio | Media/alta por ciclo, adapter y paridad de validaciones. |
| #1059 | #1718/#1658 candidatos | `needs-review`; el adapter descarta impuesto y el modelo no lo conserva; confirmar contrato antes de tratarlo como error o feature incompleta. |
| #1162, #1099 | #1658 — elementos sin caller productivo | Media; cotejar caller/feature antes de retirar código. |
| #1101 | #1653 candidato — `commit=False` ignorado en destino de pago | Media; comprobar writer actual/atomicidad. |
| #1193, #1151, #1118, #1088, #1051, #1042, #1041, #1129, #1128, #1105, #1067, #1029 | Sin asignación confirmada | Mantener criterio `needs-review`; mecanismo/política no coincide con precisión con los roots actuales. |
| #1089, #1264 | Sin root actual; duplicado causal probable | Reasignar PettyCashFund deja de leer saldo histórico de la cuenta previa; bloquear cambio vs. reclasificar sigue `needs-review`. |
| #1080, #1504 | Sin root actual; duplicado probable | Candidato elegido no coincide con la regla reportada; mismo mecanismo. |
| #1081, #1509 | Sin root actual; duplicado probable | Auto conciliación omite `reference_contains`; no mezclar con la discrepancia de provenance #1080/#1504. |
| #1138, #1220 | Sin root actual; duplicado probable | Devolución física parcial valida importe contra total de línea; #1522 comparte capacidad por línea, pero es borde acumulativo distinto. Proporcionalidad/impuestos/FX siguen `needs-review`. |
| #1083, #1258 | #1717 candidato; duplicados causales probables | POST HTTP/SQLite actual persiste `periodicity=annual`; servicio lo interpreta como semanal y genera 53 períodos. Ambos issues describen el mismo mecanismo; evidencia comentada en los dos y en root #1717 (`#issuecomment-6661820462`, `#issuecomment-6661820305`, `#issuecomment-6661820298`). No cerrar ni deduplicar externamente sin triaje.
| #1079 | #1717/#1708 candidatos | ID de ronda inexistente/cerrada convertido a `None`; dominio de referencia y estado, mantener provisional. |

Corte histórico posterior a #1915: 912 IDs abiertos exactos. El corte vigente posterior a #1917 contiene 914 IDs; la cobertura causal completa permanece pendiente. Este lote documenta candidatos y excepciones y no altera issue labels.

## Cotejo del lote #1201–#1500 (2026-11-05)

El rango contiene 294 issues abiertos; 256 ya aparecían antes de este encabezado y 38 son primeras menciones en esta sección. El conteo usa sets de IDs únicos del snapshot `ISSUE.md` y el texto previo; las referencias repetidas no cuentan como issues distintos. Las propuestas siguen provisionales y preservan `needs-review` hasta validar la causa.

| Issue(s) | Causa candidata | Confianza / acción pendiente |
|---|---|---|
| #1031, #1203, #1397 | #1718 — ciclo de vida y recovery de importación | Alta para la causa común de lifecycle; #1031 también conserva la regresión `started_at` que bloquea validate→execute, reproducida históricamente y reconfirmada por inspección independiente en HEAD `85eed67b`. #1203 conserva hallazgos de recuperación/race distintos; no consolidar automáticamente. |
| #1347, #1492, #1226, #1465, #1952 | #1717 — validación server-side de dominio/entrada | Alta para entradas inválidas; #1952 además pertenece al ciclo fiscal (#1656 secundario). No incluir #1350, que comparte el fallback de período #1584. |
| #1227 | #1714 — dirección/subtipo de open item | Alta. |
| #1208, #1423 | #1708 — transición/cancelación documental | Alta para el mecanismo; #1208 retiene `needs-review` por fecha de anulación en el mismo periodo. |
| #1315 | #1711 candidato — contrato ruta/plantilla; asignación vigente #1656 | Media: el issue describe una query `FiscalYear` presentada como comprobante, no una transición fiscal. La evidencia HTTP confirma el desacople entre el modelo de respuesta y Jinja; revisar con el desarrollador si la causa debe moverse del root fiscal al root de contrato UI. |
| #1493 | #1658 candidato — recurrencia guardada pero no ejecutada | Media; potencial duplicado causal de #1149, preservar revisión de alcance. |
| #1498 | #1716 candidato — uso de fondo de caja inactivo | Media; conservar `needs-review` sobre desactivación vs liquidación. |
| #1311 | #1709 — saldo histórico/as-of | Alta; no #1656 (ciclo fiscal). |
| #1207 | #1657 primario; #1714 secundario candidato | Alta en causa reportada; revisar corte `reversed_at` como factor contribuyente. |
| #1297 | #1707 candidato — regla fiscal de tercero ausente del resolver canónico | Alta; comentario existente #1658 parece demasiado amplio. |
| #1264, #1089 | Posible mismo mecanismo histórico de PettyCashFund account | Alta para mecanismo/duplicidad: cambiar cuenta hace que el saldo GL histórico se lea con cuenta actual. No asignar #1657; bloquear cambio vs. asentar reclasificación sigue `needs-review`. |
| #1220, #1138 | Posible mismo contrato de nota de crédito física / qty devuelta | Alta para mecanismo/duplicidad: se valida importe total de línea aunque la devolución sea parcial. Proporcionalidad, impuestos y FX conservan `needs-review`. |
| #1461 | #1717 candidato; vínculo actual #1650 no coincide | Mecanismo confirmado por QA: fecha ISO string se asigna a `posting_date` sin normalización y falla SQLite. Candidato de root, revisar alcance de #1717. |
| #1434 | #1708 candidato; vínculo actual #1709 no coincide | Mecanismo confirmado por QA: KPI de PurchaseOrder ignora estado/cantidades y cuenta por `docstatus`; revisar alcance de la política de estados. |
| #1421, #1420, #1402 | #1711 candidato | Mecanismo confirmado por QA: estado de UI/selectores y filtros desincronizados, no saldo derivado #1657. |
| #1379 | #1711 primario, #1712 secundario candidato | Mecanismos confirmados por QA: party-change conserva referencias aplicadas obsoletas y respuesta asíncrona anterior puede ganar carrera. |
| #1363 | #1708 candidato | Media; orden de ULID no cronológico altera secuencia/reconstrucción de eventos. |
| #1349, #1587 | Sin root confirmado; duplicado probable | Umbrales `min_stock_qty` y `reorder_level` priorizados de forma distinta; confirmar la política de alertas antes de consolidar. #1741 no es root ni mismo mecanismo. |
| #1359, #1368, #1337 | #1658 candidato para dimensiones al GL | Media; deduplicar #1359/#1337 y conservar `needs-review` por reglas de dimensiones. |
| #1357 | #1658, dead code de blueprint | Alta en evidencia de issue, pero verificar HEAD porque comment afirma retirado en commit. |
| #1470, #1508, #1644, #1721 | Sin root confirmado; cluster duplicado probable | Selector de conciliación automática elige entre candidatos exactos bajo reglas conflictivas; política fail-closed necesita `needs-review`. |
| #1483 | Sin root; patrón relacionado, no duplicado exacto | Valor monetario persistido en cero se confunde con ausencia; #1555/#1612 comparten patrón en otros sitios, pero efectos distintos. |
| #1405, #1371, #1370, #1344, #1340, #1303, #1246 | Sin root confirmado | No forzar root por proximidad; conservar dudas de payload/flujo, workflow/tests, control de flujo, SSRF, unicidad, conciliación bancaria e indicador de inventario hasta validar causa/criterio. |
| #1385 | #1652 candidato, `needs-review` | Reproducción funcional en SQLite: dos transacciones duplicadas al ejecutar grupo por `reference`; para alcanzar ejecución se limpió `started_at` porque el flujo normal validate→execute está bloqueado por #1031. Aún falta HTTP y criterio para columnas desconocidas; no marcar como fully end-to-end. |
| #1390, #1514 | #1711 candidato; duplicado probable | Fecha default usa UTC en lugar de fecha local; preservar contrato de zona horaria bajo `needs-review`. |
| #1476, #1537 | #1718 candidato; duplicado probable | Import de terceros descarta campos `grupo`/`clasificacion`; el mapping esperado queda `needs-review`. |

QA de código confirmó que varios enlaces anteriores eran causalmente incorrectos (#1461→#1650, #1434→#1709, #1420/#1421/#1402/#1379→#1657 y #1349→#1741). Los mecanismos están documentados arriba; los roots alternos son candidatos, no asignaciones finales, hasta verificar alcance y preservar las decisiones `needs-review`.

Los roots citados en esta muestra incluyen #1649–#1658 y #1706–#1719; el índice enumera los 24 roots abiertos del snapshot. Las menciones incluyen referencias cruzadas/conflictos y no equivalen a asignaciones causales confirmadas ni a validación por código; el conteo vigente se reconcilió con `ISSUE.md` después de #1917.

## Lote consultado #1501–#1800 (candidatos, sin asignación confirmada)

105 issues abiertos ausentes en el mapa se consultaron vía API. Estas agrupaciones provienen de lectura de bodies/comments; requieren cotejo por código antes de consolidar referencias:

| Issues candidatos | Root candidato(s) | Nota |
|---|---|---|
| #1797, #1796, #1789, #1777, #1781, #1753 | #1649 | Guards/lecturas/escrituras fuera de scope de compañía o permisos; #1797 depende de blueprint duplicado no registrado. |
| #1765, #1678, #1677, #1671, #1663, #1528, #1203 | #1718 | Contrato de importación, parsing/encoding, precisión, locale, recuperación y caché. |
| #1791, #1788, #1787, #1768, #1769, #1772, #1778, #1779, #1578, #1579, #1687, #1739 | #1717 candidato | Validación de escritura y referencias; #1739 depende de política de cuenta de bodega. |
| #1799, #1790, #1786, #1774, #1749, #1567, #1592, #1539 | #1708 candidato | Estado/transiciones; varias solicitudes requieren definir política o ciclo exacto antes de agrupar. |
| #1746 | #1717 candidato primario; #1708 secundario por consecuencia | Dos sondas SQLite independientes confirmaron que `_approval_rule_from_form()` persiste min 500 > max 100 y el motor devuelve nivel 0 para 250. El defecto primario es aceptar rango/nivel inválido server-side; confirmar con desarrollador que el alcance de #1717 incluye invariantes entre campos de una matriz. |
| #1773 | #1656 | Guard de período cerrado. |
| #1547 | #1714 primario; #1709 secundario solo para subcaso histórico | Saldo canónico aplicado vs. corte `reversed_at`; no atribuir todo el issue al corte. |
| #1745, #1744, #1297 | #1707 candidato | Resolución canónica de reglas/templates fiscales. |
| #1793, #1763 | #1655 candidato | Conversión y edición de tasas; #1763 requiere inspección del manejo del duplicado. |
| #1759, #1757, #1758, #1727, #1726 | #1715/#1716 candidatos | Base/ponderación y capitalización de landed cost; #1758 depende de criterio de asignación. |
| #1737 | #1651 candidato | Canonización/conversión UOM. |
| #1704, #1227, #1547 | #1714 candidato | Clasificación advance/open item y saldo aplicado. #1704 no encaja con el comentario actual a #1657. #1207 se separa: el issue y la reproducción actual refieren a saldo derivado/cache (#1657). |
| #1780, #1782, #1743, #1740, #1514, #1390 | #1711 candidato | Contratos visuales, CSRF, traducción y zona horaria local; #1514/#1390 parecen mismo cluster. |
| #2012 | #1711 candidato | Alta; los forms vacíos de matching de compras/ventas no hidratan su configuración existente y al guardar defaults visibles resetean matching, tolerancias y flags; evidencia HTTP con CSRF válido. #1567 cubre aparte el guardado parcial ante aprobación. |
| #2014 | #1711 candidato, `needs-review` | Alta en repro: botón de borrado visible de TaxRule genera 500 porque el guard sensible bloquea `session.delete`; decidir borrado auditado, inactivación o retirar acción. |
| #2021 | #1711 candidato | Baja: `usuario_companias.html` re-renderiza HTTP 200 ante choice inválido sin mostrar `form.errors`; POST con CSRF válido conservó la asignación. Comentario a #1711 `6679672907`; #1700 cubre el fallo distinto al reemplazar filas existentes. |
| #2022 | #1711 candidato | Alta: curl en locale EN confirmó el botón `accion` del CRUD usuario en español aunque el encabezado se traduce; #1740 cubre mensajes de error y es una superficie distinta. Issue abierto `needs-work`; asociación raíz no confirmada. |
| #2023 | #1710 candidato | Alta: con SMTP ausente, curl produjo error de envío, pero dejó `PasswordResetToken.consumed=False`, consumió el enlace anterior y no creó EmailQueue; el mensaje externo sigue genérico. Comentario al root `6680192947`; asociación causal candidata, sin cambiar el estado `needs-review` del root. |
| #1680, #1730, #1784 | #1653 candidato | Ediciones/reintentos concurrentes y atomicidad; #1784 además puede tener dimensión FX (#1655). |
| #1617 | #1713 candidato | Duplicar factura/remisión conserva origen pero omite relaciones `DocumentRelation` por línea que exige submit; el root hoy cubre matching/consumo pendiente, ampliar a creación/preservación en duplicación requiere aprobación. Comentario al root: #6661648378. |
| #1798, #1618 | #1658 candidatos | Duplicadores de órdenes/facturas omiten campos persistidos (descuento, bodega); causa candidata de flujo de copia incompleto, distinta de identidad `DocumentRelation`. |
| #1508, #1644, #1721, #1470 | Sin root confirmado | Conflicto/ambigüedad de conciliación; candidato cluster, validar política fail-closed. |
| #1504, #1509, #1080 | Sin root confirmado | Asociación de regla tras selección de candidato; separar de conflicto ambiguo. |
| #1522, #1220, #1138 | Sin root confirmado | Duplicidad probable de límite monetario/cantidad en devoluciones; política `needs-review`. |
| #1537, #1476 | #1718 candidato; duplicado probable | Importación de Party pierde `grupo`/`clasificacion`; #1718 permanece provisional hasta definir el mapping esperado. |
| #1559, #1434 | #1708 candidato | Duplicidad probable: dashboard trata pedido cerrado como abierto; #1709 no describe estado actual. |
| #1555, #1483, #1612 | Sin root confirmado | Ceros tratados como ausencia en subsistemas distintos; #1556 se separa como selección visual del lado de movimiento bancario, candidato #1711; #1612 no es coerción Decimal (#1650). |
| #1551, #1556, #1550, #1729, #1620, #1619, #1564, #1563, #1731, #1738, #1630, #1748 | Sin root confirmado | Issues consultados con candidato no demostrado; revisar uno a uno en sus módulos y no forzar raíz. #1798/#1618 quedan candidatos #1658 por copia incompleta; #1617 es candidato #1713 por relaciones de línea. |

**Comentarios/root discrepantes detectados en el lote:** #1798→#1659 y #1617→#1798 citan issues normales, no roots; se reclasifican localmente #1798/#1618 como candidatos #1658 y #1617 como candidato #1713. #1787→#1770 y #1742→#1688/#1791 también citan issues normales; #1704→#1657 no coincide con clasificación open-item; #1612→#1650 confunde truthiness de cero con Decimal; #1559/#1434→#1709 confunde estado actual con corte histórico. Este cotejo no cambia etiquetas; #1713 recibió comentario de candidato y límites.

La auditoría debe seguir agregando módulos y conciliando los issues abiertos antes de actualizar los cuerpos/tablas de hijos de los root issues. Las asignaciones de confianza baja/media requieren validar mecanismo y duplicados; los asuntos `needs-review` no deben convertirse en fixes propuestos sin decisión del responsable.

## Lote #1801–#1911 consultado por GH (candidatos por mecanismo)

Los 41 IDs que faltaban en la mención del mapa fueron consultados individualmente con `gh issue view`. Ninguno tiene etiqueta `root`/`causa-raiz`; lo siguiente son agrupaciones candidatas tomadas de issue bodies/comments, pendientes de validación por código. No cambiar labels `needs-review`.

| Issues | Root candidato | Confianza / pendiente |
|---|---|---|
| #1885, #1855, #1844, #1842, #1843, #1814, #1808 | #1711 | Alta para i18n/UI/contrato frontend; #1844 requiere verificar chain del sample renderer. |
| #1856 | #1711; #1655 secundario | Media; formateador de moneda inválida puede romper render. |
| #1883 | #1711 | Alta para presentación de compañía/fondo/moneda en conciliación, no lógica del saldo. |
| #1852, #1845, #1828 | #1649 | Alta para permiso/ACL; #1845 ya tiene issue específico auditado. |
| #1823 | #1649; #1716 secundario | Alta para compañía; estado activo del proveedor es guard distinto. |
| #1886, #1822, #1818 | #1655 | Alta para mezcla/pérdida de moneda y tasa en flujos multimoneda. |
| #1860 | #1719 | Alta para árbol relacionado sin ciclo/profundidad y nodos huérfanos. |
| #1849 | #1706 candidato | Media-alta; downgrade de hash v2, confirmar si downgrade se soporta por contrato. |
| #1733, #1751 | #1706 candidato | Falta evento de auditoría en writers (consultados en lotes previos, completar evidencia). |
| #1805 | #1706 candidato | Media; snapshot histórico de `customer_name` depende de política de persistencia. |
| #1809, #1804, #1812 | #1708 | Alta para estado sin efecto/guard de transiciones/dependencias; #1812 también cruza vínculo #1713. |
| #1816 | Sin root confirmado; #1656 candidato | Media; cuando el POST no incluye IDs, la ruta redescubre plantillas ya aplicadas y vuelve a rechazar duplicados. Replay secuencial, distinto del paso parcial `pending` de #1152/#1776; no es saldo derivado #1657. #1653 solo sería aplicable si su contrato se amplía más allá de la carrera concurrente descrita por el root. |
| #1830 | #1709 candidato | Alta si el saldo de vales abiertos debe respetar corte as-of y estado posterior. |
| #1821 | #1714; #1708 secundario | Media; draft de nota de crédito consume capacidad por relación activa, validar regla de negocio. |
| #1837 | #1714 candidato | Media; `needs-review` debe resolver inclusión de filas GL sin party/book. |
| #1802 | #1713 | Alta; tipo de fuente de `DocumentRelation` no coincide con línea fuente efectiva. |
| #1836 | #1653 candidato | Alta en mecanismo; `needs-review` exige contrato de replay con misma clave y distinto payload. |
| #1815 | #1653; #1656 secundario | Alta; clave de idempotencia usa nombre mutable del período. |
| #1819 | #1654 candidato | Media; writer permite posteo vacío; confirmar si el root cubre libro activo y requisito GL. |
| #1528, #1677, #1765 | #1718 candidato | Alta para ejecución, invalidación de catálogo y parser CSV en importaciones. |
| #1866, #1831, #1813 | #1717 candidato | Alta: validación de input/negocio; #1813 no exige DeliveryNote en matching 3-way. |
| #1832 | #1717 candidato | Media; confirmar si rango de tolerancia <7 se debe aceptar o aplicar. |
| #1806 | Sin root confirmado | Cero tratado como ausencia y signo de withdrawal; candidato a agrupar con #1555/#1483/#1612 solo después de confirmar mismo mecanismo. |
| #1735 | #1710 candidato | Media; desactivar verificación de email sin SMTP, revisar contrato operativo. |
| #2013 | #1710 candidato | Alta en defecto: con 60 segundos exactos restantes la UI muestra 2 min por `seconds // 60 + 1`; verificar redondeo de lockout. |
| #1839 | #1710 candidato | Media; estado/token de confirmación pública; revisar transición ordinaria vs carrera. |
| #1882 | #1658 candidato | Alta si HEAD confirma template de import sin callers; conservar `needs-review` para decisión de retiro. |
| #1851 | Sin root confirmado | La URI `postgresql://` sí se normaliza a pg8000; el fallo por defecto se reprodujo por `DB_PASSWORD` vacío en PostgreSQL 16. Se comentó evidencia en #1851; deduplicar el mecanismo de configuración antes de asignar root. |
| #1853, #1840, #1833 | Sin root confirmado | Configuración de lint/test o issue compuesto; no agrupar como causa funcional sin descomponer. |

Discrepancias relevantes: #1852 cita #1783, #1855 cita #1659, #1843 cita #1838, #1802 cita #1756 y #1851 cita #1658; esos destinos no son roots o no encajan con la causa. #1564 queda bajo #1719 solo si el root incluye paginación fija; #1830 es candidato #1709 y requiere validar el corte histórico del modelo. En #1912 se confirmó en runtime el keyword incompatible `required_permission` del menú admin frente a la firma `module_badge(required=...)`; se creó el hijo y se comentó #1711 (`#issuecomment-6649923615`).

## Issues aún sin mención, consulta puntual #332–#1767

Se consultaron estos 16 issues abiertos antes ausentes del mapa; ningún issue hijo tiene label root/causa-raíz. Las asignaciones son candidatos sobre el mecanismo descrito en GitHub, no evidencia independiente del árbol salvo cuando el propio issue ya incluye una reproducción validada.

| Issue | Root candidato | Confianza / clasificación |
|---|---|---|
| #332 | #1653 | Alta para race de INSERT de StockBin sin relectura/savepoint tras UniqueViolation; la parte ACL histórica se reporta corregida y se excluye. #1868 es distinto (fila ya existente/identity map). |
| #444 | #1708 | Media; estado de SerialNumber tras reversas de transferencia, valores/cantidades se revierten. No asignar a #1715 (valuación). |
| #547 | #1718 candidato primario; #1717 secundario; vínculo citado a #1652 en comentario actual | `needs-review`; el residuo es validar moneda existente/activa en adapter, no parser/shape tabular de #1652. No asignar a #1716 solo porque intervenga `Currency.active`. |
| #647 | Sin root actual | Reapertura: validadores GL toleran discrepancia `0.0001`; #1655 no encaja (no es FX). Falta paraguas para invariante de balance común a writers GL. |
| #841 | #1651 | Alta; edición vuelve a interpretar cantidad base como UOM comercial y reconvierte (crear ya se había corregido). |
| #1150, #1492 | #1717 candidato; duplicado causal confirmado por cuerpo y código | Alta; `validate_template_balance` solo iguala sumas; acepta importes negativos o débito y crédito positivos en una línea. Aplicación elige débito si es positivo y pierde crédito, pudiendo producir diario desbalanceado. Repro temporal del servicio confirma recorrido `pending`; no hay suite dedicada. |
| #1318 | #1658 | Alta, asociación ya explícita en comentarios: función de backfill bancario sin caller; integrar o retirar según decisión del root. |
| #1587 | Sin root actual | `needs-review`; umbral visual y shortage usan prioridad distinta reorder/min. Probable mismo asunto que #1349, sin fijar política. |
| #1681 | Sin root actual | `needs-review`; unicidad global de códigos choca con aislamiento por compañía; decidir identidad global vs. company-scoped. |
| #1723 | Sin root confirmado | Checkbox ausente se interpreta como activo; #1717/#1711 son vecinos, ninguno expresa exactamente semántica de checkbox ausente. |
| #1732 | #1710 | Alta; sesión Flask sigue viva tras desactivar usuario. Nueva sonda SQLite/Flask confirma el mismo bypass en `GET /portal/customer` (`active=False`); extensión comentada en el hijo, sin root nuevo. |
| #1734 | Sin root actual | Cardinalidad de mappings de contador no está definida; `scalar_one_or_none()` falla si hay varias filas. Política N:1 vs N:M pendiente. |
| #1752 | #1711 | Alta; enlace “Editar” apunta a endpoint de alta que ignora el ID. |
| #1755 | #1717 | Alta; proveedor de devolución puede diferir del proveedor de recepción origen y no se valida al guardar. |
| #1760 | #1717 | Alta; `from_invoice` es opcional en service aunque la columna sea requerida; acaba en IntegrityError. |
| #1766 | #1717 candidato | Media; el alta de moneda permite múltiples `default=True`; validar si root incluye invariantes cruzadas de CRUD y si la semántica exige singleton. |
| #1767 | Sin root actual | `needs-work`; dos QA independientes reprodujeron por POST autenticado editar al único admin activo a `classification=system` y dejar cero admins. Protección del último administrador es una política de continuidad/recuperación. #1710/#1732 son adyacentes pero no raíz suficiente. |

Los asuntos no asignados conservan motivo explícito y, cuando corresponde, `needs-review`; no crear roots genéricos que mezclen cardinalidad, continuidad de administrador, balance GL y políticas de stock.

## Cotejo de referencias no normalizadas #1501–#1917

Revisión de los issues con `Refs:` a root en su cuerpo que no tenían fila granular, separando causa funcional de referencias de bloqueo y conservando decisiones pendientes. No se actualizaron etiquetas ni se cerraron issues.

| Issue hijo | Root principal/secundario candidato | Mecanismo y límite |
|---|---|---|
| #1807 | #1708 candidato | El certificado emitido aparece como dependencia activa de su propio pago y bloquea anulación antes de llamar su cancelador; confirmar contrato de transiciones/cancelación cruzada. |
| #1841 | #1658 candidato | Inventario de código sin consumidor; incluye `accounting_engine/fiscal/resolver.py::RuleResolver`, sin imports/instancias/calls/tests locales y no exportado por `fiscal.__init__`. Flujo activo usa `tax_rule_service`; falta confirmar contrato externo antes de retirar. `query_tools` sigue excluido por API de plugins. |
| #1869 | #1711 primario; #1655 secundario solo si la vista también mezcla bases monetarias | Los listados omiten la divisa transaccional; es presentación, no falla del resolver. Comparativos excluidos expresamente. |
| #1906 | #1711 candidato | Template de adjudicaciones muestra `supplier_quotation_id` bajo columna “Proveedor”; falta nombre humano en el payload/UI. |
| #1912 | #1711 candidato, requiere reconciliación | El issue afirma que `admin.html` pasa `required_permission`, pero el archivo en HEAD `85eed67b` usa `required=link.required_permission`, compatible con la firma; un escaneo Jinja de 134 callsites no encontró keywords incompatibles. Se comentó evidencia actual y no se cambió etiqueta ni se cerró; falta que el responsable determine si el issue quedó obsoleto o reporta otra versión. |
| #1913 | #1717 | Forms Profile/Create/Edit aceptan nombre de 81 y teléfono de 51 caracteres frente a columnas PostgreSQL `varchar(80/50)`; comentario amplía las superficies y confirma error de persistencia en vez de validación. |
| #1914 | #1717 | Choices WTForms omiten `purchase_settlement_variance` válido del catálogo; probe confirma rechazo como Not a valid choice. |
| #1915 | #1658 candidato | `base.ods` sin caller/package y con formato legacy; decidir si es dato manual contractual o artefacto a retirar. |
| #1917 | #1710 | Handler envuelve una respuesta Flask `Response` en otro redirect y pierde el destino tras consumir OTP; reproducido en Flask/SQLite. |
| #1918 | #1711 candidato | HTTP con usuario `language=en`: perfil y Portal muestran texto en inglés/Babel `en`, pero `<html lang="es">`. Auth standalone lee `session.lang` sin writer; perfil y `portal/base_portal.html` fijan español. QA confirmó extensión a portal; mismo defecto, no duplicado. Root frontend/i18n queda candidato. |
| #1919 | #1716 candidato | Dashboard cliente sigue accesible con Party y CompanyParty inactivos; decidir si se revoca acceso a documentos históricos. |
| #1920 | Sin root confirmado | Rol customer redirige a portal pero el guard requiere classification customer y devuelve 403; QA independiente concluyó que #1649 no aplica y #1710 solo comparte tema de roles, no mecanismo. Decidir cuál es fuente de elegibilidad. |
| #1910 | Sin root de producto | Infra de tests PostgreSQL: `str(URL)` redacta contraseña y provoca setup failure; la referencia #1653 es bloqueo para validar concurrencia, no causa de un flujo productivo. |

## Últimos 7 abiertos sin mención (#1771–#1795)

| Issue | Root candidato | Confianza / clasificación |
|---|---|---|
| #1771 | #1717 | Alta; edición de entidad omite guard para desactivar la única entidad Desktop. |
| #1775 | Sin root confirmado | Media; cambiar `Book.entity` deja reglas activas huérfanas/aparentemente activas pero no aplicables. #1649 no explica el síntoma (no se demostró bypass de compañía); #1717 es solo candidato si se decide validar transición de referencias. Separada de la carrera de alta concurrente registrada bajo #1653. |
| #1776 | Sin root confirmado; #1656 candidato | `needs-review`; aplicación exitosa queda `pending`, el wizard la vuelve a enviar y servicio la rechaza; definir recuperación/no-op y si el check puede pasar antes del posting. #1653 es débil porque no se reprodujo carrera concurrente. Cancelación de plantilla sin guardas/bloqueo requiere decidir política separada. |
| #1785 | Sin root actual | El filtro approved existe en selector UI, no en POST/reporte; falta paraguas para validación de consulta. |
| #1792 | #1711 | Alta; paginación/status de notas usa endpoint/doctype de devoluciones. |
| #1794 | #1653 candidato de confianza baja-media | `log_create` fuera de la transacción del documento pierde evento; no asignar #1706 (la evidencia nunca queda persistida, no se altera evidencia existente); verificar si #1653 abarca atomicidad distinta a read-then-post. |
| #1795 | #1719 candidato; #1711 secundario | CTA/form no transporta el documento fuente obligatorio; #1223 citado no es root ni el mismo síntoma. |

## Reconciliación de IDs

El siguiente bloque es histórico (corte de 955 IDs abiertos, 24 roots/931 code); la cuenta vigente de 1002 IDs está en el encabezado de este mapa. En ese corte, #1945 omitía `voucher_id` en liquidación de caja chica y #1946 exige un ID técnico de banco sin selector; ambos son candidatos #1711. #1947 reproduce HTTP 500 en edición RFQ inválida y es candidato #1717; confirmar rollback/atomicidad antes de asignar. #1916 (`WorkflowActionLog`) se asigna provisionalmente a #1658 por falta de consumidores, con #1706 secundario por la inmutabilidad declarada. #1917 se agrupa bajo #1710 por la redirección defectuosa tras OTP; #1918 queda candidato #1711 por locale/lang; #1919/#1920 requieren política de elegibilidad; #1921 es hijo confirmado de #1711; #1922 requiere decidir semántica mensual; #1923 es open redirect independiente; #1924 no tiene root actual para flags booleanos; #1925 es error de impresión tipo no registrado. #1833 es compuesto: el flujo GL incompleto es candidato #1658 y el guard de autenticación no aplicado en GET es candidato secundario #1649; la sonda no observó lectura/escritura de comprobantes. No confundir #1945 con la carrera backend #1266/#1187.


Corte histórico previo a #1913–#1917: los 912 IDs abiertos aparecían al menos una vez. En el corte vigente, los **991/991 IDs de `ISSUE.md` aparecen en el mapa** (reconciliación local por ID, 2026-11-06, tras #1994). Esto mide menciones, no asignación causal: candidatos de root, duplicados y asuntos sin decisión permanecen provisionales o sin asignación con motivo; validar por código y respetar `needs-review` antes de actualizar relaciones externas.

## Nuevo issue verificado

- [#1913](https://github.com/cacao-accounting/cacao-accounting/issues/1913): longitud no validada en ProfileForm excede límites `String(80/150/50)` del modelo; la sonda Flask acepta 81 caracteres y PostgreSQL 16 rechaza `varchar(80)`. Candidato a #1717 por validación server-side; root conserva `needs-review`. Refs: #1717 #757. Comentario con reproducción se dejó en el root (#1717).

## Issues agregados en este checkpoint

- [#1914](https://github.com/cacao-accounting/cacao-accounting/issues/1914): `purchase_settlement_variance` está en los CSV/mappings y `default_accounts.py`, pero falta en `ACCOUNT_TYPE_CHOICES`; agrupación candidata bajo #1717, root mantiene `needs-review`. Refs: #1717 #757.
- [#1915](https://github.com/cacao-accounting/cacao-accounting/issues/1915): `base.ods` no tiene caller, no se empaqueta y difiere del CSV activo; candidato a dead data #1658, requiere decidir contrato manual. Refs: #1658 #757.

## Adjudicación canónica #1501–#1917 — 2026-11-05

El rango incluye 411 issues abiertos: 24 roots y 387 hijos. El cotejo distingue asignaciones explícitas, candidatas y sin root; no convierte una mención o un comentario en causa confirmada por código. Con los 16 IDs antes sin fila granular adjudicados abajo, el recuento disjunto de trabajo es: **24 roots + 256 hijos con root explícito + 78 candidatos a root + 53 sin root confirmado = 411**. `needs-review` y las dudas de política permanecen.

### IDs sin fila granular previa

| Issue | Root primario/secundario candidato | Motivo y límite |
|---|---|---|
| #1561 | #1656 candidato débil | Gráficas agrupan meses de años distintos; #1709 no es corte as-of. Falta root específico de granularidad de reportes; validar si #1656 cubre periodo de presupuesto/reporte. |
| #1580 | Sin root confirmado | Prefijo de numeración externa; no asignar por proximidad a identidad o numeración interna. |
| #1350, #1584 | #1656 candidato | Mes inválido en retención cae silenciosamente al actual; misma causa, según revalidación de QA. |
| #1611 | #1712 candidato | Cambio de artículo conserva estado batch/serial anterior; validar sincronización de respuesta/formulario. No asignar a #1716 sin demostrar guard de uso. |
| #1629 | #1717 / #1651 / #1652 candidatos | Import de series/cantidades mezcla validación de dominio, UOM y contrato lector; conservar `needs-review` hasta separar causa primaria. |
| #1679 | Sin root confirmado | Degradación del token al fallar Redis; mecanismo distinto del cache de Party #1900 y de no-dependencia de cache. |
| #1703 | Sin root confirmado | Colisión de número visible/ULID; requiere confirmar si es representación, unicidad o concurrencia. |
| #1720 | #1716 candidato débil | Checkbox crea entidad inactiva; creación de estado inactivo no es el guard de uso del root. |
| #1742 | #1717 candidato | Validación numérica/fechas; sus referencias #1688/#1791 no son roots. Mantener vínculo provisional. |
| #1762 | Sin root confirmado; #1710 candidato débil | POST HTTP/SQLite confirma que el contador se revierte a 0 al desmontar sesión. Es fallo secuencial; no confundir con la carrera de #1696 ni doble aceptación #1000. QA independiente observa que el mecanismo no coincide claramente con el body de #1710; dejar `needs-review` de alcance sin asignación final. Repro y comentario en el issue. |
| #1770 | Sin root confirmado | Lectores de entidad default sin causa compartida suficientemente demostrada. |
| #1783 | Sin root confirmado | Variaciones presupuestarias; falta una raíz que describa el mecanismo común. |
| #1801 | Sin root confirmado | Mensaje de éxito tras rollback; no asignar a #1653 solo por el término rollback. |
| #1817 | #1707 candidato | Corrector de proforma del motor fiscal se escala doble bajo FX; root contable cercano #1707, confirmar alcance/causa. |
| #1820 | Sin root confirmado | Reserva de órdenes cerradas; no agrupar con #1713/#1716/#1717 por afinidad de módulo. |
| #1824 | #1707 candidato | `needs-review`: el builder omite errores inyectados en recálculo secundario (fault injection lo confirma), pero las condiciones actuales de FiscalEngine/SettlementEngine parecen invariantes entre monedas y no se reprodujo un error exclusivo del libro alterno; impacto funcional no confirmado. |

### Normalización de root primario/secundario

| Issue hijo | Root primario | Root secundario / dimensión | Nota |
|---|---|---|---|
| #1515 | #1719 | #1649 | Destinos/source permitidos en árbol y flow; ACL/company ownership como factor secundario. |
| #1971 | #1649 | — | `GET` del formulario de cotización carga y serializa nombre/compañía de `SalesRequest` cross-company antes de validar acceso al origen; sin lectura de líneas reproducida. |
| #1972 | #1650 | — | `Decimal('NaN')` en monto de conciliación bancaria escapa como `InvalidOperation` antes del try/except; reproducción focal en `test_request_context`, no HTTP autenticado. |
| #1973 | #1658 candidato | — | `transaction_grid()` declara `source_label`, `items_disponibles`, `uoms_disponibles` y `warehouses_disponibles`, pero no consume esos cuatro argumentos; los callers sí los pasan. No se probó efecto en el flujo de carga; resolver contrato integrando o retirando en pase coordinado. |
| #1532 | #1718 | #1652 | Import agrupado/paridad de contexto; lectura tabular solo dimensión secundaria. |
| #1545 | #1655 | #1714 | Tasa FX en aplicación posterior; open-item es dimensión secundaria. |
| #1547 | #1714 | #1709 | Saldo aplicado primario; corte `reversed_at` secundario. |
| #1811 | #1711 | #1655 | Interfaz/selector como problema primario; moneda como factor contextual. |
| #1815 | #1653 | #1656 | Atomicidad/reintento primario; cierre de periodo como condición secundaria. |
| #1821 | #1714 | #1708 | Aplicación/open-item primaria; transición documental secundaria. |
| #1823 | #1649 | #1716 | Scope de entidad primaria; vigencia de entidad secundaria. |
| #1856 | #1711 | #1655 | Contrato de interfaz/moneda presentada como principal; mantener tema FX secundario. |
| #1861 | #1711 | #1655 | Vista/contrato visual primario; moneda como dimensión secundaria. |
| #1865 | #1706 | #1713 | Mutación/borrado de relación append-only primario; identidad de línea secundaria. |
| #1872 | #1708 | #1657; #1711 solo para subhallazgo visual | Transición de cancelación primaria; estado/cache derivado secundario. UI solo si el criterio pide un tercer subhallazgo. |
| #1889 | #1711 | #1713 | Contrato de vista/relación como problema principal; identidad de línea como contribuyente. |
| #1916 | #1658 | #1706 | WorkflowActionLog sin caller/writer/reader es primero código sin uso; append-only secundaria por semántica declarada. |
| #1380 | #1711 | #1655 | El selector conserva tasa del par de monedas anterior; UI/estado stale primario, validar la tasa nueva en backend secundario. |
| #1427 | #1711 | #1655 | La conciliación de compras omite código de moneda; formato visible, sin mezcla de valores confirmada. |
| #1869 | #1711 | #1655 solo si la vista mezcla bases | Listados comerciales omiten moneda transaccional; alcance distinto de comparativos #1942. |
| #1943 | #1711 | #1707 | El cliente no comunica errores devueltos por preview fiscal; el engine/contrato de errores es secundario. |
| #1378 | #1711 | #1655 | El árbol de flujo mezcla allocated_amount documental con currency del pago; extensión HTTP en `bancos/pago.html`: pie de referencias vuelve a sumar allocated_amount y rotularlo con la moneda del pago (#1378 comentario `6682287085`, root #1655 `6682287380`). Contrato de presentación primario; en referencias con varias monedas, el agregado nominal tampoco es comparable. |
| #1438 | #1711 | #1655 | Formulario omite moneda funcional/trasacción y el preview cae en fallback; UI primario, conversión secundaria. |
| #1594 | #1711 | #1655 | El motivo de excepción se calcula en UI con tarifa nominal, mientras backend usa moneda funcional. |
| #1382 | #1650 | #1655; #1652 | Tasa 0 se trata por truthiness como ausente; coerción/validación es primaria, importación es dimensión secundaria. |
| #1440 | #1657 | #1655 | El neto GL agregado de varios pagos se reutiliza por pago; saldo derivado primario, FX downstream. |
| #1223, #1224 | #1719/#1717 candidatos | #1655 | Enlace de origen incorrecto es el mecanismo; la moneda puede agravar, pero no lo causa. Requiere validar root primario. |
| #1427, #1861, #1869 | #1711 | #1655 | Omisión de moneda en UI. Mantener issues separados por pantalla/superficie; no consolidar sin caller común. |
| #1943 | #1711 | #1707 | POST autenticado del preview con reglas circulares reprodujo HTTP 200, `errors` y cero líneas; cliente omite el error según revisión estática (sin prueba de navegador). El engine/contrato de errores es dimensión secundaria. |
| #1944 | #1711 candidato | Alta | GET HTTP de lista con `ItemCategory` existente devuelve 200 pero la celda Categoría muestra `-`; handler no carga relación y Jinja usa literal constante. Es presentación incompleta, no la validación del selector #1850. |
| #1945 | #1711 candidato | Alta | El formulario Jinja de gasto no transporta `voucher_id` que el handler necesita; al enviar “Liquidar” se registra gasto suelto y el vale sigue entregado. La UI y handler discrepan; distinto de carrera de backend #1266/#1187. |
| #1946 | #1711 candidato | Alta | Reposición requiere pegar un `bank_account_id` técnico en texto sin mostrar cuentas disponibles; el usuario no puede descubrir una cuenta válida desde el flujo aunque el backend sí valida pertenencia, vigencia y moneda. |
| #1947 | #1717 candidato | Media-alta | POST de edición RFQ draft sin líneas deja escapar `DocumentFlowError` como HTTP 500, mientras las altas y edición PR capturan error equivalente. QA retiró la sesión SQLite antes de volver a consultar y confirmó rollback de cabecera, línea y relación; no se reproduce pérdida durable ni ruptura de atomicidad. Defecto confirmado: el 500 no capturado; el comentario del issue sobre borrado previo no demuestra pérdida persistida. |
| #1975 | #1711 candidato | Baja, HTTP confirmado | La fila vacía de `caja_chica_lista.html` declara `colspan=8` para tabla de nueve columnas; issue abierto con `Refs: #1711 #757`. |
| #1949 | #1711 candidato | Alta | Lista y detalle presentan `paid_amount` para todos los PaymentEntry; `receive`/`credit_note` guardan el saldo en `received_amount`, y el detalle también traduce ambos a “Pagar”. El writer actual confirma que son filas válidas; defecto de presentación del importe/dirección. |
| #1950 | #1711 candidato | Alta, reproducción HTTP confirmada | Tres formularios Jinja de administración hacen POST sin token CSRF con Flask-WTF global activo: sin token responden 400 y con token válido llegan al handler y persisten. El caso coincide con el contrato de interfaz/CSRF de #1711; tres vistas no estaban cubiertas por #1743. |
| #1951 | #1711 candidato | Alta, reproducción HTTP/SQLite confirmada | POST inválido de Cash Forecast devuelve 200 con formulario vacío porque la ruta no reenvía el formulario rechazado; se pierden versión/descripción. Síntoma análogo a #1884/#1901, pero no se presume mismo fix; confirmar alcance de retención de estado en root #1711. |
| #1952 | #1717 candidato; #1656 secundario | Alta, HTTP/SQLite reproducido | Rango fiscal invertido en setup devuelve 500; al retirar sesión no persiste Entity/FiscalYear. Validación de entrada primaria, invariante de período secundaria. |
| #1974 | #1717 primario; #1656 secundario | Alta, HTTP/curl/SQLite efímero | `POST /accounting/fiscal_year/new` con 2026-12-31..2026-01-01 responde 302 y persiste `FiscalYear` invertido. #1952 es setup (500 con rollback); #1941 es `AccountingPeriod`. |
| #1953 | #1711 candidato | Alta, locale es reproducido | `_COLUMN_LABELS` usa msgids ingleses; encabezados de reportes operativos permanecen en inglés. |
| #1954 | #1656 candidato | `needs-review` | Rango de 18 meses genera 12 períodos y extiende el último por siete meses; requiere definir duración máxima del ejercicio fiscal. |
| #1955 | #1656 primario; #1711 secundario | `needs-review`, HTTP/SQLite reproducido | Fechas libres editables en Kardex/bancos se rechazan como 400 al no coincidir con límites de período. Decidir períodos completos vs cortes diarios. |
| #1948 | Sin root confirmado | Alta | `WTForms.Email` invoca un validador que depende de `email-validator`, ausente en ambos manifiestos de instalación; el formulario sí se ejecuta, por lo que no es código desconectado (#1658) ni el defecto de dominio de #1717. Probar otros casos del mecanismo antes de proponer un root de dependencias runtime no declaradas. |

Esta matriz resuelve el orden de causa para estos cruces; las filas de agrupación por root pueden seguir mostrando una causa secundaria. Los títulos/IDs abiertos se toman de `ISSUE.md`, sin consultar el listado remoto ni modificar etiquetas en GitHub.

### Solapamientos revisados en multimoneda

| Grupo | Evaluación | Tratamiento local |
|---|---|---|
| #1114 / #1235 | Probable duplicidad de mecanismo y caller: parámetro de moneda no coincide con moneda de libro en la matriz de conciliación. | Mantener ambos abiertos hasta cotejar alcance/criterio del root. |
| #1121 / #1251 | Saldo final de banco en moneda de libro etiquetado con moneda de cuenta; ambos apuntan al mismo resumen. | Tratar como grupo candidato de un arreglo, conservar tickets separados hasta definir si son duplicados exactos. |
| #1560 / #1597 / #1607 | La misma suma de GL en moneda base recibe etiqueta de moneda bancaria en dashboard/`get_banks_data`. | Duplicidad de mecanismo probable; validar callers y alcance antes de fusionar. |
| #1016 / #1281 | Solapamiento fuerte pero no idéntico: falta propagar moneda desde endpoint/caller vs resolver/validador que ignora moneda de lista. | Mantener separados como capas del flujo; candidato a subcaso/duplicado al confirmar alcance. |
| #1233 / #1325 | Solapamiento parcial: pronóstico manual sin tasa vs omisiones silenciosas con cobertura adicional de AR/AP. | Mantener separados; probar si el arreglo común cubre ambos. |
| #1078 / #1594 | Comparten recomendación por moneda funcional, pero uno es excepción de adjudicación backend y el otro la justificación del frontend. | Relacionados, no duplicados. |
| #1427 / #1861 / #1869 / #1942 | Omisión de moneda en conciliación de compras, inventario, listas y comparativos. | Causas de presentación relacionadas; mantener issues separados por superficie/caller. |

## Adjudicación canónica #901–#1500 — 2026-11-05

El rango contiene 493 issues abiertos (#901–#1200: 199; #1201–#1500: 294). La mención previa no implica asignación causal. Las propuestas siguientes quedan como candidatas o sin root; conservar `needs-review` hasta validar el mecanismo en código y el alcance del root.

### Candidatos sin asignación primaria previa

| Issue | Root candidato / estado | Evidencia y límite |
|---|---|---|
| #1049 | #1708 candidato | Transición documental; confirmar alcance del root. |
| #1050 | #1650 candidato | Relación de registro contable; candidato, no confirmado. |
| #1053, #1147 | #1713 candidatos | Linaje/referencia de líneas contables; mantener sin asignación final. |
| #1161 | Sin root primario | Posibles dimensiones #1714/#1708/#1657; evidencia insuficiente para elegir. |
| #1163, #1386 | Sin root confirmado | No hay mecanismo común suficientemente respaldado. |
| #1165 | #1716 candidato | Vigencia/uso de entidad; comprobar contrato del root. |
| #1177 | Sin root primario | Referencias existentes no establecen mecanismo causal. |
| #1179 | Sin root de producto | Infraestructura de tests; no forzar agrupación funcional. |
| #1194 | Sin root primario | Posible interacción con aprobación/conciliación; falta mecanismo único. |
| #1248 | #1709 candidato | Consulta de saldo/corte histórico; validar alcance. |
| #1262, #1389 | #1652 candidatos, `needs-review` | Contrato de datos/tabular; conservar criterio pendiente. |
| #1272 | Sin root primario | Root no determinado con evidencia disponible. |
| #1313 | #1708 primario | Corregir #1658 previo: mecanismo es transición documental. |
| #1351 | #1709 primario; #1657 secundario candidato | As-of primario; saldo derivado solo dimensión secundaria. |
| #1377 | #1714 candidato | Posible duplicado de #1585; confirmar contrato de open-item. |
| #1406 | #1707 o #1713, separar mecanismos | Fiscalidad y linaje de líneas son causas distintas; no consolidar sin subcasos. |
| #1466 | Sin root confirmado | No hay root causal suficientemente preciso. |
| #1496 | #1717/#1649 candidatos, baja confianza | Validación de entrada o scope; mantener `needs-review`. |
| #1664 | Sin root confirmado (retirar vínculo provisional #1718) | Inyección de fórmulas por LF inicial que el sanitizador de exportación CSV no neutraliza; el importador solo aporta la fuente controlable, no es la causa del escape de salida. Mecanismo de exportación/salida requiere root específico o revisión transversal completa. |
| #1937 | Sin root confirmado | Export PDF de detalle contable usa el fetch paginado de 100 filas mientras CSV/XLSX repiten con `export_all=True`; mecanismo de truncamiento del export, no coincide con un paraguas causal existente. |

### Issues sin root confirmado

| Issues | Disposición |
|---|---|
| #1029, #1036, #1041, #1042, #1051, #1067, #1080, #1081, #1084, #1085, #1088, #1089, #1105, #1118, #1126, #1128, #1129, #1138, #1151, #1193, #1220, #1234, #1246, #1264, #1303, #1340, #1344, #1349, #1370, #1371, #1405, #1470, #1483 | Mantener sin root confirmado. Para duplicados/mecanismos específicos, consultar la tabla del lote #1201–#1500; no asignar por similitud superficial. #1080/#1504, #1081/#1509, #1089/#1264 y #1138/#1220 son duplicados probables con mecanismos diferenciados; la política de cada caso sigue `needs-review`. |

### Normalizaciones que prevalecen sobre menciones históricas

- #1461 → #1717 candidato, no #1650.
- #1434 → #1708 candidato, no #1709.
- #1420, #1421, #1402 y #1379 → #1711 como causa primaria/candidata, no #1657; #1379 conserva #1712 como dimensión secundaria.
- #1349 queda sin root confirmado; #1741 no corresponde al mecanismo.
- #1273 y #1313 → #1708, no #1658.
- #1147 → #1713; #1377 → #1714.
- #1004 y #1293 permanecen en #1656, no #1653; #1496 no se asigna a #1713.

El conteo del snapshot de estos rangos es 493 issues. Las tablas documentan decisiones provisionales; no afirman validación por código de los 493 ni autorizan cambios de labels o relaciones remotas.


## Contabilidad: moneda, presupuesto y UI bancaria

| Issue/candidato | Root | Confianza / estado | Evidencia y límite |
|---|---|---|---|
| Revaluación histórica | #1657 / #1709 candidatos | needs-review | Candidato: cálculo incluye pagos y corridas de revaluación posteriores a la fecha `as_of`; resolver contrato canónico de corte antes de asignar raíz final. |
| Período revaluado disabled sin vínculo GL | #1656 candidato | Alta estática; issue existentes #1157/#1158 | Resolver periodo y enumerar IDs usa criterios distintos; posible GL con `accounting_period_id=NULL`. Falta repro HTTP/posteo. |
| Edición tasa usada por conversión inversa/carry-forward | #1655 candidato | Alta | El guard de tasa usada comprueba fecha/orientación exactas, mientras `_closing_rate` permite tasa previa e inversa (#546). |
| Listado revaluación sin compañía | #1649 | Alta | List route omite scope, detail lo aplica; confirmar endpoint runtime por usuario multiempresa. |
| Toggle moneda sin permiso `editar` | #1601 | Alta | Ruta de toggle verifica acceso de módulo pero cambia `active`, a diferencia de edición. Extensión HTTP: `GET /accounting/entity/set_inactive/<id>` muestra acción al usuario solo lectura y solo exige acceso al módulo; viewer con `view=True`, `setup=False` la ejecutó y cambió `Entity.enabled/status`. Mismos decorators en `set_active`/`set_default`; comentario #6669311831. |
| Conteo multilibro de documentos afectados | Sin asignación | needs-review | `affected_documents_count` cuenta drafts por libro; definir si UI cuenta documentos únicos o líneas. |
| `MONETARY_ACCOUNT_TYPES` sin caller local | #1658 candidato | Media | Solo declaración en servicio; revisar contrato importable externo antes de retirar. |
| #1934 | #1711 | Alta | Revalidado por curl: GET real de detalle incluye `x-data="numberingConfig()"` y datos, omite la función y URL de API porque el bloque `scripts` no existe en el layout base. Matriz confirma anon 302, no-role 403, viewer propio 200 y cuenta ajena 403; comentario `6671948017`. #1645 CSRF es defect independiente cuando el script llegue al cliente. |
| #1488 | #1649 | Alta | Import staging se resuelve por `import_id` sin confirmar que corresponda al presupuesto autorizado de URL. |
| Reversas excluidas del reporte/control presupuestario | #1709 candidato | needs-review | Reporte y committed amount excluyen `is_reversal`; confirmar reglas de signo/fecha efectiva antes de asignar. |
| #1202 | #1652 | needs-review del root | Además del camino de presupuesto, el ImportService común normaliza con `dict(zip(columns,row))`; repro actual en HEAD devolvió solo `{'a': '1'}` para encabezado `a` y fila `1, extra`, descartando silenciosamente la celda. Las filas de todos los readers llegan a esa normalización; falta regresión con error por fila. |
| Filtros de presupuesto desconectados | #1658 candidato | Media | Handler no pasa filtros de período/cuenta presentes en la vista; `include_descendants`/`only_variance` no se exponen en UI/caller local. |
| Mensajes de import/reporte sin gettext | #1711 candidato | Media | Literales visibles en errores y mensajes construidos por presupuesto/FX; falta comparar catálogo completo. |

## Auditoría R2R: validación de payload

| Issue | Root | Confianza | Evidencia / límite |
|---|---|---|---|
| #1933 | #1717 | Alta | POST autenticado a `/accounting/journal/new` con `order="not-an-integer"` propaga `ValueError` desde `_normalize_line()`; sonda temporal sobre SQLite, sin persistencia previa a la excepción. |


## CTM: ruta de extractos duplicada/obsoleta

| Ruta/candidato | Root | Confianza | Evidencia / límite |
|---|---|---|---|
| `statement_service.import_bank_statement()` y `suggest_bank_matches()` | #1658 candidato | Alta local, contrato externo pendiente | No tienen caller local; curl anon 302 `/login`, admin `/cash_management/bank-statement/import` 302 a `/imports/new`; usuario sin permiso Imports llega al shim pero el wizard responde 403. El menú sigue al redirect legacy; `extracto_importar.html` no se renderiza. Confirmar contrato URL/API externo antes de retirar. Evidencia #1658 [comentario 6670219127](https://github.com/cacao-accounting/cacao-accounting/issues/1658#issuecomment-6670219127). `apply_bank_matching_rule` y `create_bank_difference_journal` sí tienen consumers. |
| #1507 | #1652 | Alta | QA local reprodujo duplicado exacto en un batch; `seen_in_batch` se usa para excluir filas insertadas previamente. |


| #1957 | #1653 candidato, no confirmado | Alta, fallo inducido | `upload_item_image()` confirma archivo/vínculo antes de persistir `Item.image_path`; el segundo commit fallido deja el Item apuntando a la imagen previa (o a ninguna) y conserva un vínculo/archivo adicional sin instalar. Probe de reemplazo conserva el archivo anterior pero deja dos FileAttachment; la estrategia concurrente actual de #1653 podría no cubrir la compensación entre commits. #1376 es ACL distinta. |
| #1958 | #1710 candidato, no confirmado | Alta, fallo de commit inducido | `_send_document_emails()` entrega antes de confirmar EmailQueue/AuditTrail; commit fallido deja destinatario aceptado sin fila durable. El alcance difiere de retry concurrency #1693; validar la solución de mensajería antes de confirmar root. |




## Issues de la auditoría abiertos en esta ronda

| Issue | Root candidato / estado | Evidencia y límite |
|---|---|---|
| #1959 | Sin root confirmado | `needs-review`: catálogo configurado con todos los Incoterms inactivos cae al fallback estático; probe SQLite mostró EXW disponible/aceptado. Definir contrato antes de root/fix. |
| #1960 | Sin root confirmado | `needs-work`: macro de detalle presenta `batch_id` FK/ULID como número de lote; render real. No asignar #1711 solo por proximidad UI. |
| #1961 | #1711 candidato | `needs-work`: imports Jinja sin `with context` dejan vacío el selector de Incoterms; render real/control positivo. Comentado en root #1711; issue separado del catálogo #1959. |


## Issues nuevos de lotes administrativos — 2026-11-05

| Issue | Agrupación | Estado/evidencia |
|---|---|---|
| #1962 | #1717 candidato; coherencia de checkbox/estado en endpoints | `needs-work`: `is_active` omitido al desmarcar se interpreta como True en `/settings/taxes`, `/settings/tax-templates` y alta de Caja Chica (#comment `6672333357`). La creación default activa puede ser intencional para algunas superficies; el issue original pide decidir el contrato de checkbox antes de consolidar causa. |

| #1963 | #1711 candidato | `needs-work`: la tabla presupuestaria muestra `CacaoConfig.budget_control_action_*` crudo (`do_nothing`/`notify`/`block`); render HTTP confirma. Mecanismo de localización frontend; candidato, no asignación confirmada. |

| #1964 | #1711 candidato | `needs-work`: catálogo ofrecido como inglés contiene 109/217 nombres iguales al español y 64 con expresiones españolas; nombres persisten directamente en Accounts. Mantener separado hasta validar contrato de idioma para dato contable. |

| #1965 | Sin root confirmado | `needs-work`: hash Argon2 almacenado ilegible propaga InvalidHashError y produce 500 en POST /login. Hallazgo de manejo de error; evaluar si existe causa común de normalización/validación de credenciales antes de agrupar. |

| #1966 | #1718 candidato | `needs-work`: company_id JSON como lista alcanza query SQL previa al permiso en /api/line-import/validate y lanza ProgrammingError; repro HTTP/SQLite. Comparte contrato payload/import, validar alcance antes de confirmar. |

| #1967 | #1653 candidato, no confirmado | `needs-work`: escritura parcial deja archivo sin metadatos; falla `os.remove` después del commit y se confirma éxito dejando archivo huérfano. Comparte divergencia DB/filesystem con #1957, pero ventanas distintas; revisar mecanismo de recuperación común antes de asignar root. |


| #1968 | #1711 candidato | `needs-work`: acciones válidas de AuditTrail sin etiqueta en Jinja ni `audit_action_label()` se imprimen como snake_case; render temporal de 33 acciones en ES/EN confirmó que 20/33 caen raw en 18 consumers; asignación candidata, falta regresión permanente. Comentado en root #1711; asignación no confirmada. |

### Configuración SMTP administrativa — validación de entradas (2026-11-06)

| Issue | Root candidato / estado | Evidencia y límites |
|---|---|---|
| #1994 | #1717 candidato | `email_settings.html` guarda `smtp_port=nope` y `smtp_from_email=not-an-email` con éxito; envío posterior falla por puerto sin conexión. Admin/curl/CSRF y loopback SMTP válido probados sin salida externa. Falta confirmar que root #1717 cubra configuración de infraestructura; comentario `6673829033`. |

### Administración — resumen de cuentas predeterminadas (2026-11-06)

| Issue | Root candidato / estado | Evidencia y límites |
|---|---|---|
| #1993 | #1711 candidato | `default_accounts.html` etiqueta el número fijo de definiciones (26) como cuentas configuradas. Probe Flask/SQLite: sin configuración muestra estado vacío; tras asignar solo `default_cash`, el resumen informa 26. Curl admin GET 200; escritura válida persiste; cuenta cross-company y tipo incompatible son rechazados sin mutación parcial; delete elimina configuración. Causa de presentación UI; asociación a #1711 candidata, root sigue `needs-review`. |

| #1969 | Sin root confirmado | `needs-review`: la fecha imposible propaga `ValueError` al handler registrado y el rango invertido retorna cero; no hay dispatcher local que aplique `format: date`; decidir si valida adaptador externo o handler y el contrato del rango antes de asignar causa/fix. |

| #1970 | #1709 confirmado | `needs-work`: probe FX real en noviembre confirma que `get_account_movement_detail` ordinario retorna 0 filas y P&L `income=0`, aunque hay dos reversas activas con efecto -60; `include_cancellations=True` las muestra. Distinto de cierre #1168 y analytics #1582. Root conserva needs-review para contrato histórico global. |
| #1976 | #1711 candidato | `needs-work`: opciones de Smart Select solo escuchan `mousedown`; selección por teclado no ejecuta `selectOption`. Revisión de HTML/JS y suite focal 30 passing sin caso teclado; requiere comprobación browser independiente. |
| #1977 | #1711 candidato | `needs-work`: `fiscal_year` no está registrado; dos selectors de presupuesto reciben 404, mientras el registry define `fiscal_year_id`. Dedupe con #1780 revisado: placeholder Jinja diferente. |


## Bodegas — revisión 2026-11-05

| Hallazgo | Root candidato | Confianza/evidencia |
|---|---|---|
| #1183 — alta persiste código/nombre vacíos cuando WTForms falla | #1717 | Alta: QA reproduce por HTTP/SQLite; se confirmó ruta `inventario_bodega_nuevo()` y condición que permite cualquier POST. #1717 ya agrupa validación omitida. |
| Smart Select sin selección por teclado en alta de bodega | #1711 | Alta a nivel de componente: dos callers de bodega usan el macro que solo enlaza `mousedown`; hijo existente #1976. |
| Lista de bodegas sin link a detalle pese a ruta/template disponible | #1658 candidato | Media: búsqueda local no encuentra caller/link a `inventario_bodega`; no se descarta URL/API externa. No retirar hasta decidir contrato. |
| Listado autenticado sin RBAC responde 200 vacío | #1649 `needs-review` | Evidencia HTTP no mostró filas no autorizadas; definir enforcement 403 vs vacío antes de proponer cambio. |


## Extensiones auditadas — plantillas 2026-11-05

- **#1183 → #1717:** QA revalidó por curl/SQLite que POST de alta de Bodega con code/name vacíos persiste registro; comentario `6671096486`. Tres plantillas de bodega ya están revisadas por cobertura, dejando el defecto abierto.
- **#1976 → #1711:** Bodega llama al Smart Select común sin handler de selección por teclado; las dos invocaciones dependen del componente compartido.
- **#1524 → #1649:** QA extendió por HTTP la falta de permisos a alta/edición de proveedor; editar sin compañía elimina el vínculo previo y deja al usuario comprador sin acceso. Comentario `6671096854`; probe con CSRF desactivado.
- **#1761 → #1711:** curl reprodujo GET/auth/CSRF de Contador externo; corregida referencia antigua a #1648 (que cubre Imports), comentario `6671096192`.
- **Vista de detalle de Bodega sin caller de UI local → #1658 candidato:** ruta/template son activos por URL directa, pero la lista no enlaza filas; confirmar contrato externo antes de retirar. Comentario `6671097265`.

- **#1978 → #1717 candidato; #1282 asociado:** Un link_id de PartyContact perteneciente a otro Party propaga ValueError/HTTP 500 en la ruta de desactivación; el helper detiene la mutación. La ruta análoga de PartyAddress no se probó por HTTP; el defecto abierto es respuesta no controlada, separado del bypass de permisos #1282. Comentario al root #1717: `6671318308`.
- **#1979 → #1716 candidato:** `banco_cuenta_nuevo.html` filtra monedas inactivas en Smart Select, pero POST válido con CSRF persiste una `Currency.active=False` en BankAccount. #1165 cubre línea de diario y #547 Imports, no esta asignación. Comentario a root #1716: `6671753593`; agrupación provisional.
- **#1980 → #1717 candidato:** doble POST secuencial con igual `(company, account_no)` responde 500 por `IntegrityError`; la constraint conserva una sola fila. No se probó carrera concurrente. Comentario a root #1717: `6671753963`.
- **#1981 → #1711 candidato, needs-review:** CTA `Nuevo` de `banco_cuenta_lista.html` visible para no-role y solo-view; endpoint devuelve 403, sin fuga ni bypass. Falta decidir ocultar/deshabilitar acción. Comentario a root #1711: `6671802106`; raíz no confirmada.


### Reconciliación de Caja Chica — nuevos issues (2026-11-05)

| Issue | Root candidato / estado | Evidencia y límites |
|---|---|---|
| #1986 | #1649 candidato | GET de alta de reposición con `petty_cash_id`/`company` ajenos devuelve conceptos/importes; POST de compañía ajena 403. Fuga de lectura confirmada; comentario root `6672566015`. |
| #1987 | #1706 candidato; #1653 secundario | Alta válida intenta mutar `PettyCashExpense.replenishment_id` y guard Cloud produce 500; rollback deja sin reposición/reserva parcial. Decidir contrato de vínculo append-only; root comment `6672566312`, se conserva `needs-review`. |

### Administración — matriz de aprobación (2026-11-06)

- **#1995 → #1717 candidato:** QA Flask/SQLite reprodujo que referencias inexistentes de rol/usuario producen HTTP 500 con FKs activas y se persisten como reglas huérfanas con FKs desactivadas. Comentario al root #1717: `6673957692`. La relación causal queda provisional.

### Administración — idioma del sistema (2026-11-06)

- **#1918 → #1711 candidato:** `system_language.html` cambia el idioma global y Babel renderiza el cuerpo en inglés, pero el `base.html` compartido conserva `<html lang="es">`; evidencia comentada en #1918 (`6674071940`). El mismo pase detectó `Language default` para “Idioma predeterminado” en el catálogo en inglés; candidato i18n bajo #1711, comentado (`6674197997`). `#1711` conserva `needs-review`; relación candidata, no aprobada como causa común.

### Compras — configuración de abastecimiento (2026-11-06)

- **#1996 → #1717 candidato; #1711 secundario:** el POST de `minimum_offers=not-a-number` evita mutación, pero muestra en flash el ValueError crudo de Python. Evidencia HTTP/curl reproducida; comentarios en los roots `6674684794` y `6674684894`. Candidato de validación de dominio y traducción de error; causalidad no confirmada.

- **#1997 → #1706 candidato:** la vista interna de confirmación de saldos no valida `snapshot_hash` antes de presentar `snapshot_json`; curl reprodujo HTTP 200 con datos alterados/hash no coincidente y HTTP 500 para JSON inválido. Comentario QA al root `6674807740`; extensión candidata de integridad al leer, no causa aprobada.

- **#1998 → #1649 candidato:** GET de alta de confirmación precarga Party y correos por ID sin validar ACL/CompanyParty; `curl` con usuario sin roles/access a compañía devolvió 200 e incluyó nombre y email de Party global no asociado. Comentario QA en #1649 `6674869316`; distinto de la lectura O2C #1971.

- **#1999 → #1711 candidato:** formulario de roles sigue mostrando en español botones y error de duplicado con el perfil EN aunque los títulos traducen; curl reprodujo alta, edición y duplicado. Comentario en #1711 `6675009059`; agrupación UI/i18n no confirmada.

- **#2000 → #1653 candidato:** reemplazos concurrentes de `RolesAccess` reproducidos en PostgreSQL 16.15 con dos transacciones: índice `(role_id,module_id)` no único permite duplicados y `Permisos` une permisos de ambas filas. La reproducción fue sobre esquema temporal/SQL equivalente; el intercalado exacto de rutas se deriva del flujo SELECT/DELETE/INSERT de `rol_permisos`. Root candidato, no asignado como causa confirmada porque #1653 trata principalmente recursos reservables. Comentario `6675142264`; preservar `needs-review` del root.


## Documentación y sitio

| Issue | Root | Confianza | Mecanismo/nota |
|---|---|---|---|
| #2001 | Sin root actual | Alta | En inicio, CTA de instalación responde 404 y tarjeta titulada CLI apunta a Codecov/cobertura. Son defectos de contenido/navegación; no se asigna a #1711/#1719 sin confirmar mecanismo causal común. |


## Administración de aprobaciones

| Issue | Root | Confianza | Mecanismo/nota |
|---|---|---|---|
| #2002 | Sin root actual | Alta | La matriz de UI lista `enabled=False` como si estuviera habilitada y ofrece un delete idempotente; el motor sí excluye las reglas inactivas. No se fuerza vínculo con #1708/#1711 sin validar mecanismo común. |


## Formularios administrativos y estado de vigencia

| Issue | Root candidato | Confianza | Mecanismo/nota |
|---|---|---|---|
| #2003 | #1717 candidato; relacionado con #1962 | Alta | Checkbox `is_active` omitido al desmarcarse cae al default `"1"` y persiste tipo de dimensión activo. Mismo patrón que taxes; #1962 conserva su alcance explícito y el caso nuevo queda separado. |
| Tipo/company inexistentes en valores de dimensión | #1717 candidato | Alta | El endpoint inserta referencias sin validar; la instancia de `create_app` SQLite probada tenía `PRAGMA foreign_keys=0`, por lo que IDs inexistentes redirigieron y persistieron. Comentario #1717 `6675515150`. |


## Issues de este checkpoint — 2026-11-06

- [#2005](https://github.com/cacao-accounting/cacao-accounting/issues/2005): enums de `TaxRule` se persisten sin allowlist y pueden excluir reglas o calcular importe cero; hijo candidato #1717 (validación de dominio), comentario agregado al root. La asignación causal sigue provisional y #1717 mantiene `needs-review`.
- [#2004](https://github.com/cacao-accounting/cacao-accounting/issues/2004): botón de eliminar reglas sin accessible name; candidato #1711 (contrato de interfaz/i18n), ya comentado allí.


### Administración de acceso — escrituras bloqueadas por guard (2026-11-06)

- **#2006**: el guard de borrado sensible bloquea `RolesUser` al reemplazar/revocar roles en `usuario_roles()`, HTTP 500 y rollback. Relación técnica hermana de #1700 (`UserCompanyAccess`), pero no asignada a #1649 porque su alcance es específico de compañía. Causa común candidata: mutaciones de relaciones ACL carecen de servicio autorizado compatible con el guard; agrupación raíz todavía provisional, pendiente de ratificación.
- **#1682 → #1653 candidato**: la ruta admin permite enviar el mismo role ID repetido y crear filas duplicadas si el usuario aún no tiene asignaciones. Reconfirmado por HTTP con rol inactivo.
- La hipótesis anterior de asignar `usuario_roles()` a #1716 se retiró: `Roles` no tiene `active`; `RolesUser.active=False` es filtrado por los consumidores. La evidencia y la retractación quedaron en #1716.

- **#2007**: `/permisos_usuario` muestra encabezado de módulo vacío por usar atributo `modulo.modulo` que no existe en `Modules` (`module`); raíz causal pendiente de agrupar, sin asignación provisional por afinidad.

## Hallazgo reciente de configuración — 2026-11-06

- **#2012 → #1711 candidato:** Los formularios `purchase_reconciliation_config.html` y `sales_matching_config.html` no precargan valores existentes; al seleccionar compañía ya configurada y guardar controles por defecto, reescriben matching/tolerancias/flags y, en compras, desactivan anticipos. Repro Flask/SQLite con CSRF válido; se comentó a #1711 (`6677539733`) y #1567 (`6677539956`). La agrupación raíz queda provisional.

## Hallazgo reciente de lockout — 2026-11-06

- **#2013 → #1710 candidato:** el template de seguridad de sesión muestra dos minutos cuando el tiempo restante es exactamente 60 segundos. Repro con reloj controlado Flask/SQLite y HTML renderizado; expiración se oculta y el login limpia `lockout_until`. Comentado bajo root candidato en `6677675624`.

## Hallazgo reciente en configuración fiscal — 2026-11-06

- **#2014 → #1711 candidato, needs-review:** Delete de regla fiscal desde UI se bloquea con 500 por el guard de modelos sensibles. El criterio de borrado vs inactivación auditada requiere decisión; comentario en el root `6677756526`.


## Hallazgos recientes — comparación de pronósticos — 2026-11-06

- **#1084**: Flask/SQLite confirmó weekly FY2027 vs FY2028 empareja `Semana 1 (01/01 - 07/01)` (100 NIO vs 900 NIO, varianza +800) y weekly vs monthly genera saldo comparado cero para períodos no emparejados. La ruta rechaza IDs de compañía ajena con 404; falta decisión de equivalencia de períodos. Comentario `6678379947`.
- **#2015 → #1711 candidato primario / #1655 secundario**: `cash_forecast_comparar.html` presenta importes en moneda funcional sin código; HTML NIO imprime `800.00` y no `NIO`. Relacionado a #1942, comparativos S2P. Comentarios: #1655 `6678383947`, #1942 `6678408168`, #1711 `6678408732`. Causa candidata; no consolidada aún.


## Hallazgo reciente — alta de pronósticos — 2026-11-06

- **#2016 → #1711 candidato; relacionado #1632 y #1951:** el selector de compañía ofrece cambiar, pero años fiscales se cargan solo para la compañía inicial. Un POST a otra compañía con el FY anterior se rechaza. #1951 cubre la pérdida de valores al re-renderizar, mecanismo distinto. Comentarios de evidencia en #1711 y #1632 (`6678548694`, `6678549063`); child #2016 queda needs-work.
- #1083/#1258 se editaron para corregir que la interfaz muestra periodicidad inválida como Mensual mientras el servicio crea semanas. Evidencia del alta mensual válida, duplicado e `annual` en #1083 (`6678557612`).


## Hallazgo reciente — estado del formulario fiscal — 2026-11-06

- **#2017 → #1711 candidato:** al fallar validación en alta/edición de `TaxRule`, las rutas re-renderizan sin pasar `request.form`; `tax_rules.html` recupera solo la fila persistida o defaults, descartando el resto de la propuesta. Comentarios a #1711 `6678756216` y repro dinámico en el issue `6678984108`. POST inválido devuelve HTTP 200 pero descarta campos enviados; es pérdida de estado de UI; #2005 cubre la validación de enums y conserva causa distinta. Pendiente revisión de causalidad; #2017 abierto como `needs-work`. Snapshot: 1014 issues (24 root/990 code).


## Hallazgo reciente — referencias de TaxRule — 2026-11-06

- #2018 → #1717 candidato primario / #1649 secundario: PostgreSQL 16 reprodujo FKs de company/account/currency inexistentes como HTTP 500 sin fila; cuenta de otra compañía persiste en la regla y luego bloquea snapshot fiscal por company mismatch. Comentarios a ambos roots 6678896668 y 6678896931. #1549/#1441 son diferentes: cubren cuenta ausente/omisión de asiento, no referencias cruzadas. Causalidad provisional; issue needs-work. Snapshot: 1015 issues, 24 root/991 code.


## Impresión / validación pública

| Issue hijo | Root candidato | Confianza | Mecanismo/nota |
|---|---:|---|---|
| #2019 | Sin root confirmado | Alta en reproducción, causa raíz pendiente | Flask + SQLite: el mismo grand_total Decimal cambia de escala `125.50` a `125.5000` tras persistencia; la serialización textual cambia el hash y muestra falso estado invalid en `validation_result.html`. No se asigna a #1650 (coerción de entrada Decimal) sin demostrar el mismo mecanismo. Debe verificarse también contra PostgreSQL/MySQL. |

| #2020 | #1707 candidato primario; #1686 asociado al adapter legacy | Alta en el mapeo incorrecto, Confirmado hasta GLEntry | `calculate_taxes()` omite impuesto inactivo; `_tax_rules_from_template()` reutiliza índice de la lista original y asigna al impuesto activo la base `net_document` de la fila anterior, en vez de `previous_total`→`accumulated`. Con fixture compra/venta y libro abierto, legacy withholding 22 vs posting 20 (AR/AP 90 vs 88) en SQLite. Comentarios #1707 `6679181368`, #1686 `6679181599`; child `needs-work`. |



## Hijo añadido — navegación de reportes de caja

| Issue hijo | Root candidato | Confianza | Mecanismo/nota |
|---|---|---|---|
| #2024 | #1711 | Alta en la discrepancia UI/permiso | `bancos.html` oculta el bloque de reportes usando `acceso.autorizado` (`cash.access`) aunque cada link requiere `reportes`; usuario con `cash.reportes` y compañía autorizada ve HTTP 200 en los dos endpoints, pero no recibe los enlaces en el home. Reproducción y comentario root `6680825322`. `needs-work`; sin decisión de negocio identificada. |

| #2025 | #1711 | Alta | Con `cash.access=True` y `cash.consultar=False`, el home muestra el enlace de pronósticos con badge no-access aunque el destino da 403. Condicional/badge no reflejan el permiso efectivo del endpoint. Comentario root `6680851819`. |
| #2026 | #1711 candidato | Alta en el defecto de estado vacío | `banco_lista.html`: curl con búsqueda sin coincidencias devuelve `0 items encontrados` / `Página 1 de 0` sin estado vacío; issue `needs-work`, comentario root `6681035995`. Asociación UI candidata, sin confirmar como causa compartida. |
| #2027 | #1711 candidato | Alta en i18n/accessibility | `banco_lista.html` deja `aria-label="breadcrumb"` literal inglés en locale español; `messages.po` usa también un msgid inglés, así que incluso llamadas gettext cercanas no garantizan salida española. Issue `needs-work`, comentario root `6681054700` y precisión `6681205307`; falta determinar alcance y dedupe del patrón transversal. |
| #2029 | #1711 candidato | Alta en feedback de formulario | `banco_nuevo.html`: POST vacío o de espacios falla `DataRequired` y no persiste, pero el template oculta el error del campo; QA independiente confirmó HTTP 200. Comentario root `6681172389`; asociación UI candidata. |


### Alta de banco — validación de SWIFT

| Issue | Root candidato / estado | Evidencia y límites |
|---|---|---|
| #2028 | #1717 candidato | `banco_nuevo.html` acepta SWIFT >20; SQLite persiste y PostgreSQL Tier 1 da 500 por `StringDataRightTruncation`, sin fila. Modelo `String(20)` y WTForms sin límite; comentario root `6681156190`. Asociación a validación de dominio provisional. |


### Continuación Jinja — gasto de caja chica

| Issue hijo | Root candidato | Confianza | Mecanismo/nota |
|---|---|---|---|
| #2030 | #1653 candidato | Alta en atomicidad de cancelación | `cancel_petty_cash_expense()` confirma la reversa GL antes de mutar `PettyCashExpense.docstatus` y restablecer `PettyCashVoucher`; una falla SQL entre pasos deja ledger cancelado y subledger/voucher activos. Repro con trigger SQLite, root comentó `6681302275`, issue padre `6681302607`. |
| #2031 | #1711 candidato | Alta en discrepancia visual | `caja_chica_gasto_nuevo.html` no limpia `#pc_currency` al invalidar fondo por cambio de compañía; Chromium reprodujo moneda vieja visible. No prueba posteo incorrecto. Root comentó `6681439259`. |
| #2032 | #1711 candidato | Alta en accesibilidad/validación visual | Etiqueta marca Centro de costo obligatorio, pero el Smart Select omite `required=True`; formulario/servicio lo rechazan en backend. Root comentó `6681482400`. |
| #1992 ampliado | #1711 / #1717 candidatos, `needs-review` | Alta en contrato visible/persistido | El selector `naming_series` del formulario de gasto también se ignora; la ruta omite el campo y el servicio asigna identifier con `naming_series_id=None`. Evidencia agregada al issue existente, comentario `6681439582`; la decisión sobre permitir elección manual permanece pendiente. |


| #2033 | #1711 candidato | Alta en pérdida de estado frontend | El callback de selección navega con fondo/compañía, pero GET no hidrata Smart Select: ambos hidden inputs regresan vacíos y el callback vuelve a recargar. Comentario root `6681563054`. |
| #2034 | #1658 candidato; `needs-review` | Alta en código sin caller local | El modo edición/attached_ids de `caja_chica_reposicion_nueva.html` no recibe `reposicion` ni `attached_ids` en el único render local; definir integrar o retirar. Comentario root `6681579859`. |


| #2035 | #1711 candidato | Alta en pérdida de selección tras rechazo | POST amount=0 en alta de vale devuelve 200 y no persiste; al re-renderizar, company/petty_cash_id vacíos aunque el monto se conserva. Se mantiene separado de #1951 hasta validar fix común; root 6681710816. |


| #2036 | #1711 candidato | Alta en identificación UI | La lista de reposiciones muestra ULID del fondo sin nombre/compañía; admin multiempresa no distingue cajas. Similar por síntoma a #1990, pero otra lista; root `6681779391`. |
| #2037 | #1711 candidato | Alta en localización de etiquetas | El comparativo imprime zonas y estados internos en inglés sin gettext; Chromium confirmó etiquetas `Real`/`Current`/`Projected`. Root `6681825635`; #2027 cubre también breadcrumb literal (`6681825927`). |
| #2038 | #1711 candidato | Alta en selección de compañía | La ruta bancaria no ofrece selector de compañía; admin multiempresa carga formulario con hidden vacío y el POST exige compañía explícita. Comentario raíz `6681892132`. |
| #2039 | #1711 candidato; `needs-review` | Alta en persistencia de referencia | `nota_nueva.html` envía `external_number`, pero el builder no lo asigna ni a `PaymentEntry.external_number` ni `reference_no`; decidir semántica/validación antes de corregir. Comentario raíz `6682135249`. |
| #2040 | #1711 primario; #1655 secundario por FX | Media en estado UI de moneda | `nota_nueva.html` y `bancos/transferencia_nueva.html` leen `event.detail.extra.currency`, aunque Smart Select entrega `option.currency` en nivel superior; ambos dejan moneda vacía. En transferencia esto además simula moneda igual y calcula preview sin conversión, mientras backend deriva tasa histórica. Evidencia cruzada en #2040 `6683062365`, root #1711 `6683062718`, #1655 `6683063014`; mecanismo primario de interfaz, consecuencia de FX.
| #2041 | #1711 candidato; relacionado #2026 | Baja en estado vacío | `pago_lista.html` no tiene bloque vacío y el paginador compartido puede renderizar Página 1 de 0. Comentarios `6682328312`/`6682328601`. |
| #2042 | #1711 candidato | Media-alta en contrato de ruta | `pago_lista.html` fija el endpoint de pagos en el macro: página 2 de transferencia y notas vuelve a `/payment/list`, perdiendo el tipo. Reproducido con 11 filas por tipo; comentario en #1711. |
| #2043 | #1711 y #1655 candidatos; `needs-review` | Decisión de representación monetaria | La lista de transferencia usa `paid_amount` sin moneda ni importe de destino; falta decidir qué pierna mostrar. Comentado en #1711/#1655; no implementar hasta criterio de negocio. |
| #2044 | #1711 primario candidato; #1649 relacionado | Alta en re-render y status de autorización | POST de alta de transferencia con CSRF y payload inválido o sin `cash.create` responde 200 y renderiza `pago_nuevo.html`, sin `bankTransferForm`. `bancos_transferencia_nueva()` delega a `bancos_pago_nuevo()`, que pierde template/contexto al recibir None. El guard está antes del add/flush; la sonda no comprobó filas persistidas. Comentarios: #1711 `6683126179`; #1649 `6683126499`; curl en #2044 `6683201514`. Distinto por ruta de #1951/#1956, que son analogías de pérdida de estado.
| Confirmación pública de saldos, posible pérdida de precisión | #1711 candidato; `needs-review` | Media, reproducción numérica | `confirm_balance_view.html` convierte importes/totales del snapshot a `float` antes de formatear; `Decimal(1.015)` mostrado a dos decimales pasa de `1.02` por formatter Decimal a `1.01` por float y números grandes pierden precisión. Candidato reportado al root `6683852444`; validar precisión/rounding esperados por moneda antes de issue/fix. |
