# Validación de Documentos mediante QR

La funcionalidad de validación por QR permite a un tercero confirmar que un documento fue emitido por Cacao Accounting y que sus datos principales no han sido alterados.

## Cómo funciona

1. Cuando se postea un documento oficial, Cacao genera o reutiliza un token público seguro y almacena un hash SHA256 determinista de la carga útil de validación permitida.
2. El backend de impresión inyecta `validation.enabled`, `validation.public_url`, `validation.token` y `validation.qr_data_uri` en el contexto de Jinja. Los templates nunca deben construir las URL de validación por sí mismos.
3. Escanear el QR abre `/public/validate_doc/<token>`, que recalcula el hash a partir del estado actual de la base de datos y renderiza un modelo de vista público y seguro.

Los documentos en borrador nunca crean ni actualizan registros de validación pública. Los documentos cancelados y revertidos conservan su token, pero el estado público cambia.

## Configuración

La validación externa de documentos se gestiona desde **Administration -> Configuration -> External Document Validation**.

Los ajustes se persisten en `CacaoConfig`:

- `external_document_validation_enabled`: habilita el endpoint de validación pública, la inyección de URL y el renderizado del QR.
- `external_document_validation_base_url`: URL base usada para construir los enlaces de validación pública.

Si `external_document_validation_base_url` falta o está vacío, Cacao usa `https://cacaocontent.com`. Los valores de entorno como `EXTERNAL_DOCUMENT_VALIDATION_ENABLED` y `EXTERNAL_DOCUMENT_VALIDATION_BASE_URL` son solo valores de respaldo de arranque cuando no existe ningún ajuste persistido.

## Dependencia de QR

La generación de QR usa `segno==1.6.6`, declarado en `requirements.txt`. La falta de soporte de QR es un error de despliegue: el backend lanza un error de tiempo de ejecución claro en lugar de ocultar silenciosamente la funcionalidad de QR.

La publicación de templates valida el renderizado del QR cuando el cuerpo hace referencia a `validation.qr_data_uri`, de modo que una dependencia de QR rota se detecta antes de que se publique el formato.

## Estados técnicos

El backend de validación devuelve estados técnicos:

- `valid`: el hash actual del documento coincide con el hash de validación almacenado.
- `invalid`: el documento existe, pero el hash actual difiere.
- `unavailable`: el token no existe, está deshabilitado o el documento fuente no está disponible.
- `cancelled`: el documento fuente fue cancelado.
- `reverted`: el documento fuente fue revertido.

El template público traduce estos estados en etiquetas legibles por humanos.

## Contrato de datos públicos

La página pública solo puede mostrar este modelo de vista:

- nombre de la compañía
- identificación fiscal de la compañía
- tipo de documento
- número de documento
- fecha del documento
- moneda
- total
- estado del documento
- hora de validación

No debe exponer cuentas del libro mayor, notas internas, detalle a nivel de línea, identificadores de usuario, relaciones privadas ni objetos de SQLAlchemy en crudo.

## Seguridad

- Los tokens no son predecibles.
- El hash canónico incluye solo una lista blanca de campos seguros para validación.
- El sistema no almacena snapshots del PDF o HTML; valida contra el estado actual de la base de datos.
- Cuando la validación global está deshabilitada, Cacao no construye `public_url`, token contextual ni datos renderizables de QR.
