# SESSIONS - Bitacora de desarrollo

Este archivo resume decisiones de diseño y resultados relevantes para continuar el desarrollo. Los detalles historicos externos no se duplican aqui.

## 2026-08-23 - Internacionalizacion

- Se incorporaron catalogos Babel para espanol e ingles, con mensajes extraidos de Python y Jinja2.
- Los archivos `.po` y `.mo` se incluyen en los paquetes distribuibles mediante `MANIFEST.in` y `pyproject.toml`.
- La seleccion del idioma global se guarda en `SETUP_LANGUAGE`; el idioma preferido del usuario tiene prioridad.
- Los tests de mensajes flash deben considerar el locale activo despues de cambiar el idioma.
- Se corrigio la regresion del test de configuracion de idioma para validar las traducciones inglesas.

## 2026-08-23 - Interfaz movil

- La barra de acciones ocupa una fila completa en pantallas pequenas.
- Las acciones se apilan con objetivos tactiles de al menos 44 px y los grupos de impresion usan el ancho disponible.
- El comportamiento se implementa mediante macros compartidos para mantener consistencia entre detalles, pagos y comprobantes.

## 2026-08-23 - Adjuntos, imagenes e impresion

- Las operaciones de adjuntos validan referencia, documento, compania, modulo y permisos.
- Las imagenes validan extension, MIME y firma binaria; el reemplazo conserva la imagen anterior hasta persistir la nueva.
- Los formatos de impresion muestran auditoria de creacion, aprobacion e impresion, con valores seguros cuando no hay eventos.

## 2026-08-23 - Modos de ejecucion

- Desktop Mode limita deliberadamente ciertas capacidades multiusuario, multiempresa, portales y aprobaciones.
- Las pruebas dependientes de capacidades cloud se omiten explicitamente en Desktop Mode; las restricciones propias de desktop permanecen cubiertas.

## 2026-08-22 - Contabilidad y persistencia

- Los balances multianuales no vuelven a sumar resultados de ejercicios ya transferidos al patrimonio.
- La liquidacion multicurrency propaga diferencias cambiarias explicitas y tolera diferencias de redondeo de hasta 0.01.
- Los flujos de pagos, inventario, conciliacion y fiscalidad conservan invariantes de atomicidad, permisos, moneda y libro activo.
- Los snapshots fiscales y de pagos se validan mediante los constructores reales del dominio.

## 2026-08-22 - Calidad y continuidad

- El proyecto requiere Python 3.12 o superior, Flask, Alpine.js y pip.
- Antes de entregar cambios se deben considerar Black, mypy, Ruff, Flake8, pydocstyle y pytest.
- La suite completa se ejecuta con el comando documentado en `AGENTS.md`, usando `venv` o `.venv`, en segundo plano y con resultados guardados en un archivo de texto.
- Las pruebas nuevas deben cubrir las regresiones y conservar las decisiones de dominio descritas aqui.

## Estado de continuidad

- Revisar primero este resumen y el codigo actual antes de planificar una nueva etapa.
- Consultar el historial externo solo cuando se necesite recuperar contexto historico; no copiar esa trazabilidad en esta bitacora.
## 2026-08-23 - Tipos de entidad localizados en setup

- El formulario de empresa conserva valores estables para persistencia y ahora localiza sus etiquetas según el idioma elegido.
- El catálogo inglés muestra Association, Limited Liability Company, Cooperative, Corporation, Nonprofit Organization e Individual.
- Se agregó una regresión que verifica etiquetas bilingües y valores equivalentes.
## 2026-08-23 - Publicacion de catalogos Babel

- El workflow de publicacion instala Babel y compila los catalogos PO a MO antes de construir wheel y sdist.
- La compilacion usa el directorio de traducciones del paquete y fuerza la regeneracion de los archivos binarios.