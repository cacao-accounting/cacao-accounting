# Auditoría: estado para continuar

La auditoría está pausada. Referencia: rama `estabilizacion`, código auditado en `73fcbd3feab0f7c56bdbd082c4b7422a41ce473f`; seguimiento consolidado en `fbef114431e603a89599c3c3c3de7e1a1cf5143e`. Comprueba los cambios de código y sus dependencias antes de reutilizar cobertura.

El inventario deduplicado tiene 557 rutas: 84 completas y 473 sin cierre (287 parciales y 186 pendientes), sin deltas y con dos criterios pendientes (#1888 y #1889). `AUDIT_PENDING.md` es la cola vigente; sus descripciones mezclan cobertura y trabajo pendiente y no son un inventario exhaustivo de símbolos. Las filas completas y evidencia histórica están en el manifiesto anterior. Recuperar sin cargar todo en contexto:

```sh
git show fbef114431e603a89599c3c3de7e1a1cf5143e:AUDIT_PROGRESS.md
```

Buscar en esa salida por ruta, función, hash o número de issue antes de repetir una revisión. El histórico contiene afirmaciones contradictorias; preferir checkpoints recientes y verificar contra código, hashes e issues. Los issues y sus comentarios conservan reproducciones y límites.

## Componente activo: Persistencia / Inventario / StockEntry

Trabajar un flujo a la vez con un revisor Python y otro Jinja/JS del mismo módulo. Reconciliar sus resultados y revisar dependencias transversales solo hasta el contrato del flujo. No cerrar Persistencia al terminar únicamente StockEntry.

- Submit normal: se cotejó el fan-out GL por línea y libro, con SLE/SVL una vez por compañía; AR/AP no aplica a StockEntry. Los demás consumidores de esos servicios siguen parciales.
- Edición y detalle: #1810, #1835, #1863, #1865, #1890; #1888 y #1889 requieren criterio. Las plantillas de alta, conciliación, detalle y lista siguen parciales. Cancelación pendiente de aprobación no se muestra correctamente (#1803); solicitud ignorada si retorna `None` (#1728); cancelación aprobada no revierte relaciones/cache (#1872).
- Reversas: #761 fecha, #1857 orden/capacidad, #1858 asignación FIFO, #1876 capacidad por lote, #1211 valor consumido y #444 seriales. #1868 **ya tiene reproducción PostgreSQL con dos sesiones**: bin obsoleto en identity map tras `FOR UPDATE`; falta integración completa cancelación/posting y reconciliación SLE/SVL. No repetir la sonda sin una brecha concreta.
- Huellas de referencia: `posting_service.py` `3ee08c467cd91773d2e392d72192cb1abd1c170f546e35a96def187885eb4f3b`; `database/__init__.py` `647da8ff195aea8ed0fd09c2360fc1a53eb0541c5b32c5bc05d2e36803bf1dcc`; `inventario/routes.py` `66616916d5e79061cecd99ba283fa540d1342a468fffb4e7a8535e39f859628d`; `inventario/services.py` `3fb2ddaf16e176db2269a0563f6d81f7c4d08ebb7d8a4f658570b8641fd16f71`.

Próximo trabajo: completar límites no acreditados de cancelación y reversa, incluyendo transferencia serializada #444 y la integración pendiente de #1868 si aporta evidencia nueva; luego revisar importes sin moneda en `entrada_lista.html`, sus productores y causa compartida (#1427 y #1016 no son duplicados automáticos). Completar los propósitos y superficies de StockEntry, luego modelos/constraints/listeners y consumidores pendientes de `database/__init__.py` y `database/helpers.py` según sus checkpoints históricos. Mantener archivos parciales hasta cubrir todo su alcance.

Tras cada revisión, registrar aquí evidencia, hashes, límites y punto siguiente; actualizar la cola y recalcular rutas únicas. Consultar estado y contenido de issues antes de comentar o crear uno; no duplicar. Véase `AUDIT_PROMT.md` para método y restricciones.
