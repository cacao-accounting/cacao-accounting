# Caché de datos con Redis

Redis es una optimización opcional para consultas repetidas de datos maestros. No es un requisito
operativo de Cacao Accounting: el sistema continúa funcionando contra SQLite en modo desktop y
contra la base de datos configurada en cloud cuando Redis no está disponible.

## Activación

La caché de datos solo se utiliza cuando se cumplen todas estas condiciones:

- La aplicación corre en modo cloud, no en modo desktop.
- `CACHE_REDIS_URL` está configurada.
- Flask-Caching está instalado y el backend configurado es `RedisCache`.
- Existe una solicitud HTTP y un usuario autenticado.

Ante un error de Redis al leer, guardar o invalidar, la aplicación continúa consultando la base de
datos. En modo desktop no se intenta abrir una conexión Redis.

## Aislamiento por usuario y RBAC

Las consultas se decoran con `user_scoped_cache(namespace)`. La llave se construye en el servidor e
incluye:

```text
<prefijo>:<namespace>:user:<id_usuario>:generation:<versión>:<hash_de_consulta>
```

El hash contiene los argumentos de la consulta, incluidos texto buscado, filtros, límite y alcance
autorizado de compañías. El identificador del usuario evita que una entrada creada por un usuario se
entregue a otro.

La autorización nunca se obtiene de Redis. Cada solicitud vuelve a validar RBAC y calcula las
compañías autorizadas antes de intentar leer una entrada cacheada. Si el acceso de un usuario cambia,
el alcance diferente genera una llave distinta.

## Datos cubiertos

Actualmente se cachean las opciones de compañías y los resultados de Smart Select para datos maestros
usados con frecuencia:

- Compañías.
- Cuentas contables.
- Centros de costo.
- Unidades de negocio.
- Proyectos.
- Clientes y proveedores.
- Artículos.

Los artículos conservan su comportamiento actual de catálogo global. La caché no cambia las reglas de
visibilidad existentes en la consulta.

No se deben cachear en este mecanismo saldos, disponibilidad de inventario, documentos pendientes,
tasas de cambio, asientos ni reportes financieros. Esos valores son transaccionales o pueden afectar
decisiones contables.

## Invalidación

Cada namespace mantiene una llave de generación. Después de confirmar una actualización de datos
maestros, `invalidate_cache(namespace)` escribe una nueva generación. Las entradas creadas antes de la
actualización dejan de coincidir de inmediato para todos los usuarios, sin recorrer ni borrar llaves
individuales.

La invalidación debe ejecutarse después de `database.session.commit()`. Los flujos cubiertos incluyen
crear, editar, activar, desactivar o eliminar compañías, cuentas, centros de costo, unidades,
proyectos, clientes, proveedores y artículos; también cubren cambios de rol y configuración por
compañía de clientes y proveedores.

Las entradas de datos tienen un TTL de 300 segundos. La generación es el mecanismo principal de
consistencia; el TTL limita la vida de datos antiguos si un futuro flujo de mutación todavía no tiene
su invalidación conectada.

## Redis para caché y rate limit

Un solo contenedor Redis puede servir ambos propósitos mediante bases lógicas separadas:

```text
CACHE_REDIS_URL=redis://cache:6379/2
RATELIMIT_STORAGE_URI=redis://cache:6379/0
```

`CACHE_REDIS_URL` y `RATELIMIT_STORAGE_URI` deben declararse explícitamente. El limitador no hereda
la URL de caché.

## Diagnóstico y pruebas

Cuando `TESTING_MODE` está activo, un hit de caché registra `Cache hit` en el log.

Las pruebas unitarias cubren aislamiento entre usuarios, revalidación de alcance, invalidación,
fallback sin Redis y bypass en desktop. La prueba de integración con PostgreSQL y Redis requiere
`TESTING_MODE` y `CACHE_REDIS_URL`; el job `cache-isolation` de GitHub Actions proporciona ambos
servicios y usa Redis DB 2 para caché y DB 0 para rate limiting.

## Decisiones y límites de esta fase

Esta implementación se diseñó para impedir que la caché omita RBAC o entregue datos de un usuario a
otro. La regla permanente es validar autorización y alcance antes de leer Redis; una llave con usuario
no sustituye esa validación.

Se eligió un TTL de 300 segundos porque las búsquedas corresponden a interacción humana y la
invalidación por generación ya publica los cambios conocidos de inmediato. Reducirlo solo para cubrir
fallos de invalidación disminuye el beneficio de caché sin resolver el origen del problema.

La llave de generación no crece por cada actualización: su nombre es fijo por namespace y su valor se
sobrescribe. Las entradas de resultados de generaciones anteriores expiran por TTL.

Las mutaciones registradas en esta fase invalidan los catálogos cubiertos. Si se agrega una ruta,
importador, seed o servicio que cambie alguno de esos datos, debe llamar a `invalidate_cache` después
del commit. Una etapa futura puede centralizar esta responsabilidad si aumentan los puntos de
mutación.

La integración Redis se limita a modo de pruebas para evitar que una URL Redis local ejecute pruebas
de aislamiento por accidente contra una base de datos de trabajo. Antes de ejecutar esa prueba fuera
de CI, configure una base dedicada de pruebas junto con `TESTING_MODE` y `CACHE_REDIS_URL`.
