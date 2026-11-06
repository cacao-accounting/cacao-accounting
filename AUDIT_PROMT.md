# Procedimiento permanente de auditoría

`AUDIT_MATRIX.csv` es la única fuente local de cobertura y estado por símbolo. GitHub Issues
conserva la evidencia narrativa: hallazgos, investigaciones, pruebas, hipótesis y decisiones. El
alcance de la auditoría es exclusivamente el código dentro de `cacao_accounting/`; scripts, tests,
documentación, configuración de raíz y CI quedan fuera y no se inventarían. La auditoría no autoriza
correcciones de código ni cambios de reglas de negocio. Lee primero `AGENTS.md` y comprueba rama y
cambios locales antes de tocar el seguimiento.

## Registro de cobertura

Cada fila representa una unidad auditable de `cacao_accounting/`. No se omiten símbolos: funciones,
métodos, funciones anidadas, asíncronas, clases, macros Jinja, bloques de plantilla, formularios,
acciones, handlers, componentes Alpine, JavaScript embebido, migraciones y configuraciones con
comportamiento deben estar inventariados. Si un extractor no reconoce una construcción, se registra
explícitamente para revisión manual; nunca se descarta en silencio. Los assets, fixtures de pruebas
frontend y binarios compilados dentro del directorio se excluyen con motivo explícito.

Estados permitidos:

- `Pendiente`: no existe evidencia individual suficiente.
- `Parcial`: existe revisión, pero quedan brechas, ramas o escenarios sin acreditar.
- `Completo`: el contrato aplicable de esa unidad está cubierto por evidencia suficiente.

Un cierre por archivo, una mención en una investigación, un issue que describe un defecto o una
prueba del camino principal no acreditan por sí solos el estado `Completo` de cada símbolo. La
incertidumbre no justifica marcar `Completo`: es preferible repetir la revisión antes que declarar
cobertura inexistente. Un falso positivo de cobertura es más grave que un falso negativo.

## Ciclo de trabajo

1. Consulta `AUDIT_MATRIX.csv` y selecciona una unidad `Pendiente` o `Parcial`.
2. Examina el código vigente, sus contratos, callers, validaciones, permisos, persistencia, errores,
   concurrencia, reversas y escenarios límite aplicables. Contrasta la evidencia existente y no
   repitas trabajo válido.
3. Antes de registrar un defecto, busca en GitHub Issues y añade la evidencia al issue
   correspondiente. Crea uno nuevo solo para un hallazgo verificable que no esté cubierto. El estado
   de un issue no determina el estado de cobertura.
4. Registra hallazgos, pruebas y decisiones en los issues; en la matriz escribe solo un comentario
   operativo breve y, cuando corresponda, la referencia al issue.
5. Actualiza únicamente las unidades revisadas. No promuevas estados por proximidad, por herencia
   de una plantilla completa ni por estimaciones de avance.
6. Revisa el archivo completo para detectar unidades añadidas, eliminadas o modificadas. Las
   unidades nuevas entran como `Pendiente`; las eliminadas se retiran tras comprobarlas.
7. Ejecuta el verificador después de cada actualización de la matriz.

## Verificación del inventario

Contrasta la matriz con el código vigente antes de actualizarla: rutas existentes, estados válidos,
sin duplicados, en orden y con correspondencia entre símbolo registrado y símbolo real. No se
conservan extractores ni verificadores locales; esa comprobación es parte de la revisión.

La presencia de una fila en la matriz **no** demuestra cobertura funcional. La cobertura acreditada
requiere evidencia por símbolo y revisión humana o agéntica. Toda ruta omitida, construcción
dinámica o unidad no reconocible debe investigarse, no asumirse cubierta.

## Cambios de código

Identifica las unidades afectadas y sus dependencias de contrato. Añade las nuevas como
`Pendiente`, retira las eliminadas tras comprobarlas y reevalúa la cobertura de las modificadas.
Conserva los estados de las unidades no afectadas. Una revisión anterior solo sigue siendo válida
para código modificado después de comprobar el contrato y la evidencia pertinentes.

## Evidencia histórica

La evidencia anterior a la matriz permanece en Git. Consúltala con `git show <commit>:<archivo>`
para los documentos históricos de seguimiento. Verifica que corresponda a la implementación vigente
y que permita identificar el símbolo revisado antes de usarla. La evidencia agregada de un archivo
no acredita automáticamente todos sus símbolos. No crees bitácoras locales paralelas ni checkpoints
manuales de avance: los indicadores se derivan de la matriz y la narrativa vive en los issues.

## No saturar la API de github

Implementa una estrategia de consulta local para los issues de `cacao-accounting/cacao-accounting`, con el objetivo de reducir drásticamente las peticiones a la API de GitHub durante la auditoría de la rama `estabilizacion`.

Descarga inicialmente todos los issues abiertos, incluyendo sus metadatos, descripciones, etiquetas y comentarios necesarios, mediante paginación y respetando los límites de la API. Almacena el snapshot fuera del repositorio de código, en un formato estructurado y reutilizable (JSONL o SQLite).

Implementa sincronización incremental basada en `updated_at`, con un margen de solapamiento y deduplicación por ID. Debe detectar también issues que dejaron de estar abiertos y manejar correctamente paginación, errores, interrupciones y rate limits.

A partir de ese momento, todos los agentes deben utilizar exclusivamente el snapshot local para consultar, clasificar, comparar, agrupar y analizar issues. GitHub se utilizará únicamente para sincronización controlada y publicación de hallazgos verificables.

Evita consultas individuales repetitivas, especialmente para comprobar duplicados. Permite compartir una única cache entre agentes y garantiza que ninguna sincronización sobrescriba o corrompa datos utilizados por otros procesos.

No modifiques código funcional de Cacao Accounting, no cierres issues, no cambies etiquetas ni alteres el inventario existente. No agregues archivos de seguimiento al repositorio. Mantén la rama `estabilizacion` congelada durante la auditoría.

Documenta brevemente cómo realizar la descarga inicial, actualizar el snapshot, consultar sus datos y verificar cuándo se sincronizó por última vez.
