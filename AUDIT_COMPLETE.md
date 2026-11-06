# Rutas con cierre histórico declarado — revalidación en curso

Corte: rama `estabilizacion`, código en HEAD `85eed67b20d818150895fe2bc8a691d2ae5d2f4f`.

Este manifiesto reconstruye, de forma reproducible, las 118 rutas que quedaron fuera de `AUDIT_PENDING.md`: parte de `git ls-files cacao_accounting/` (547), excluye 13 rutas de `static/media/`, seis de `static/test/` y el `.mo` compilado (20), y resta las 409 rutas productivas de la cola (527 - 409 = 118). Las filas conservan el historial de 118 cierres: al corte, 47 se revalidaron y 71 se reabrieron como Parcial; los 118 cierres heredados ya tienen decisión. Solo las rutas revalidadas cuentan como completas. “Completa” significa que se revisó el alcance del archivo; no significa que el archivo tenga lógica propia, esté activo ni que no sea candidato a dead code. Un módulo Python con solo docstring se cierra como marcador de paquete únicamente cuando `pyproject.toml` (`namespaces = false`) y la estructura/imports confirman que setuptools lo necesita; de otro modo debe quedar como candidato sin uso o parcial hasta comprobar callers y contratos externos. La columna SHA fija el contenido al corte; si cambia, se invalida la revisión afectada. Las menciones ambiguas por basename e inventarios de símbolos no prueban revisión de comportamiento.

Después del corte histórico se cerraron setenta y cinco rutas adicionales revisadas con el criterio de `AUDIT_PROMT.md`; el total vigente es 123 completas y 441 parciales de 564 rutas auditables. La evidencia queda en las tablas de cierres posteriores. Las plantillas están reconciliadas por ruta exacta: 252 rutas únicas, 84 completas con SHA y 168 parciales. Las secciones de cierres posteriores tienen filas explícitas con ruta/SHA/estado; las filas históricas reabiertas permanecen Parciales salvo que una sección posterior documente un cierre vigente.

| Ruta | SHA-256 en el corte | Estado de evidencia | Referencia disponible |
|---|---|---|---|
| `cacao_accounting/accounting_engine/__init__.py` | `e28f8ad865fe6abe32f7054fb36b9e65e3cbadd4fa144bacfc9606c90d4399a8` | Revalidado: cobertura del archivo revisada | Solo docstring; prueba con `find_packages` confirma que quitar este marcador excluye el paquete (`namespaces=false`). La conclusión se limita al rol de empaquetado de este archivo. |
| `cacao_accounting/accounting_engine/common/__init__.py` | `cc05cfd0a241cbe4805f9cfb677c712f69b7c359dca044f162521ba2a180d156` | Revalidado: cobertura del archivo revisada | Solo docstring; prueba con `find_packages` confirma que quitar este marcador excluye el paquete (`namespaces=false`). La conclusión se limita al rol de empaquetado de este archivo. |
| `cacao_accounting/accounting_engine/common/fiscal.py` | `36aeb2290e638e67b061c44ded4536695474c8c89238465f72893af0ac935ad9` | Reabierto: Parcial | Faltan callers y escenarios límite de periodo/moneda. |
| `cacao_accounting/accounting_engine/fiscal/__init__.py` | `06cee04b285cc32fd7f5f2f14b10c90b8c6ed0fcbb4532d2ecccd8c42a2c2560` | Revalidado: cobertura del archivo revisada | Solo docstring; prueba con `find_packages` confirma que quitar este marcador excluye el paquete (`namespaces=false`). La conclusión se limita al rol de empaquetado de este archivo. |
| `cacao_accounting/accounting_engine/landed_cost/__init__.py` | `4d099267e0085fdaa224f3a490b28141e0a989204ada5c2609a947dbde3d72c6` | Revalidado: cobertura del archivo revisada | Solo docstring; prueba con `find_packages` confirma que quitar este marcador excluye el paquete (`namespaces=false`). La conclusión se limita al rol de empaquetado de este archivo. |
| `cacao_accounting/accounting_engine/landed_cost/engine.py` | `6016fde0c137d474e97eed6e7ac0cb53dbba33684e22fea79edd095fd8dd35dc` | Reabierto: Parcial | Faltan flujo/callers e invariantes de costo y bordes. |
| `cacao_accounting/accounting_engine/orchestrator/__init__.py` | `bac506e05be4c49f85f2935c729b4cdb1513a8755cb8cdc3be0e24ddf41b5468` | Revalidado: cobertura del archivo revisada | Solo docstring; prueba con `find_packages` confirma que quitar este marcador excluye el paquete (`namespaces=false`). La conclusión se limita al rol de empaquetado de este archivo. |
| `cacao_accounting/accounting_engine/settlement/__init__.py` | `6e46b5a19df8303f48e44b5cd60cde6e2446e3024bf7c9558c63aa454278f7f0` | Revalidado: cobertura del archivo revisada | Solo docstring; prueba con `find_packages` confirma que quitar este marcador excluye el paquete (`namespaces=false`). La conclusión se limita al rol de empaquetado de este archivo. |
| `cacao_accounting/accounting_engine/snapshots/__init__.py` | `7c62ab06697b414c3043b88955acc5b4cd99c9c54bd3485cc3dbbc7b75a839d9` | Revalidado: cobertura del archivo revisada | Solo docstring; prueba con `find_packages` confirma que quitar este marcador excluye el paquete (`namespaces=false`). La conclusión se limita al rol de empaquetado de este archivo. |
| `cacao_accounting/admin/navigation.py` | `6bffae602a0ffa14021c277ec98da42080d8f7ad2de344d603dd296219ddb7e5` | Revalidado: cobertura del archivo revisada | Navegación y callers revisados estáticamente; SHA coincide. |
| `cacao_accounting/admin/templates/admin/inventory_valuation.html` | `22dd2989d47f854154321329ad213ff1cec888b8e410aa6eef89166fe8682082` | Reabierto: Parcial | Falta cotejar contexto, caller, permisos y render Jinja. |
| `cacao_accounting/api/line_import.py` | `1c0b646d29fd2a1b6f5dd3b631ae093e20ae73079e75ca25c7053d57813f529b` | Reabierto: Parcial | Falta trazar consumidores, payload y flujo de importación end-to-end. |
| `cacao_accounting/api/line_import_registry.py` | `9f34958a13bfa6cb4d6c056f36ac70b11cc2fba69efb4df0342a82cf8de9a151` | Reabierto: Parcial | Falta cotejar registro con callers/contratos de importación. |
| `cacao_accounting/api/templates/empy.html` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | Revalidado: cobertura del archivo revisada | Vacío (0 bytes), sin caller local; candidato dead code #1658 permanece registrado sin decisión de borrado. |
| `cacao_accounting/app/templates/app.html` | `e86a1a95c5acb5bea82a37c90ecc9724dcb16d333b7cc34b1f314d30b403ac99` | Revalidado: cobertura del archivo revisada | Template y contexto revisados estáticamente; SHA coincide. |
| `cacao_accounting/app/templates/development.html` | `55f2e8635cf6260fd4c691bc05fd37fb7c7a254ec0e727c31e51704218fbd490` | Revalidado: cobertura del archivo revisada | Template y contexto revisados estáticamente; SHA coincide. |
| `cacao_accounting/auth/README.md` | `7f095fc96749db2770e849207d3d3ad8a7bf8fc09a308e0935aa1a3323ac06e2` | Reabierto: Parcial | Falta confirmar vigencia y límites de exposición de credenciales de desarrollo. |
| `cacao_accounting/bancos/templates/bancos/caja_chica_conciliacion_lista.html` | `83f87dd53beb2b808a881eaa51b500795b03557c71cea9f23170aa8bbab4d080` | Reabierto: Parcial | Falta cotejar endpoint, compañía y ramas Jinja. |
| `cacao_accounting/bancos/templates/bancos/caja_chica_conciliacion_nueva.html` | `0f9708ca302840c8ec39732836d9da4d80ef2cef7c03a012c8927105c3105d7f` | Reabierto: Parcial | Faltan POST, validaciones, permisos y render Jinja. |
| `cacao_accounting/bancos/templates/bancos/caja_chica_gasto_lista.html` | `e81b0395acc701619415d85abc952a02a02db5812d49add547dd34c65bff4b84` | Reabierto: Parcial | Falta cotejar endpoint, compañía y ramas Jinja. |
| `cacao_accounting/bancos/templates/bancos/caja_chica_lista.html` | `0f65d5c91fe12ed604cd98969663db1eef6a0e5fb4e6625433df517a41b41c9f` | Reabierto: Parcial | Falta cotejar endpoint, compañía y ramas Jinja. |
| `cacao_accounting/bancos/templates/bancos/caja_chica_reposicion_lista.html` | `ad14d8029a61b91a505457c01e48baa0af16e68b2b05ddaef29bc71ed255467a` | Reabierto: Parcial | Falta cotejar endpoint, compañía y ramas Jinja. |
| `cacao_accounting/bancos/templates/bancos/caja_chica_vale_lista.html` | `2d1fb7e9613650e157c3f8fa7e506b5c76af5d7b6d8c3e89877caad7e1fb5eaf` | Reabierto: Parcial | Falta cotejar endpoint, compañía y ramas Jinja. |
| `cacao_accounting/bancos/templates/bancos/conciliacion_bancaria.html` | `6d3df3b2c861c63fbb03bd17f58b470b9f1ede035c5085c6fff1e3f44e73df61` | Reabierto: Parcial | Faltan formularios/endpoints y flujo de conciliación. |
| `cacao_accounting/bancos/templates/bancos/extracto_importar.html` | `a6152a0bee480fd3f28a088220020b69551b1810f3c800c147cdd45339ee0b82` | Reabierto: Parcial | Falta cotejar carga, validación y errores con el caller. |
| `cacao_accounting/bancos/templates/bancos/reglas_matching.html` | `5a253fdb2c635e3cd34875b3bd2e4268552046101f8e562a748e39233c897da6` | Reabierto: Parcial | Falta cotejar edición/prioridad y comportamiento de matching. |
| `cacao_accounting/cancellation_scope.py` | `da367ee15d5e89adbbfffda618c7cb06aec8efd770ef348e3a6e35ddfacc8844` | Reabierto: Parcial | Faltan callers y transiciones por módulo de cancelación/reversión. |
| `cacao_accounting/compras/__init__.py` | `2ab1f2fa06167ac89f5053fc605f7ee4d88012e403e020be24391f77f82fd883` | Reabierto: Parcial | Facade y contrato externo de imports no comprobados. |
| `cacao_accounting/compras/gr_ir_service.py` | `40e8efc6cc32c836d3e50a0c73aaee81469b67c4ff36468805ac06e467d6b9b8` | Reabierto: Parcial | Sin caller interno hallado; candidato legacy/dead #1074, contrato externo pendiente. |
| `cacao_accounting/compras/templates/compras/gr_ir.html` | `0c6170bd4d77cce6538dc0d85975104d9daee2d65e5b83e50a40f7936550ba95` | Reabierto: Parcial | Sin caller interno hallado; flujo #1074, contrato externo/render pendientes. |
| `cacao_accounting/contabilidad/__init__.py` | `2021d7e4372bac29938f1e5defbfcc3fa7f74ca62ce9084721bbdee0917c22e8` | Revalidado: cobertura del archivo revisada | Exports y contexto del paquete cotejados; SHA coincide. |
| `cacao_accounting/contabilidad/cancellation_service.py` | `6ad21da463c76e8e26fa86aeccb6b83b573d22172218901d98e1443fedc37dea` | Reabierto: Parcial | Faltan callers, atomicidad e invariantes de cancelación/reversión. |
| `cacao_accounting/contabilidad/ctas/catalogos/README.md` | `527d2a6380663a7881dce21e76b18ef1c44be75a4d65b21f33a21c1c65e9b419` | Reabierto: Parcial | Falta cotejar instrucciones contra catálogo y flujo actual. |
| `cacao_accounting/contabilidad/ctas/catalogos/base_en.json` | `4ab20ae98c196df9be6dc7788278c29db3a2e51370e304a150336ca0d2d34763` | Revalidado: cobertura del archivo revisada | Datos/estructura y uso del catálogo cotejados; SHA coincide. |
| `cacao_accounting/contabilidad/ctas/catalogos/base_es.csv` | `152b51e49d7298ea7114fdd386b9145ba4acc8e66d1dc8680b0bb7971851e9b7` | Revalidado: cobertura del archivo revisada | Datos/estructura y uso del catálogo cotejados; SHA coincide. |
| `cacao_accounting/contabilidad/ctas/catalogos/base_es.json` | `23d6c60b7df29bf72476eaca60bdbfac2a8a8da546ef970fde52c29bd2fdc79f` | Revalidado: cobertura del archivo revisada | Datos/estructura y uso del catálogo cotejados; SHA coincide. |
| `cacao_accounting/contabilidad/ctas/catalogos/ifrs_smes_en.csv` | `2c5b47c291ab669a4751b97c694fcdb84064ec5065a1a289b5286e11a60d0367` | Revalidado: cobertura del archivo revisada | Datos/estructura y uso del catálogo cotejados; SHA coincide. |
| `cacao_accounting/contabilidad/ctas/catalogos/ifrs_smes_en.json` | `7c7b6ce9e0e37003d655001e726ac38b93d889ce11309896d5ba9d6182b3f3ea` | Revalidado: cobertura del archivo revisada | Datos/estructura y uso del catálogo cotejados; SHA coincide. |
| `cacao_accounting/contabilidad/ctas/catalogos/niif_pymes_es.csv` | `b0fca7c57cd5d86e5b31a3651feb87c30b28bad0ea5b55fcb36d4738b4548f6a` | Revalidado: cobertura del archivo revisada | Datos/estructura y uso del catálogo cotejados; SHA coincide. |
| `cacao_accounting/contabilidad/ctas/catalogos/niif_pymes_es.json` | `9468aa9481d4117f2c919cb221f51610d5ba7ad401e2237ad2eab9b1aa69ee6c` | Revalidado: cobertura del archivo revisada | Datos/estructura y uso del catálogo cotejados; SHA coincide. |
| `cacao_accounting/contabilidad/ctas/catalogos/us_gaap.csv` | `3c2b6a876c367069fd9033432fdbea021dc97fcd713a46d92b0c7abf0548a444` | Reabierto: Parcial | Reabierto Parcial: dataset de 232 filas es consumido por cargar_catalogos; falta verificar jerarquía, tipos y compatibilidad del plan. |
| `cacao_accounting/contabilidad/ctas/catalogos/us_gaap.json` | `7758b2762355ee437895556e072124be8b4627994b1df8f065a4ea5a8652cea7` | Reabierto: Parcial | Reabierto Parcial: define archivo y cuentas predeterminadas; falta validar claves referenciadas y alta/setup. |
| `cacao_accounting/contabilidad/posting.py` | `35ad7f6353dc7eb192571851e13d0314f7c6e5a5960a3686d0ab96bfa40ae283` | Reabierto: Parcial | Reabierto Parcial: fachada __getattr__/__dir__ activa y consumida; falta comprobar exports y errores de atributos. |
| `cacao_accounting/datos/__init__.py` | `5a3ecee041f1586b2e3ff4b0b20a87b087cd8c1aea3bf075b5d332ee33a02bbd` | Revalidado: cobertura del archivo revisada | Revalidado: reexporta base_data/dev_data y restringe __all__; callers revisados, marcador de paquete requerido. |
| `cacao_accounting/document_flow/__init__.py` | `d5ff8a6b32185c847560d257d76e2da2e0cf9e08547dce942cfdca637bf74fa5` | Reabierto: Parcial | Reabierto Parcial: fachada pública amplia y activa; falta verificar compatibilidad de cada export. |
| `cacao_accounting/document_flow/status.py` | `a8bf81f0ad38ccc9f677f392ba974cfe611b3dc969decadbc641aaee33096c4e` | Reabierto: Parcial | Reabierto Parcial: 17 símbolos de cálculo/status; #1803 cubre solo subcaso; faltan estados y callers del payload. |
| `cacao_accounting/exceptions/mensajes.py` | `2a288afcf289803e40189cf91929e98df9535447f41e536b0966b60eda8bcd15` | Revalidado: cobertura del archivo revisada | Revalidado: revisión completa y búsqueda de consumidores documentadas en AUDIT_PROGRESS.md:650–654. |
| `cacao_accounting/i18n.py` | `3aab68395711b34f2d7bc8c1d366a92e76fdef306164f7282df5ca2e9593dc58` | Revalidado: cobertura del archivo revisada | Revalidado: funciones/callers y probe SQLite documentados en AUDIT_PROGRESS.md:762; SHA coincide. |
| `cacao_accounting/imports/__init__.py` | `b0d59722919fee914d682fd6ef623c287ec5b6a1a964f16db4fe9c0d6bc3f252` | Revalidado: cobertura del archivo revisada | Solo docstring; prueba con `find_packages` confirma que quitar este marcador excluye el paquete (`namespaces=false`). La conclusión se limita al rol de empaquetado de este archivo. |
| `cacao_accounting/imports/adapters/__init__.py` | `78c3ff4e42b9a3eb20f53f979a36078c109d7204a86857ee63a2cdade1a36056` | Revalidado: cobertura del archivo revisada | Solo docstring; prueba con `find_packages` confirma que quitar este marcador excluye el paquete (`namespaces=false`). La conclusión se limita al rol de empaquetado de este archivo. |
| `cacao_accounting/imports/adapters/bank_statement.py` | `8627d65ac34c36ea34161234cbfdf95892d67714f8b65369768a3dea4f48b420` | Reabierto: Parcial | Reabierto Parcial: tests existentes cubren parsing; #1385 y ciclo end-to-end de persistencia/reintento/aislamiento siguen sin cierre. |
| `cacao_accounting/imports/adapters/base.py` | `72d43415c2bc21dd7b24aba125c657d6087f36dea3dacccb45de8052f3df7a97` | Reabierto: Parcial | Reabierto Parcial: base común activa; falta revisar contrato y casos de error de localized_columns. |
| `cacao_accounting/imports/adapters/cash_forecast_entry.py` | `69431b749d452dc3cad3c8e1a433034e795af4750bce351ccc898310e033ab64` | Reabierto: Parcial | Reabierto Parcial: adaptador registrado; falta revisión de validaciones/persistencia y bordes. |
| `cacao_accounting/imports/adapters/chart_of_accounts.py` | `a3cd20ed8772d470c1c8bba94b922fa14592e1dae6440938cb280705e7f033e1` | Reabierto: Parcial | Reabierto Parcial: falta comprobar invariantes de padres, duplicados y atomicidad de importación. |
| `cacao_accounting/imports/adapters/journal_entry.py` | `190e12be69e2117045fc7db9291fc7675f1b646ac75c3a362ed28ecffe5b7ca9` | Reabierto: Parcial | Reabierto Parcial: falta balance por documento, multi-libro/moneda y atomicidad del lote. |
| `cacao_accounting/imports/adapters/purchase_order.py` | `26d3d52865b383a21cdabebf63aed8bc610140313c0dac607ecf0a33f0d5161f` | Reabierto: Parcial | Reabierto Parcial: falta moneda destino, referencias y comportamiento ante fallos parciales. |
| `cacao_accounting/imports/adapters/transaction_documents.py` | `763f3c46551d9d11cd7285f65e7b2bbba6c26f52ef7ab3b1fb76f3f569975aa2` | Reabierto: Parcial | Reabierto Parcial: 12 clases/configuraciones; falta cobertura de invariantes por tipo de documento. |
| `cacao_accounting/imports/column_labels.py` | `b8b10ba515da6157871b79d5375af5d4238689c76dc8b03ae8375a9bb815436b` | Reabierto: Parcial | Reabierto Parcial: falta validar colisiones, locale y columnas desconocidas de localized_columns/canonical_columns. |
| `cacao_accounting/imports/models.py` | `73355208b4c2c45e34d0c8f621af08342c2219f20c1f466077a411edc6d49c30` | Reabierto: Parcial | Reabierto Parcial: tests cubren recuperación/cancelación parcialmente; faltan constraints y transiciones/relaciones completas. |
| `cacao_accounting/imports/readers/__init__.py` | `43ebcc946778abd746dc9e9b4e5295be6cb5c13e71e2b7ded7cdbf002d58599a` | Revalidado: cobertura del archivo revisada | Solo docstring; prueba con `find_packages` confirma que quitar este marcador excluye el paquete (`namespaces=false`). La conclusión se limita al rol de empaquetado de este archivo. |
| `cacao_accounting/imports/readers/base.py` | `03a2cc038310d76fd7f5ee5f1ccd02eff06185f1fb0a9e1dc970cda6b9368052` | Reabierto: Parcial | Reabierto Parcial: NormalizedTable/BaseReader usados por cuatro lectores; faltan entradas vacías e irregulares. |
| `cacao_accounting/imports/readers/csv_reader.py` | `c8ed9e4ffe374009964efba660c68ff705807300e90112b2e262074bfa77283a` | Reabierto: Parcial | Reabierto Parcial: falta cobertura de encoding, delimitadores ambiguos y filas irregulares. |
| `cacao_accounting/imports/readers/ods_reader.py` | `b6f6de503df5d678a3ede5600067cb4835ff316682de2631e40df88d7a7e6fdf` | Reabierto: Parcial | Reabierto Parcial: faltan casos de hojas vacías/sin tabla y límites de celdas repetidas. |
| `cacao_accounting/imports/readers/xls_reader.py` | `9332b3c662858b6b59a0f00b938cb4933820774a3c52ea79d9c4bc401ca20627` | Reabierto: Parcial | Reabierto Parcial: lector registrado sin evidencia funcional específica. |
| `cacao_accounting/imports/readers/xlsx_reader.py` | `3485ed69c1e46f78d51d21d0274bdba0df9d724fae1bc2601e79215f2536b946` | Reabierto: Parcial | Reabierto Parcial: test de archivo corrupto no cubre lector/tipos de celda integralmente. |
| `cacao_accounting/imports/routes.py` | `bc6a1c38e920c5febf2bde0e7bbdd890a7e962c309c3a955816841c83b0bd6de` | Reabierto: Parcial | Reabierto Parcial: 17 rutas/helpers; falta trazar permisos, límites/MIME y transiciones validate/execute/cancel. |
| `cacao_accounting/imports/services/__init__.py` | `64846651a8062553da6b2d0805a4aa60652cfb2cf80b16eb7d6fd767dd7ce514` | Revalidado: cobertura del archivo revisada | Solo docstring; prueba con `find_packages` confirma que quitar este marcador excluye el paquete (`namespaces=false`). La conclusión se limita al rol de empaquetado de este archivo. |
| `cacao_accounting/imports/templates/imports/detail.html` | `7fca20dda0c4d37f01739496b59b6b796b3aa322a8261e3c14c039b13bf65b7f` | Reabierto: Parcial | Reabierto Parcial: falta cotejar estados y acciones Jinja con endpoints/permisos/escaping. |
| `cacao_accounting/imports/templates/imports/index.html` | `9c7c51928a9adf161eae67d207e889e8d20cf73755ff57ff051ce6150a6d1448` | Reabierto: Parcial | Reabierto Parcial: falta render/ACL por rol y estados vacíos/error. |
| `cacao_accounting/imports/templates/imports/new.html` | `bfa1638882b1dec7e8b757640f2637bb363224f7f6ff2a15fc86a8c5cdd3023e` | Reabierto: Parcial | Reabierto Parcial: falta validar submit, errores de formulario y aislamiento del selector de compañía. |
| `cacao_accounting/imports/utils/__init__.py` | `fe612415b271fb4aeb9de0f82746306741c37c64d72d9b34f3eeb4292ab3804b` | Revalidado: cobertura del archivo revisada | Solo docstring; prueba con `find_packages` confirma que quitar este marcador excluye el paquete (`namespaces=false`). La conclusión se limita al rol de empaquetado de este archivo. |
| `cacao_accounting/imports/utils/recovery.py` | `f28a0bec1e5b02f8ac6497666fa0349d22fa61757908818d5a3c6c1d61e73129` | Reabierto: Parcial | Reabierto Parcial: faltan estados concurrentes, atomicidad y relación completa con execute(). |
| `cacao_accounting/imports/utils/validation.py` | `9feeaf2398008cf7a93f139683ba73ce94069ba498b60d1560d21fc4c1b31a2c` | Reabierto: Parcial | Reabierto Parcial: is_period_open tiene callers; faltan límites de fecha y periodos cerrados por compañía. |
| `cacao_accounting/inventario/__init__.py` | `c5805068eb9d1ffc6b6a23e8d716a8e0c5d5f4aa3292f60e55d4e10847d56a4d` | Reabierto: Parcial | Reabierto Parcial: fachada dinámica usada por app; falta validar compatibilidad de exports y ciclos de import. |
| `cacao_accounting/inventario/templates/inventario/articulo_lista.html` | `9f7846291dfd87572bc28e189155c59c483b077e015c882d601f4f0bb8d70ec7` | Reabierto: Parcial | Reabierto Parcial: falta render con ACL, moneda/cantidades y conjunto vacío. |
| `cacao_accounting/inventario/templates/inventario/articulo_nuevo.html` | `c538c395a6b35036ea8d2dc1d2c5ca5759ab06d6e547ec315b2cd0f79680a617` | Reabierto: Parcial | Reabierto Parcial: formulario de 655 líneas; falta cubrir create/edit, UOM, campos y errores. |
| `cacao_accounting/inventario/templates/inventario/bodega.html` | `de2341fd8e24e6470afd3702aea9b8b4396b3fe44c1b9a91af971b6cc7806d09` | Reabierto: Parcial | Reabierto Parcial: falta validar permisos, estado y relaciones en el detalle. |
| `cacao_accounting/inventario/templates/inventario/bodega_lista.html` | `86df93f49ae4359e5a67b36fd3c9cb04a584f597e10318d53a786ae6b0c460e1` | Reabierto: Parcial | Reabierto Parcial: falta comprobar scope de compañía y acciones visibles. |
| `cacao_accounting/inventario/templates/inventario/bodega_nuevo.html` | `f6ca37dc92df532e90584a9b9056a3cc3740517be8e15a6f7523dbcaec30e0eb` | Reabierto: Parcial | Reabierto Parcial: falta cotejar formulario create/edit y JS contra route/service/validación. |
| `cacao_accounting/inventario/templates/inventario/lote.html` | `0c435685bf643a808c2515f2fcd0bef35a7af6c3a369874a50ff13eee4c12c0f` | Reabierto: Parcial | Reabierto Parcial: faltan estados, relaciones, scope compañía y condiciones sin datos. |
| `cacao_accounting/inventario/templates/inventario/lote_lista.html` | `23ec9584570d02699fcde24899cd0e4410ec62dc3c5ab1cbfd8854f73b42fe1d` | Reabierto: Parcial | Endpoint lista Batch sin filtro de compañía (#1540); falta validar scope. |
| `cacao_accounting/inventario/templates/inventario/lote_nuevo.html` | `e17f2d0fe04733141deffd2de5083221af9d2a8dcba037dd94c1a7532d2ed402` | Reabierto: Parcial | Falta cotejar alcance multiempresa de artículo/lote y caller. |
| `cacao_accounting/inventario/templates/inventario/uom.html` | `e8ccb574732a23d2bc75b9b5a135d03da433980bbfd286a32fc538dc944b5279` | Reabierto: Parcial | Falta caller y contrato de detalle de UOM global. |
| `cacao_accounting/inventario/templates/inventario/uom_lista.html` | `fbc7993222551bf37c517b898c99b23592ea19be29da79418cc48dd158ab0b8f` | Reabierto: Parcial | Falta caller y alcance de lista UOM. |
| `cacao_accounting/inventario/templates/inventario/uom_nuevo.html` | `e3daf6f8e31a2bc47b4470330fd2438bd6fc43b2591412344e6a07a574eddc36` | Reabierto: Parcial | POST continúa cuando validate_on_submit falla; se eluden validaciones WTForms. |
| `cacao_accounting/logs.py` | `9c3bb1f808b217f31ff48c9c5e14de9ea56f8530f28d4dfc1bf5f6b4b85fba26` | Revalidado: cobertura del archivo revisada | Archivo y usos completos revisados; SHA coincide. |
| `cacao_accounting/messaging/__init__.py` | `b971b6e9640e82d005156cb310d30828d9d4561ab6b02c47b05597a52d7c54c2` | Revalidado: cobertura del archivo revisada | Solo docstring; prueba con `find_packages` confirma que quitar este marcador excluye el paquete (`namespaces=false`). La conclusión se limita al rol de empaquetado de este archivo. |
| `cacao_accounting/migrations/20260809_0001_baseline.py` | `722220b28ff7d6bc1ba264fea3aabca14e9f886c5b1567b15a28798594261d0f` | Revalidado: cobertura del archivo revisada | Revisor independiente inspeccionó `upgrade()`/`downgrade()` no-op: la revisión baseline delega esquema a `create_all()`. Sin operaciones mutantes que probar. |
| `cacao_accounting/migrations/script.py.mako` | `f3fc6003e826fce85e8673bb0a22228d68279b4d1996ccc41ed207ac0605265d` | Revalidado: cobertura del archivo revisada | Template renderizado con Mako y Python generado validado por `ast.parse`; producción de migración se limita a stubs upgrade/downgrade e ids/config suministrados. |
| `cacao_accounting/module_badges.py` | `8f10f17f61e63bf4b2a9b3412166ce2b56b66127025f06d6f973a0c69dc1ad46` | Revalidado: cobertura del archivo revisada | Clase/metadata y todas las funciones cotejadas. Prueba en Flask app context confirma cinco estados; AST revisó 134 callsites Jinja con keywords de firma válidos. #1912 describe una llamada `required_permission` que no está en este HEAD (el menú usa `required=`); se comentó evidencia y queda pendiente resolver el issue externamente. El fallback `module`/`user_id` de `_resolve_access` no tiene caller local identificado; candidato #1658, contrato externo no descartado. |
| `cacao_accounting/printing/__init__.py` | `9bc17706c4c655dcb15544ac4c7a79c5d0406e4b71c19a6b6c6553d92622dc1c` | Reabierto: Parcial | Falta validar init_printing, caller app factory y fallo de seed/tablas. |
| `cacao_accounting/printing/routes.py` | `1c9643b034825d6b18d88de634ccd6c5aa517390d7bddfc0853deb90e060ac49` | Reabierto: Parcial | Faltan permisos/callers, URL de retorno y tests directos. |
| `cacao_accounting/printing/templates/admin/print_template_form.html` | `13f4f0fdc82fe27253c30f7ea908510466961487b175bb7ebb52ffd90ea31375` | Reabierto: Parcial | Reabierto por HTTP render vacío: define `block content`, base declara `contenido`; issue #1928. #1761 CSRF queda pendiente cuando vuelva a renderizarse. |
| `cacao_accounting/printing/templates/admin/print_template_list.html` | `2cf76c7057c13be877821da506e2e53253ed2beb2e77ef6352fc93c9340b655b` | Reabierto: Parcial | Reabierto por mismatch `content`/`contenido`: HTTP 200 omite UI; #1928. Historial `versions` tampoco se muestra (#1931). |
| `cacao_accounting/printing/templates/admin/print_validation_settings.html` | `3580dc9ee28939979da9a8233e6d6db3971b832d2e0d055b9a6baecb5eee4a21` | Reabierto: Parcial | Reabierto por mismatch `content`/`contenido`: HTTP 200 omite ajustes; #1928. CSRF presente para POST al volver a renderizarse. |
| `cacao_accounting/query_tools/context.py` | `0fe3c8d844fd99b38b6f0bbbac0c85a58184dad32c9e2815f715230a91179cc5` | Revalidado: cobertura del archivo revisada | Contexto, compañías y permisos cotejados con publication/#1338. |
| `cacao_accounting/query_tools/handlers/__init__.py` | `1d4a3c239554298df55ad684717e4346b1f94ebc34852bfaff2c8b0d51876a22` | Revalidado: cobertura del archivo revisada | Solo docstring; prueba con `find_packages` confirma que quitar este marcador excluye el paquete (`namespaces=false`). La conclusión se limita al rol de empaquetado de este archivo. |
| `cacao_accounting/query_tools/handlers/aging.py` | `89e65910563d8ec593978e71c2a45333c11784c0c0d6f2beb82d3f3ddb06db64` | Revalidado: cobertura del archivo revisada | Funciones/callers cotejados; defecto de créditos en aging sigue en #1585. |
| `cacao_accounting/query_tools/schemas/__init__.py` | `964404e2db9b7fb99ce9bbd02e416b790945038b48890c79af96b7622560e1b4` | Revalidado: cobertura del archivo revisada | Solo docstring; prueba con `find_packages` confirma que quitar este marcador excluye el paquete (`namespaces=false`). La conclusión se limita al rol de empaquetado de este archivo. |
| `cacao_accounting/reportes/documentos.py` | `13046a1af261fb8303bbb92a2069ea130c3037e564e56ed635bb1ef6c9d21a3b` | Revalidado: cobertura del archivo revisada | Whitelist, compañía, líneas y callers revisados. |
| `cacao_accounting/reportes/templates/reportes/cash_flow_blocked.html` | `6af4e600692a2763d82d75c1b04acdfc85d6d0cfb530c9b053aaa625880eed5d` | Revalidado: cobertura del archivo revisada | Caller, permiso y escape Jinja revisados; no consta render. |
| `cacao_accounting/reportes/templates/reportes/report_pdf.html` | `835883c1a2e7b3c068b3ef64925b43145ddc0ab22d84a6a246c9c17b73d3f4cd` | Revalidado: cobertura del archivo revisada | Caller y escape Jinja revisados; render real con `_write_report_pdf()` en app context SQLite generó PDF de 9,001 bytes con firma `%PDF-`; requirió instalar runtime nativo Pango/Cairo en este entorno. |
| `cacao_accounting/runtime_mode.py` | `496037c247616fc535537297e5a7c751b5dbd2da350ba9f5bf916f10ede8e409` | Reabierto: Parcial | Callers Desktop/Cloud en auth/setup/API/cache/permissions/templates sin cotejo integral. |
| `cacao_accounting/setup/catalogs.py` | `def83f1cb85bb9213f1ef6a28225c218bcfe4d60768c0e171651c9e35c3d49eb` | Revalidado: cobertura del archivo revisada | Catálogos/consumers revisados y sonda runtime documentada. |
| `cacao_accounting/static/js/dashboard.js` | `b0267ac12731224fd6441a5be1e28932052139042c7b423e089d2c66f5c8e84a` | Revalidado: cobertura del archivo revisada | Revisado con #1856 abierto; test relacionado no cubre moneda inválida ni se ejecutó ahora. |
| `cacao_accounting/static/js/sw.js` | `a27c7e258fbd23fc36681b4806a820178cd9f31f5143c88ef08ae3b58a11499e` | Revalidado: cobertura del archivo revisada | Registro/callers y contrato network-only revisados; test no ejecutado en esta ronda. |
| `cacao_accounting/templates/400.html` | `e5710b3a93e555066f37399490fe7ac742410f4ea9d8f0210ed2275e925ed80f` | Revalidado: cobertura del archivo revisada | Handler, traducción y status cotejados. |
| `cacao_accounting/templates/403.html` | `82acf8f7a18e9e488269b4d304718ca00d86111fa59c1fce03453ebf34febe91` | Revalidado: cobertura del archivo revisada | Handler revisado; mensaje genérico sin datos internos. |
| `cacao_accounting/templates/404.html` | `5c31cbe12c008ee5312bc25b0d9fd51b68c1731a598f8b680c464525702b8ba5` | Revalidado: cobertura del archivo revisada | Handler revisado; mensaje genérico sin datos internos. |
| `cacao_accounting/templates/public/confirm_balance_status.html` | `e9b8ed7fd0d7489dfc2553fc517f474a371ce5a0709f7452820eac349b49a6bb` | Reabierto: Parcial | Falta render Jinja con contexto real del endpoint. |
| `cacao_accounting/templates/public/confirm_balance_success.html` | `541a2d5076dd002728d29e216bf56f8ef987aea7500f85f4a8cec8453abbe7c2` | Reabierto: Parcial | Falta render con objeto/contexto real, incluido responded_at. |
| `cacao_accounting/templates/public/confirm_balance_verify.html` | `acfec376d14ed19e5b3096565a976979a56f90bb1e27752f4c5ee22ce66e9000` | Reabierto: Parcial | Falta render/HTTP del formulario y mensajes públicos. |
| `cacao_accounting/templates/public/confirm_balance_view.html` | `12f7ddbfb42143f2cfd57b6543ee9701300de4f52ad5c292c0fc3d228f056339` | Reabierto: Parcial | Falta render con snapshot vacío/poblado y ramas Alpine. |
| `cacao_accounting/templates/public/validation_result.html` | `d611e5b76817f63cc36ab3b0c83a97f9ff634c9527c0c00bf634b1f7c2586a8c` | Reabierto: Parcial | Faltan renders de estados valid, invalid y alternativo. |
| `cacao_accounting/ventas/__init__.py` | `397671ed43d9458999142fd60738bc82228b171c27a7e3a3d1aadaddcb2ba5c3` | Reabierto: Parcial | Facade __getattr__/__dir__ sin cobertura; imports externos no comprobados. |
| `cacao_accounting/ventas/forms.py` | `30ff300854eb4a52078209807e418aeaa965a5bb1dcb40d943d77e1a9ee7f83f` | Reabierto: Parcial | Faltan choices, validadores, coerción y tests de formularios. |
| `cacao_accounting/version/__init__.py` | `40306592970163929adc46c40bb0e8263037e01febfac8b4edc267ac468d72cb` | Revalidado: cobertura del archivo revisada | build_version/VERSION y consumers setuptools/app/CLI revisados; build no ejecutado. |
| `cacao_accounting/warehouse_accounting.py` | `628189fc05f334f40c27985dba77c0610e59765bf8e3ed682bfbe63f02be5a62` | Revalidado: cobertura del archivo revisada | Revisor independiente cotejó ambas funciones/callers; #1827 conserva mismatch. |

## Cierres nuevos posteriores al manifiesto histórico

| Ruta | SHA-256 | Estado de evidencia | Referencia disponible |
|---|---|---|---|
| `cacao_accounting/templates/smart_select_field.html` | `aafca33daee797f5e223d8bd53bc284188222e3472adcb1720940c04b0630f9f` | Revalidado: un macro, todos los argumentos, 40 invocaciones en 8 templates, y contrato de render revisados | Jinja render comprobó JSON/atributos escapados y `x-text` para resultados/errores; labels actuales son literales traducidos confiables. Suite Mocha Smart Select: 30 passing. `tests/test_cross_module_acl.py`: 4 passed; el catálogo `user` filtrado incorrectamente por el endpoint es hallazgo separado #1321. Incidencias de interacción mapeadas: #1855 (limpiar escribiendo no notifica filtros), #1976 (opciones no seleccionables por teclado; también afecta el macro de transacciones). Fallos de doctype en llamadas de presupuesto se registran bajo #1977, no se atribuyen al macro. |


### Cierre posterior — Bodegas (2026-11-05)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/inventario/templates/inventario/bodega.html` | `de2341fd8e24e6470afd3702aea9b8b4396b3fe44c1b9a91af971b6cc7806d09` | Completo: se cotejó el detalle con `inventario_bodega()` y el query de configuración de compañías/cuentas; curl anónimo 302, detalle propio 200 y ajeno 403. Lista sin enlace a detalle queda como candidato de integración/retiro bajo #1658; no borrar sin decidir contrato externo. |
| `cacao_accounting/inventario/templates/inventario/bodega_lista.html` | `86df93f49ae4359e5a67b36fd3c9cb04a584f597e10318d53a786ae6b0c460e1` | Completo: listado/campos/paginación cotejados con `inventario_bodega_lista()` y scope; curl anónimo 302, usuario sin rol 200 vacío, viewer de cacao 200 sin filas de secret. #1976 cubre el selector compartido; no hay link a detalle en filas. |
| `cacao_accounting/inventario/templates/inventario/bodega_nuevo.html` | `f6ca37dc92df532e90584a9b9056a3cc3740517be8e15a6f7523dbcaec30e0eb` | Completo: formulario, CSRF, Smart Select, encoding `tojson`, required filters y ruta/server-side validation cotejados. Curl anónimo 302; sin rol 403; viewer autorizado 200; POST con code/name vacíos devolvió 302 y persistió registro vacío, reproducido bajo #1183. #1976 aplica a opciones por teclado; defectos quedan abiertos y no impiden documentar el archivo. |

QA HTTP independiente: `tests/test_inventory_company_scope.py` pasó 3/3; son pruebas de stock-entry/helpers, no una suite específica de bodegas y no se atribuyen como cobertura directa de estas plantillas. No se modificó código productivo.


### Cierre posterior — Contadores externos (2026-11-05)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/contabilidad/templates/contabilidad/external_counter_lista.html` | `feba655e5c467c53f06b6c11ed497875d4ef932840e8530b4270054ca3e71fd6` | Completo: Lista y controles renderizados y cotejados con handler. `curl` anon 302; viewer con `accounting access/view` y sin create/edit recibe 200 y ve `SECRET-FISCAL` de secret si no envía filtro; filtro `company=cacao` sí lo oculta. Viewer puede acceder a new/edit/adjust/audit con 200. Toggle admin sin CSRF 400; con CSRF válido viewer muta estado (20/21 y toggles probados), bajo #1601/#1649/#1761. Comentario #1649 `6671317950`. |
| `cacao_accounting/contabilidad/templates/contabilidad/external_counter_nuevo.html` | `fe8dc7c779fc5741476ef0570eb1e8b2925248c1853b960d1071681dc942ce31` | Completo: Formulario, campos y POST renderizados. Viewer read-only con alcance cacao obtuvo GET 200 y creó contador asignado a secret mediante POST CSRF válido (#1601/#1649; comentario #1601 `6671317456`). Los placeholders de nombre/prefijo aparecen literalmente como expresión Jinja en HTML (#1780, mismo mecanismo; comentario `6671318660`). |
| `cacao_accounting/contabilidad/templates/contabilidad/external_counter_ajuste.html` | `dc7aaba330ca47adf2daafbeabd9e81129f26fc9cc33e574f319db5e65b79d2d` | Completo: Resumen, campos requeridos y CSRF cotejados; viewer read-only abrió/ajustó contador de secret con motivo y CSRF válido, cambió 20→21 y creó bitácora. Helpers rechazan ajuste inválido/contador inactivo; no se probó cada excepción HTTP. Scope/acción omitidos #1601/#1649; motivo placeholder Jinja literal, dedupe #1780. |
| `cacao_accounting/contabilidad/templates/contabilidad/external_counter_auditoria.html` | `0f37a53251680807095452f5257059636a6e492c0584ae5aac64e5f865a52fd0` | Completo: Vista de auditoría accesible por viewer de solo lectura y contador de secret (HTTP 200); renderizó fila 20→21 con motivo/usuario después del ajuste real. Rama vacía estática cotejada. Autoescape Jinja; acceso cross-company queda registrado en #1649. |

Las cuatro plantillas se cotejaron con rutas/formularios/helpers; cobertura HTTP incluye lista/filtro opcional, alta, edición, ajuste con motivo y audit log. Los defectos de autorización/alcance continúan abiertos bajo #1601/#1649, CSRF #1761, último número sin auditoría al editar #1733 y placeholders literales #1780. No se modificó código productivo.

### Cierre posterior — Alta de cuenta bancaria (2026-11-05)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/bancos/templates/bancos/banco_cuenta_nuevo.html` | `2468ae72cd2829f1de3e70ea6426a2f299634ea6bda92d4f8e64cf59d5cc0449` | Completo: se cotejaron los nueve campos visibles/ocultos, CSRF, Smart Select, filtros por compañía/tipo y ruta de alta. GET admin real con `curl` renderizó HTTP 200; la matriz Flask/SQLite QA confirmó anon 302, sin permiso/view-only 403, compañía ajena 403 sin persistir, POST sin CSRF 400, referencias inválidas no insertan, alta válida 302 y genera las cinco configuraciones de tipo de pago. Se reprodujeron y abrieron #1979 (moneda inactiva aceptada pese a selector activo) y #1980 (número duplicado produce 500; unique constraint conserva una fila). |
| `cacao_accounting/bancos/templates/bancos/banco_cuenta_lista.html` | `fcd8467813561f160fe7b3febe4f7601f24b6ea3cbef2b4ed40d136a2ccab76c` | Completo: lista, links, filtro, paginación y scope cotejados con la ruta. Curl real: anon 302; sin RBAC lista 200 vacía y alta 403; viewer `cash.view` de cacao ve solo su cuenta, no la de secret, y detalle ajeno 403; admin ve ambas. `search` y paginación llegan a HTTP 200, mantienen el filtro en el link siguiente y escapan `<script>` en el campo de búsqueda. La CTA `Nuevo` aparece sin `cash.crear`, issue #1981 `needs-review` para decidir ocultar/deshabilitar; no se observó bypass. |

QA independiente: una sonda focal pasó 1/1; sus archivos temporales se retiraron. La aceptación de moneda inactiva se confirmó porque el formulario arma choices con todas las monedas aunque el endpoint Smart Select solo devuelve activas. La colisión de número es secuencial, no se probó concurrencia. Evidencia y límites quedan en `AUDIT_PROGRESS.md` y issues #1979/#1980; ambos se mantienen abiertos.

La navegación HTTP del listado se realizó contra un servidor Flask temporal con `curl`; la base SQLite y cookies temporales se eliminaron al finalizar. La ruta new también se abrió por `curl`; su matriz POST se verificó con cliente Flask en SQLite para comprobar CSRF y persistencia.

### Cierre posterior — Detalle de cuenta bancaria y numeración (2026-11-05)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/bancos/templates/bancos/banco_cuenta.html` | `24942aa9686f47d3d2a2c18040cdb455758f7ad94e68df5c52968cbc861e46cf` | Completo: navegación, campos de detalle, estados, cinco tipos de pago, edición Alpine, referencias de serie/contador, traducciones, escaping y rutas asociadas cotejados. Curl Flask/SQLite: anónimo 302; no-role 403; viewer `cash.view` propio 200/compañía ajena 403; admin 200. HTML renderizado contiene `x-data` y tabla, pero no la función ni URL API: el layout no declara `block scripts` (#1934, comentario `6672065581`). El `fetch` del bloque omite CSRF (#1645). CTA `Nuevo` visible a viewer sin permiso de alta y endpoint 403 (#1981, comentario `6671951870`). QA independiente probó GET/POST API: viewer POST 403; admin POST sin CSRF 400 y válido 200; payload ajeno 400 sin persistencia parcial. El guardado acepta serie inactiva (#1982, candidato #1716) y referencias de tipo incompatible/contador `other` (#1983, candidato #1717; consecuencia de serie vinculada a #1808). Defectos identificados, sin cambio de producto; la revisión del archivo queda cerrada. |

QA independiente terminó los casos de API con fixture SQLite y retiró sus temporales; la sonda/servidor del agente principal también se retiraron. Los issues permanecen abiertos y los roots `needs-review`; el cierre del archivo significa cobertura de auditoría, no resolución de defectos. Estado tras este cierre: **58/564 rutas completas, 506 parciales; HTML/Jinja 19/252 completas y 233 parciales**.


### Cierre posterior — Listado de Caja Chica (2026-11-05)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/bancos/templates/bancos/caja_chica_lista.html` | `0f65d5c91fe12ed604cd98969663db1eef6a0e5fb4e6625433df517a41b41c9f` | Completo: trazados endpoint y _cash_company_codes, columnas/cálculos de saldo, vales y reposición, responsable/default/activo, detalle enlazado, Jinja/gettext y escape. Curl Flask/SQLite: anónimo 302; sin rol 200 vacío; viewer de cacao 200 solo sus filas y alta 403; admin ve cacao/secret y alta 200; detalle propio 200/ajeno 403; parámetros de compañía/página no expanden scope (el handler no implementa filtros/paginación). Se renderizaron filas activas, inactivas y predeterminadas y payload `<script>` autoescaped; empty state confirma nueve headers contra `colspan=8` (#1975, comentario `6672170726`). CTA `Nuevo` visible para no-role/viewer aunque alta 403, extendido a #1981 (`6672171254`). La atribución antigua a #1647 era errónea: esta plantilla solo enlaza detalle válido; #1647 cubre links inexistentes en vales/reposiciones. Una sonda temporal pasó 1 test focal y fue retirada; sin prueba permanente. |

El viewer y usuario sin roles obtienen lista vacía por company-scope; la distinción 200 vacío/403 continúa bajo decisión #1649. #1975 y #1981 quedan abiertos. Conteo vigente: **59/564 rutas completas, 505 parciales; HTML/Jinja 20/252 completas, 232 parciales**.


### Cierre posterior — Detalle de Caja Chica (2026-11-05)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/bancos/templates/bancos/caja_chica.html` | `faa8f807509102fbc52e303d9e181426e74b0407472807a3338c4c34f3a17c7e` | Completo: navegación, datos de fondo/compañía/GL/moneda/responsable, cálculos de saldo/vouchers/reposición, notas opcionales, badges/ramas, gettext, escaping y formularios de acciones cotejados con detail/edit/default/toggle handlers y servicios. Curl Flask/SQLite: anónimo 302; no-role propio/ajeno 403; viewer propio 200/ajeno 403; admin ambas compañías 200. XSS en name/notes autoescaped. Admin POST toggle sin CSRF 400, viewer con CSRF 403, admin válido 302 y persistió activo→inactivo; default válido cambió X→Y solo dentro de la compañía. Sin formulario browser/Alpine en el template. #1498 ya cubre desactivar fondos con vouchers entregados; evidencia del handler/servicio comentada (`6672218579`), pero no se recreó un delivered voucher en este pase. #1326 cubre carrera concurrente al marcar default; esta prueba fue secuencial y no valida race. #1646 está en la ruta/template de edición separada y no se atribuye a este detalle. |

QA independiente retiró servidor, DB y respuestas temporales. La vista queda auditada; la decisión de negocio de #1498 y la race #1326 continúan abiertas. Conteo vigente: **60/564 rutas completas, 504 parciales; HTML/Jinja 21/252 completas, 231 parciales**.


### Cierre posterior — Alta y edición de Caja Chica (2026-11-05)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/bancos/templates/bancos/caja_chica_nuevo.html` | `14f8f332b3fb120d79fb216b463e268a2246eaf47490f772d169464bcfeb504a` | Completo: create/edit branches, inputs y Smart Select, CSRF, gettext/JSON strings, rutas y backend cotejados. Curl Flask/SQLite create: anon 302; no-role/viewer 403; creator/admin 200. CSRF ausente 400; foreign company 403; cuenta requerida ausente/ajena, moneda desconocida/inactiva/no coincidente, monto negativo, custodian inválido/no autorizado y nombre duplicado no persisten; alta válida 302 y persiste; default secuencial único. `float_amount=abc` → HTTP 500 `decimal.InvalidOperation` (#1984 candidato #1650). Checkbox `is_active` omitido → True (#1962); edición ignora `name`, `is_active`, `is_default` (#1646 ampliado `6672333821`); cuenta Smart Select requerida devuelve 403 al cash creator sin `accounting.consultar`, admin 200; se dejó como requisito de flujo pendiente de decisión y evidencia en #1327 (`6672334619`). POST de alta inválido refleja custodian_id en `x-data`; el parser HTML decodifica entidades y Node ejecuta la expresión: XSS reflejado, no stored/cross-user probado (#1985, relacionado con #1867, root #1711 candidato; comentarios `6672305683`/`6672306100`). Matriz edit: anon 302; no-role/viewer 403; editor cacao GET 200 y no ve Secret; POST sin CSRF 400; target secret 403; POST adulterando company no cambia pertenencia ni identidad del fondo; admin control positivo 200. El payload custodian malicioso no se refleja en edit POST (redirect), limitando la XSS al re-render de alta inválida. Prueba/sesión/DB temporales retirados. |

Cobertura del archivo cerrada con los defectos y el criterio cross-module registrados; no se modificó código/tests permanentes. Conteo en ese checkpoint: **61/564 rutas completas, 503 parciales; HTML/Jinja 22/252 completas y 230 parciales**.

### Cierre posterior — Lista de gastos de Caja Chica (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/bancos/templates/bancos/caja_chica_gasto_lista.html` | `e81b0395acc701619415d85abc952a02a02db5812d49add547dd34c65bff4b84` | Completo: rutas, scope, estados, columnas, traducción/escape y cancelación contrastados por lectura de caller y curl Flask/SQLite. Anónimo 302; no-ACL 200 vacío; viewer cacao no ve Secret; admin ve ambas entidades; query adulterada no amplía scope. CSRF ausente 400; usuario con `cash.anular` sin `cash.editar` rechaza 403 (#1192); cancel admin validada por HTTP deja `docstatus=2` y evidencia GL con cancelación append-only. Defectos siguen abiertos: CTA Nuevo visible sin `cash.crear` (#1981, comentado en #1711); falta company/fondo por fila (#1990, candidato #1711, relacionado #1883). Probe temporal retirado; sin cambios de producto/tests permanentes. |

Cierre vigente: **62/564 rutas completas, 502 parciales; HTML/Jinja 23/252 completas, 229 parciales**.

### Cierre posterior — Conciliación de Caja Chica (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/bancos/templates/bancos/caja_chica_conciliacion_lista.html` | `83f87dd53beb2b808a881eaa51b500795b03557c71cea9f23170aa8bbab4d080` | Completo: todas las ramas de status y acciones fueron renderizadas con Flask/SQLite; anon 302; no-role 200 vacío; viewer limitado ve solo propia, admin ve ambas; contenido malicioso escapado. GET/POST editar/conciliar/ajustar de fila ajena 403; POST sin CSRF 400; conciliación válida de draft pasa a `status=conciliado`, `docstatus=1`; cuenta de ajuste inexistente no crea journal. #1883/#1885 describen ausencia de company/fund/moneda y status sin gettext; viewer/no-role ven acciones CTA cuyo endpoint da 403, candidato #1711. Comentarios `6672934259`, `6672934762`, `6672935100`. Sin cambio de producto/tests permanentes. |
| `cacao_accounting/bancos/templates/bancos/caja_chica_conciliacion_nueva.html` | `0f9708ca302840c8ec39732836d9da4d80ef2cef7c03a012c8927105c3105d7f` | Completo: create/edit con curl Flask/SQLite, matriz anon/no-role/viewer/editor/admin/compañía ajena, CSRF, posteos draft, duplicado, fechas, negativos y recálculo de importes. Compañía/fondo ajenos rechazados; duplicado no duplica; create/edit válidos persisten cifras derivadas sin alterar GL. Fecha histórica en periodo cerrado se acepta como borrador; no se declara issue sin política de corte. `counted_cash=abc` → 500 en create, duplicado exacto #1185 bajo #1650; el edit sí captura `InvalidOperation`. #1884 confirma pérdida de datos al re-render; #1883 falta moneda/unidad del conteo y compañía/fondo reconocibles. Comments: #1883 `6672950070`, #1884 `6672950539`, #1185 `6672950861`, #1650 `6672951193`. No se ejecutó aquí posting de ajuste válido; branch de ajuste UI/guard ya probado desde lista. Sin cambio de producto/tests permanentes. |

Conteo vigente: **64/564 rutas completas, 500 parciales; HTML/Jinja 25/252 completas, 227 parciales**.

### Cierre posterior — Lista de vales de Caja Chica (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/bancos/templates/bancos/caja_chica_vale_lista.html` | `2d1fb7e9613650e157c3f8fa7e506b5c76af5d7b6d8c3e89877caad7e1fb5eaf` | Completo: ruta/list query, scope, estados draft/entregado/cancelado/liquidado, escape, CSRF y acciones se caracterizaron con Flask/SQLite/curl. Anónimo 302; no-role 200 vacío; viewer cacao no ve Secret; admin ve ambas compañías; parámetros adulterados no amplían scope. Formulario de borrador da 500 por `bancos.caja_chica_vale_editar` inexistente (#1647), issue confirmado y comentado (`6672991316`); estados terminales renderizan. Se creó y liquidó un vale con PettyCashExpense+GL reales; la lista muestra liquidado. Cancel sin token 400; viewer token válido 403; admin status cambia y se refleja. Contenido de concepto/destinatario autoescaped y estados traducidos. CTA Nuevo/Liquidar/Cancelar se muestra a viewer/no-role aunque endpoints dan 403; decisión de UI bajo #1711 (`6672991729`), sin bypass. Sin cambios de producto/tests permanentes. |

Conteo vigente: **65/564 rutas completas, 499 parciales; HTML/Jinja 26/252 completas, 226 parciales**.


### Cierre posterior — Lista de reposiciones de Caja Chica (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/bancos/templates/bancos/caja_chica_reposicion_lista.html` | `ad14d8029a61b91a505457c01e48baa0af16e68b2b05ddaef29bc71ed255467a` | Completo: los cinco estados y todas las ramas visibles se mapearon a endpoint y caller; curl/SQLite con no-role/viewer/admin y dos compañías. Draft/solicitado/aprobado dan 500 por `url_for` a endpoints editar/anular inexistentes (#1647/#1092, comentario `6673117371`); reembolsado/cancelado renderizan 200. Scope oculta compañía ajena; CSRF ausente 400; viewer sin edit 403; admin draft→solicitado persiste. solicitado→aprobado da redirect pero estado sigue solicitado por guard Cloud al mutar `approved_by`, candidato append-only #1706 y no bypass; comentado también #1095 (`6673118375`) y root #1706 (`6673118916`). Status raw #1885 (`6673117694`), ID de cuenta bancaria como texto libre #1946 (`6673117993`), discrepancias UI/URL bajo #1711 (`6673119478`). No se completó Nota de Débito de reposición; las ramas que la habilitan no renderizan por los BuildErrors, así que la limitación queda explícita. Sin cambios productivos/tests permanentes. |

Conteo vigente: **66/564 rutas completas, 498 parciales; HTML/Jinja 27/252 completas, 225 parciales**.

### Cierre posterior — Configuración de control presupuestario (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/admin/templates/admin/budget_control_config.html` | `8edb0637693f1798c9b954227fced4526048a02533c6583ccf6fa465914a809a` | Completo: cotejado con ruta `/settings/budget-control`, servicio consumidor de compras, configuración y ramas de alerta/tabla. GET autenticado real vía curl en Flask/SQLite efímero: 200, HTML contiene encabezado, selector y CSRF. Probe HTTP con `.venv`: admin permitido, CSRF faltante 400, acción inválida no persiste, acción `block` sí persiste; el aviso condicional `do_nothing` ya fue renderizado y confirmado. Company inexistente `ghost` permite guardar claves CacaoConfig huérfanas, pero no aparece en Entity ni en tabla y no se demostró efecto sobre compañía válida; registrado como observación sin issue separado. `cfg.action` expone enum sin localización (#1963, evidencia extendida en comentario `6673409708`). El selector cambia a GET y envía el token en query string, observado como parte del contrato actual. No incluye Alpine/JS propio. Pruebas temporales retiradas; sin cambios productivos. |

Conteo vigente: **67/564 rutas completas, 497 parciales; HTML/Jinja 28/252 completas, 224 parciales**.

### Cierre posterior — Cuentas predeterminadas (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/admin/templates/admin/default_accounts.html` | `6a1cf273493efbebcdce89b6d9e9e2290e122b0c7820c87b37240778152117c4` | Completo: ruta y servicio `upsert_company_default_accounts()`/`validate_default_account_assignment()` cotejados; `curl` admin GET 200; anónimo 302, usuario sin admin 403. Smart Select API rechaza compañía ajena al usuario (403) y entrega la cuenta propia al admin (200). Chromium/Playwright sobre la plantilla: búsqueda/selección actualiza input hidden, envío real persiste el ID, sin errores JS. POST sin CSRF 400; referencia cross-company y tipo incompatible se rechazan preservando configuración; delete con CSRF retira la fila. Defecto de presentación reproducido: con solo `default_cash` asignada, el resumen «Cuentas configuradas» muestra `26` por usar `definitions | length`; nuevo #1993 (`needs-work`), comentario QA `6673676673`, candidato root #1711 comentado `6673524321`. Pruebas temporales retiradas; sin cambios productivos. |

Conteo vigente: **68/564 rutas completas, 496 parciales; HTML/Jinja 29/252 completas, 223 parciales**.

### Cierre posterior — Configuración de correo electrónico (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/admin/templates/admin/email_settings.html` | `dfa81a3c6166856518c89461698fa52cccd2cf7e50de679519c2709596d6ed82` | Completo: curl autenticado del GET Flask/SQLite 200; contraseña almacenada nunca se prellena ni aparece en HTML. Anónimo 302, usuario sin admin 403, modo Desktop 403; CSRF faltante 400. Save con contraseña vacía conserva secreto; TLS y notificaciones guardan on/off según checkbox. `test_email` guarda SMTP por acción separada: puerto inválido previamente guardado falla antes de conectar y muestra error; destinatario omitido se rechaza; un transporte SMTP falso loopback aceptó EHLO/MAIL/RCPT/DATA y el UI reportó éxito, sin envío externo. El guardado sí acepta `smtp_port=nope` y `smtp_from_email=not-an-email`, confirmado en #1994 (`needs-work`, raíz candidata #1717, comentario `6673831805`); defecto abierto no impide documentar todas las ramas. Sonda temporal retirada, sin cambios productivos. |

Conteo vigente: **69/564 rutas completas, 495 parciales; HTML/Jinja 30/252 completas, 222 parciales**.

### Cierre posterior — Registro de correo (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/admin/templates/admin/email_log.html` | `2593a1bb42082e669e25ba784c0f3a26392ef42cfb00e828f1d2f827579b0ed7` | Completo: GET Cloud real 200; anónimo 302, usuario sin admin 403, Desktop 403; CSRF faltante 400. Búsqueda/status, autoescape de destinatario/asunto/error, estado vacío/desconocido, botones por estado y paginación se verificaron. 27 filas filtradas en dos páginas; prev/next preservan `search=needle&status=failed`; `page=3`, `0`, `-1` responden 404 y `page=oops` cae en página 1; `curl` de ambas páginas devuelve 200. El POST también reintenta filas `sent` aunque la UI lo oculte (#1018/#1360). Con transporte fake y barrera se confirmaron dos envíos concurrentes, resultado variable (`PendingRollbackError` en una sesión) y contador perdido (`attempts` queda 2 tras dos retries concurrentes desde 1); el fallo de commit posterior al envío deja fila `failed` reintentable y el siguiente retry manda duplicado (fila `sent`, attempts 3). Evidencia en #1693 (`6673993917`, `6674011735`), relacionada con #1710; sin SMTP externo. Hallazgos permanecen abiertos; probes temporales retirados. |

Conteo vigente: **70/564 rutas completas, 494 parciales; HTML/Jinja 31/252 completas, 221 parciales**.

### Cierre posterior — Idioma predeterminado del sistema (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/admin/templates/admin/system_language.html` | `5514847042bd86ea7b100ed02a06cc21e518e6dc438a1c481dd49c8ba6955904` | Completo: Flask/SQLite real. Anónimo GET 302; usuario sin administración 403; administrador GET 200. CSRF ausente 400. Código inválido `fr` con CSRF devuelve 200 con error y no muta `CacaoConfig`; `en` válido redirige, persiste `SETUP_LANGUAGE=en` y el GET siguiente renderiza cadenas inglesas vía Babel. `_get_locale()` prioriza `User.language` y usa el idioma global como fallback, acorde al texto del formulario. Defecto #1918: `base.html` conserva `<html lang="es">` aunque el cuerpo se renderice en inglés; comentario `6674071940`. `Language default` es una traducción incorrecta para “Idioma predeterminado” en el catálogo inglés; candidato #1711, comentado (`6674197997`). Sonda temporal retirada, sin cambios productivos. |

Conteo vigente: **71/564 rutas completas, 493 parciales; HTML/Jinja 32/252 completas, 220 parciales**.

### Cierre posterior — Lista de roles (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/admin/templates/admin/roles.html` | `e9aa2c3b53bb9c3a434e947c86f223c57be1c7345ebbcd1ee8940ef1129b6d02` | Completo: curl/Flask/SQLite; anon 302, no-admin 403, admin 200 tanto Cloud como Desktop. Autoescape probado con `name`/`note` HTML malicioso; lista vacía responde 200. Los links de edición y permisos resuelven a GET 200 y un role_id inexistente redirige. No hay POST en este template; destinos están protegidos por `_require_system_admin`. #1767 continúa abierto para invariantas en los flujos de edición/gestión y no impide cerrar la cobertura de esta lista. Sonda temporal retirada. |

Conteo vigente: **72/564 rutas completas, 492 parciales; HTML/Jinja 33/252 completas, 219 parciales**.

### Cierre posterior — Grupos de terceros (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/admin/templates/admin/party_groups.html` | `8a0d95a90f9865f6f24cd3185c782edeed4860c8c7d8975dba63992470567644` | Completo: `curl` Flask/SQLite con anon 302, usuario sin admin 403, admin 200; GET real, autoescape y CSRF. Create/edit con tokens válidos permiten valores de `group_type` fuera de `customer`/`supplier` y los persisten; la vista presenta tipo desconocido como “Proveedor”. #1358 reproduce y cubre ambas escrituras; evidencia extra de duplicado/conflicto único devuelve 200 con mensaje y rollback sin alterar registro original, comment `6674602732`. Toggle CSRF ausente 400; GET en endpoint POST-only 405; POST válido cambia estado. La operación es global (PartyGroup carece de company scope). #1724 sigue `needs-review`: cambiar tipo con Parties asignados necesita decisión de tratamiento, independiente del cierre de cobertura. Sonda temporal pasó 1/1 y fue retirada. |

Conteo vigente: **73/564 rutas completas, 491 parciales; HTML/Jinja 34/252 completas, 218 parciales**.

### Cierre posterior — Configuración de abastecimiento (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/admin/templates/admin/purchase_sourcing_config.html` | `c7964d64473e1384acd27342b4189e9123d825d083cec89389b787dfceb06c12` | Completo: curl contra Flask/SQLite autenticado. Anónimo 302, usuario sin admin 403 y administrador GET 200; CSRF ausente 400. Revalidación actual con token: mínimo 3 + checkbox guarda `3/1`; 0 y `abc` no mutan estado existente; checkbox ausente guarda false con mínimo 1. `abc` sigue generando flash crudo (`invalid literal for int() with base 10`), #1996 `needs-work`, corroborado en comentario `667607...`. #1367 trata autorización de excepción, no el parser. Ruta disponible en Desktop por inspección, probe HTTP Cloud. El cierre describe cobertura examinada y conserva defecto conocido; test/sonda retirados. Agrupación candidata #1717 y #1711. |

Conteo vigente: **74/564 rutas completas, 490 parciales; HTML/Jinja 35/252 completas, 217 parciales**.


### Cierre posterior — Detalle de confirmación de saldos (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/templates/admin/balance_confirmation_detail.html` | `6cac023b7d89c18fd9358f39339dfb8d17aa646fdf20f9a81afb4fa0df3ecaf8` | Completo: revisión de estados, datos Jinja, snapshot, totales por moneda, destinatarios, historial, enlaces y formularios de acción; el contenido de terceros se escapa por Jinja. `curl` HTTP real con Flask/SQLite: anónimo 302, usuario autenticado sin permiso de compañía 403, admin 200. Snapshot con JSON inválido causa 500; snapshot JSON alterado con hash deliberadamente incorrecto responde 200 y muestra el documento alterado porque el GET no valida la huella. Abierto #1997, comentado en #1706 como asociación candidata (`6674807740`); la sonda temporal pasó 1/1 y se retiró. El defecto queda abierto, la cobertura del archivo se cierra. |

Conteo vigente: **75/564 rutas completas, 489 parciales; HTML/Jinja 36/252 completas, 216 parciales**.


### Cierre posterior — Alta de confirmación de saldos (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/templates/admin/balance_confirmation_new.html` | `4ed1b33c19ea781014b18b1ad167083628286f5d78abcc77a27cabac9d83b36b` | Completo: revisados datos Jinja/Alpine, correo sugerido, formulario, CSRF, selector de compañías y destino de alta. `curl` Flask/SQLite: anónimo 302, admin 200; usuario autenticado sin RBAC obtiene 200 y HTML con nombre/correo de tercero global sin relación activa `CompanyParty`, fuga de PII (#1998, `needs-work`, root candidato #1649, comentario `6674869316`). #1111 sigue abierto: los dos handlers usan `String.lower()` y Node reproduce `TypeError`; comentario de actualización `6674875510`. El GET lista compañías autorizadas, pero no bloquea el render del tercero/contactos. Probe temporal 1 passed y fue retirado. Cobertura cerrada; fallos quedan abiertos. |

Conteo vigente: **76/564 rutas completas, 488 parciales; HTML/Jinja 37/252 completas, 215 parciales**.


### Cierre posterior — Menú global de administración (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/admin/templates/admin.html` | `ce79b70bd055e88855cd81d2eca1590fd70e5d482950e335ceccda2df131cb22` | Completo: render HTTP real de `/admin` con curl/Flask y módulo admin habilitado. Anónimo 302; admin, reader y usuario sin RBAC 200; el menú presentó 26 badges `ok` al admin y 26 `no_access` a los otros usuarios. Las rutas visibles se resolvieron en `url_for`; `module_badge(required=link.required_permission)` no arroja TypeError. El endpoint de menú no expone datos de configuración y muestra explícitamente estado de acceso; los destinos mantienen sus guards particulares. Evidencia añadida a #1912 (`6674948877`); issue queda abierto hasta decisión de su responsable. La sonda temporal pasó 1/1 y se retiró. |

Conteo vigente: **77/564 rutas completas, 487 parciales; HTML/Jinja 38/252 completas, 214 parciales**.


### Cierre posterior — Formulario de roles (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/admin/templates/admin/rol_form.html` | `6604215ced4d1ef3b3051ec54ddf59e50bf72d534679fdc91f8bcc7a41df2a2e` | Completo: alta/edición trazadas a `RoleForm` y `_require_system_admin`; curl HTTP Flask/SQLite: anónimo 302, usuario no RBAC 403, admin 200 en ambas rutas. Campo de nombre inválido conserva y muestra error WTForms; nombre duplicado se re-renderiza con error. En locale EN los encabezados se traducen, pero botones permanecen “Guardar rol”/“Actualizar rol” y duplicado muestra “El nombre del rol ya está en uso.” (#1999, `needs-work`, candidato #1711, comentario `6675009059`). `hidden_tag()` presente; la app fixture deshabilita global CSRF, por lo que no se afirma validación HTTP del token en esta sonda. Test focal temporal 1 passed y retirado. |

Conteo vigente: **78/564 rutas completas, 486 parciales; HTML/Jinja 39/252 completas, 213 parciales**.


### Cierre posterior — Permisos de roles por módulo (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/admin/templates/admin/rol_permisos.html` | `65f52bb1a3a0764d87d43ad19be288f98c3f10751a82d5c52189b76508d42340` | Completo: curl real Flask/SQLite: anónimo 302, usuario no RBAC 403, admin 200; CSRF faltante y `rank=4` devuelven 400 sin mutación; POST válido persiste acciones/rango, checkbox omitida queda False y elimina filas de módulos omitidos. Desktop oculta rango y conserva valor previo. En locale EN, etiquetas de 15 acciones siguen en español (#1907 confirmado/comentado `6675142507`). QA concurrente PostgreSQL 16.15 sobre esquema temporal aislado reprodujo dos reemplazos intercalados que dejan filas duplicadas rol/módulo; la unión OR de `Permisos._tiene_permiso()` combina privilegios que las solicitudes no enviaron juntas. Nuevo #2000, root candidato #1653 (`6675142264`); reproducción de concurrencia fue a nivel PostgreSQL con las mismas operaciones, no por HTTP. Probe pytest temporal 1 passed y retirado; schema PG temporal eliminado. |

Conteo al corte anterior: **81/564 rutas completas, 483 parciales; HTML/Jinja 42/252 completas, 210 parciales**.


### Cierre posterior — Inicio de documentación (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `docs/theme_override_home/home.html` | `29380db4bb7aa2b0d47d87e3ad4be50a2180a133a9ae90f9e59b77377ff56dfe` | Completo: revisados bloques Jinja, enlaces y assets. Renderizado con Jinja usando layout base de bloques mínimo; servidor HTTP local con `curl` respondió 200 y devolvió el HTML generado. Logo existe; cinco destinos externos comprobados. El CTA de instalación devuelve 404; tarjeta `CLI` enlaza a Codecov y describe cobertura con typo («covertura»). Registrado en #2001; build completo MkDocs/Material no verificado porque MkDocs no está instalado. QA independiente confirmó el 404 y el mismatch. Sin cambios de producto. |

Conteo al corte anterior: **81/564 rutas completas, 483 parciales; HTML/Jinja 42/252 completas, 210 parciales**.


### Cierre posterior — Override principal de documentación (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `docs/theme_override_home/main.html` | `194e797e37f7d26f5ba14f215d5d4df2413afe67f2db11a00dbd3dc5e3c06827` | Completo: extensión de `base.html`, overrides de `libs`, `announce`, `footer` y `social` comprobados con Jinja y layout/partial padre simulados. Footer/copyright/social renderizan; libs/announce vacíos reemplazan los bloques padre. Servidor local y curl devolvieron 200 y el HTML recibido coincide con el render. No hay lógica de acceso, rutas de app ni inputs del usuario. MkDocs/Material no está instalado; build completo del sitio no validado. Sin hallazgos separados de #2001 en `home.html`, sin cambios productivos. |

Conteo al corte anterior: **81/564 rutas completas, 483 parciales; HTML/Jinja 42/252 completas, 210 parciales**.


### Cierre posterior — Verificación OTP (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/auth/templates/verify_otp.html` | `50d560fbeb619dd6ff5cb2576685b7210a1f694a3ff3e0d1b90371fa1dc17df6` | Completo: form POST incluye CSRF; `OtpVerificationForm` exige seis caracteres, el control cliente restringe a dígitos y Jinja autoescapa título, errores y flashes. Caller `verify_otp()` autentica sesión OTP, usuario activo y GET/POST; inválido/expirado muestra mensaje común y handler no confirma la mutación del contador (#1762, reproducción HTTP/SQLite ya registrada); éxito consume OTP, genera dispositivo/token, inicia sesión y confirma en una transacción. Hay límite de ruta 5/min. `<html lang>` se toma de `session.lang`, no del locale Babel observado en otras páginas (#1918/#1711). Comportamiento de render/ramas cotejado estáticamente contra form/helper y evidencia HTTP previa; no se repitió sonda. |

Conteo vigente: **82/564 rutas completas, 482 parciales; HTML/Jinja 43/252 completas, 209 parciales**.


### Cierre posterior — Matriz de aprobación (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/admin/templates/admin/approval_matrix.html` | `480c23e6a5a0f40dff6743cc05b2d3f2a153b676bfb534a42b3819e9e371ea9a` | Completo: los 224 renglones y el caller `config_approval_matrix()` quedaron cotejados. Flask/SQLite: anónimo 302, no-admin 403, admin GET 200; POST sin CSRF 400. Se cubrieron save_global/cuatro ojos, selección de compañía, empty state, alta y eliminación lógica, targeting cualquiera/rol/usuario y aislamiento de reglas de otra compañía. Los defectos caracterizados permanecen abiertos: regla inactiva se muestra activa (#2002); `max_amount=0` se presenta como sin límite y bordes no finitos fallan según backend, negativos persisten (#1746/#1650); `document_type` arbitrario se persiste y queda sin etiqueta (#1995, relacionado a #1717); botón de borrado es solo icono sin nombre accesible (#2004, candidato root #1711). Los casos de coerción fallida dan 500. La cobertura del archivo queda cerrada; issues no resueltos no se consideran fixes ni bloquean el registro de lo observado. |

Conteo al corte anterior: **83/564 rutas completas, 481 parciales; HTML/Jinja 44/252 completas, 208 parciales**.


### Cierre posterior — Catálogo de dimensiones analíticas (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/admin/templates/admin/dimension_values.html` | `ef4c1c6def0542416cf56aac0a1a5ed78a8c679692005dac742cb7c276edfa80` | Completo: template completo (110 líneas), forms de crear tipo/agregar valor, toggles por POST, tabla/empty state, autoescape, gettext y endpoints/campos cotejados con `lista_dimensiones()` y ambos handlers de toggle. Curl Flask real: anónimo 302, sin RBAC 403, admin 200; CRUD y los errores están caracterizados. Se registran: checkbox `is_active` ausente crea tipo activo (#2003/#1962); valores permiten referencias de tipo/compañía inexistentes si SQLite no fuerza FK y fallan con enforcement habilitado (#1717); catálogo permite valores duplicados/global-local (#1340 `needs-review`); tipo inactivo sigue aceptando alta de valores (#1339) y tipo/valor inactivo puede seguir visible/aceptado por el admin (#1716 `needs-review`). Query tools `dimensions.list`/`dimension_values.search` sí consumen el catálogo y su aislamiento activo/global/compañía y paginación se verificaron con sonda SQLite/service-principal. No se encontró writer/reader de `GLEntryDimension` fuera del modelo; completar la conexión al GL sigue en #1337/#1359/#1368 agrupados bajo #1658. Sondas retiradas; sin cambios productivos. |

Conteo al corte anterior: **84/564 rutas completas, 480 parciales; HTML/Jinja 45/252 completas, 207 parciales**.


### Cierre posterior — Configuración de validación externa (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/admin/templates/admin/external_document_validation.html` | `8fde25377d7880477f439ae9bb957a7d9d9e43029663cd3106c1e1885601597f` | Completo: form, campos, traducciones, autoescape, destino y contexto cotejados con `external_document_validation_settings()` y `save_external_validation_settings()`. HTTP/Flask: anónimo 302, usuario sin RBAC 403, admin GET 200; el form omite token CSRF y POST sin token devuelve 400 (#1950). `type=url` solo valida en cliente; backend guarda valor arbitrario y el servicio lo concatena a URL/QR, sin fetch/solicitud saliente comprobada, por lo que no se afirma SSRF. Existe segundo endpoint `/admin/print-templates/settings` con el mismo helper y autorización diferente; su template no muestra el formulario por mismatch de bloque (#1928), además de guard #1343. La duplicidad y el alcance canónico siguen bajo decisión `needs-review` en #1658. Defectos y límites quedan caracterizados; cobertura cerrada, sin cambio de producto. |

Conteo al corte anterior: **85/564 rutas completas, 479 parciales; HTML/Jinja 46/252 completas, 206 parciales**.


### Cierre posterior — Método de valuación de inventario (2026-11-06)

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/admin/templates/admin/inventory_valuation.html` | `22dd2989d47f854154321329ad213ff1cec888b8e410aa6eef89166fe8682082` | Completo: formularios GET/POST, CSRF, select de compañías, opciones FIFO/promedio, estado bloqueado, empty state, tabla y links cotejados con `configuracion_valuacion_inventario()`/`update_company_valuation_method()`. Sonda Flask/SQLite anterior confirma auth, GET 200, POST sin CSRF 400, método válido, enum y compañía inválidos sin mutación, compañía seleccionada bajo system-admin global, y guard secuencial por `StockLedgerEntry`/`StockValuationLayer`; probe de valoración confirma costos diferentes FIFO vs promedio. #1866 conserva GET 500 con código de compañía inválido. #1881 confirma estáticamente ausencia de lock/CAS compartido con primer posting; dos sesiones PostgreSQL no se reprodujeron, estrategia de serialización sigue `needs-review` y root candidato #1653. El riesgo no se declara reproducido ni resuelto. Sin cambios de producto. Revisión independiente coincidió en cobertura y límites. |

Conteo vigente: **86/564 rutas completas, 478 parciales; HTML/Jinja 47/252 completas, 205 parciales**.

### Reglas de mapeo entre libros — cobertura cerrada — 2026-11-06

| Ruta | SHA-256 | Estado | Evidencia detallada |
|---|---|---|---|
| `cacao_accounting/admin/templates/admin/ledger_mapping_rules.html` | `916cdaf6a58caf0ff7baaebb17626b0bcbc469b27fc6ef52a55c022f357118ae` | Completa | Sección de cierre posterior a continuación. |


`cacao_accounting/admin/templates/admin/ledger_mapping_rules.html` (SHA-256 `916cdaf6a58caf0ff7baaebb17626b0bcbc469b27fc6ef52a55c022f357118ae`) fue inspeccionada junto a sus handlers, el modelo `LedgerMappingRule`, `ledger_mapping_service.py` y el punto de integración de posting. Curl con PostgreSQL real: anon 302, usuario sin system-admin 403, admin vacío 200; POST sin token 400; referencia inválida no persiste; alta válida y desactivación conservan una fila histórica y los estados se reflejan en el GET. La UI muestra `True/False` e IDs técnicos. Se confirmó en una barrera PostgreSQL que dos altas concurrentes para el mismo origen/destino/cuenta origen pueden crear dos destinos activos distintos; al aplicar reglas, el servicio detecta ambigüedad y bloquea el posting. Se comentó #1653 como root candidato del patrón read-then-write, sin afirmar que resuelva política/implementación. #1775 ya documenta reglas activas huérfanas al cambiar entidad del libro. Sonda aislada retirada; sin cambios de producto ni tests permanentes. SHA cotejado.

Conteo reconciliado: **87/564 rutas completas, 477 parciales; HTML/Jinja 48/252 completas y 204 parciales**.

### Bandeja de aprobaciones pendientes — cobertura cerrada — 2026-11-06

| Ruta | SHA-256 | Estado | Evidencia detallada |
|---|---|---|---|
| `cacao_accounting/admin/templates/admin/pending_approvals.html` | `d7e9bec54e894894f4d1028af7cd4120571ae0f46f0c73a9712ac944447d00d6` | Completa | Sección de cierre posterior a continuación. |


`cacao_accounting/admin/templates/admin/pending_approvals.html` (SHA-256 `d7e9bec54e894894f4d1028af7cd4120571ae0f46f0c73a9712ac944447d00d6`) se revisó junto a `/me/pending-approvals`, `_pending_approval_info`, el motor estándar, las revisiones independientes y la ruta de detalle de factura. Flask/SQLite HTTP: anónimo 302; aprobador 200 con factura y CSRF; detalle 200 para quien puede aprobar y 403 para solicitante/no autorizado; el solicitante no ve la fila ni consigue aprobarla por POST directo. Un revisor con scope solo en CACAO ve su solicitud y no otra de OTHER. Con factura realista y línea de inventario, el POST autorizado de aprobación transitó a `Approved` y `docstatus=1`; el rechazo de `config_change` transitó a `Rejected`. El estado vacío fue visible para usuario inactivo.

Defecto reproducido #2008: crear una solicitud mientras el motor está activo y deshabilitarlo después deja la fila visible, pero `ApprovalEngine.reject()` retorna sin transición; el POST redirige normalmente, muestra éxito y el estado permanece `Pending Approval`. Hijo bajo #1708, distinto de acción inválida #1017. Comentarios publicados en #1708; no se cambió producto ni tests permanentes. Sondas SQLite y datos se descartaron. SHA cotejado.

Conteo reconciliado: **88/564 rutas completas, 476 parciales; HTML/Jinja 49/252 completas y 203 parciales**.

### Listas de precios — cobertura cerrada — 2026-11-06

| Ruta | SHA-256 | Estado | Evidencia detallada |
|---|---|---|---|
| `cacao_accounting/admin/templates/admin/price_lists.html` | `d4700b7893513226fe68f795e8a27dedf3c05f0b5c69e4ebb9e1900ac6d3a4f6` | Completa | Sección de cierre posterior a continuación. |


`cacao_accounting/admin/templates/admin/price_lists.html` (SHA-256 `d4700b7893513226fe68f795e8a27dedf3c05f0b5c69e4ebb9e1900ac6d3a4f6`) se inspeccionó junto a su ruta, permisos, modelo y consumidor de resolución de precio O2C. HTTP Flask/SQLite: anónimo 302, sin rol 403; sales manager con scope CACAO ve solo su propia lista y system admin ve ambas compañías. Se probó que revocar `RolesUser.active` no retira el acceso a lista ni la creación (#2011). POST sin CSRF 400 (#1743); un token CSRF válido permitió completar las sondas del handler. Lista predeterminada de venta apaga solo otro default de la misma compañía y crea el ItemPrice inicial para cada artículo de venta activo con `standard_rate`; el default de OTHER permaneció intacto.

Defectos reproducidos: checkbox `is_selling`/`is_active` omitido persiste como True (#2009, relacionado con #2003); company o currency inexistente provocan HTTP 500 por FK al hacer flush (#2010). Defectos de presentación: booleanos raw, sin columna/indicador `is_active`, sin estado vacío ni edición/desactivación de lista; #1711 comentada y #1658 se mantiene como candidato sujeto a confirmar contrato. La lógica de pertenencia de compañía fue ejercitada; la revocación del rol sigue bajo #1716 candidato, con #1649 secundario. Sin cambios productivos ni pruebas permanentes. SHA cotejado.

Conteo reconciliado: **89/564 rutas completas, 475 parciales; HTML/Jinja 50/252 completas y 202 parciales**.

### Administración de módulos — cobertura HTTP cerrada — 2026-11-06

| Ruta | SHA-256 | Estado de evidencia | Referencia disponible |
|---|---|---|---|
| `cacao_accounting/admin/templates/admin/modulos.html` | `6f89cea4af06bbd63e65f57ad91a3742590761b052d85d7bebd5a4086630d179` | Completo: template cotejado con `lista_modulos()`, sincronización y guard de módulos; HTTP anónimo 302, lector 403, admin 200; POST sin CSRF 400; se probó toggle de `sales` con persistencia y efecto inmediato sobre `/sales/sales-invoice/list` (200→404→200), y se confirmó que no puede deshabilitarse `admin`. | `type` “Estándar/Plugin” sin gettext sigue abierto bajo #1711; evidencia añadida en comentario `6677502634`. |

Conteo reconciliado: **90/564 rutas completas, 474 parciales; HTML/Jinja 51/252 completas y 201 parciales**.

### Seguridad de sesión — cobertura OTP y lockout cerrada — 2026-11-06

| Ruta | SHA-256 | Estado de evidencia | Referencia disponible |
|---|---|---|---|
| `cacao_accounting/admin/templates/admin/session_security.html` | `b4a9ea19b4981e9db7c9281c59722384d8610a414ee1a9c964b90daa9e4227c8` | Completo: anon 302, no-admin 403, Cloud admin 200 y Desktop admin 403; CSRF y ramas toggle/revoke/unlock verificadas. OTP real con transport fake crea cookie/dispositivo; dispositivo vigente evita OTP, expirado o revocado lo exige de nuevo. Lockout activo/expirado y locale EN revisados. | Sin SMTP el toggle sigue bloqueado; accesibilidad icon-only bajo #1711. Error de redondeo a 2 min con exactamente 60 s, #2013 candidato #1710 (`6677675624`). |

Conteo reconciliado: **91/564 rutas completas, 473 parciales; HTML/Jinja 52/252 completas y 200 parciales**.



### Cierre posterior — Lista de pronósticos de caja (2026-11-06)

| Ruta | SHA-256 | Estado de evidencia | Referencia disponible |
|---|---|---|---|
| `cacao_accounting/bancos/templates/bancos/cash_forecast_lista.html` | `fba269c597399eed3cd1f44c47134ff84add4a045030efb9b1232c00e3558829` | Completo: anon 302, viewer autorizado 200 limitado a CACAO, company ajena 403 sin datos ajenos. La fila Draft muestra botón eliminar al viewer; POST CSRF válido da 403. CSRF faltante 400. Admin elimina Draft y mantiene Approved ante intento de borrar (redirect + fila existente). Periodicidad inválida `annual` se presenta como Mensual en la lista, aunque el servicio la procesa como semanal; evidencia a #1083 (`6678134452`). Affordance inutilizable bajo RBAC comentada como candidata en #1711 (`6678166272`). |

Conteo reconciliado: **92/564 rutas completas, 472 parciales; HTML/Jinja 53/252 completas y 199 parciales**.


### `cacao_accounting/bancos/templates/bancos/cash_forecast_entradas.html` — cobertura HTTP cerrada — 2026-11-06

| Ruta | SHA-256 | Estado de evidencia | Referencia disponible |
|---|---|---|---|
| `cacao_accounting/bancos/templates/bancos/cash_forecast_entradas.html` | `e592a331937129ce1d2bb679c27b875d3076a236288002626b543a65aa90d7d4` | Completo: Flask/SQLite anon 302, usuario sin RBAC 403, viewer cash de compañía autorizada GET 200 con entrada. Viewer ve botones Añadir/Editar/Eliminar para Draft; POST con CSRF válido da 403 en las tres acciones, sin mutación (#1711 comentario `6678270019`). Admin añade 100 USD sin tasa FX y persiste; matrix de 53 períodos omite la línea no convertible (#1233 `6678250421`, decisión rechazo vs incompleta `needs-review`). Admin edita una fila Draft, la elimina y un intento de editar fila Approved no cambia sus datos. CSRF está presente. El select de nueva línea compara con `selected_forecast.currency`, atributo inexistente, por lo que no genera `selected`; la asignación Jinja `currency=selected_company` no tiene consumidores. Default esperado es decisión pendiente, comentada bajo #1658 (`6678306503`). |

Conteo reconciliado: **93/564 rutas completas, 471 parciales; HTML/Jinja 54/252 completas y 198 parciales**.


### `cacao_accounting/bancos/templates/bancos/cash_forecast_detalle.html` — cobertura HTTP y estados cerrada — 2026-11-06

| Ruta | SHA-256 | Estado de evidencia | Referencia disponible |
|---|---|---|---|
| `cacao_accounting/bancos/templates/bancos/cash_forecast_detalle.html` | `03410ddca3cf838da62501bd0a8f67743396b2c026a2c7990c28026064ec4cc8` | Completo: Flask/SQLite anónimo GET 302, sin RBAC 403, viewer cash autorizado y de su compañía 200, compañía ajena 403. La moneda de matriz usa `document_currency_code(forecast)` y el render mensual de NIO muestra NIO en importes. Admin recorre Draft→Approved→Closed→Archived; transiciones fuera de estado conservan Approved. Viewer ve botones approve/close/archive por estado, pero los POST con CSRF válido dan 403 sin mutación; affordance visible comentada bajo #1711 (`6678473563`). Formularios mutativos incluyen CSRF. Mensual se renderiza `January 2026` en locale base español (`Enero 2026` ausente), por `strftime('%B %Y')` expuesto como `row.period`; candidato i18n bajo #1711 (`6678473563`). Fallbacks de status desconocido muestran valor raw, candidato #1711. Defectos de cálculo que se reflejan en matriz permanecen en #1084, #1233 y #1499; están en servicios/criterios, no se duplican aquí. |

Conteo reconciliado: **94/564 rutas completas, 470 parciales; HTML/Jinja 55/252 completas y 197 parciales**.


### `cacao_accounting/bancos/templates/bancos/cash_forecast_nuevo.html` — cobertura HTTP cerrada — 2026-11-06

| Ruta | SHA-256 | Estado de evidencia | Referencia disponible |
|---|---|---|---|
| `cacao_accounting/bancos/templates/bancos/cash_forecast_nuevo.html` | `b3e14333f1b9043967babd935bffcff86229e4f710363205766c5b664ec48294` | Completo: Flask/SQLite anónimo GET 302, viewer cash sin `crear` GET 403, admin GET 200 con CSRF y periodicidad mensual seleccionada. Alta mensual válida crea Draft (302); duplicado de versión/año se rechaza sin segunda fila. `annual` también se acepta y persiste pese a que el selector solo ofrece weekly/monthly; servicio genera 53 semanas, mientras lista/detalle lo muestran mensual (#1083/#1258 corregidos en GitHub con la discrepancia visual exacta). POST sin CSRF 400. Año fiscal ajeno a compañía seleccionada se rechaza y no persiste. Al faltar periodicidad se pierden versión, descripción y FY en el re-render (#1951 comentario `6678557317`). El selector ofrece varias compañías pero carga FY solo para la inicial y no tiene evento de actualización; cambio a otra compañía con FY anterior se rechaza (#2016 needs-work, candidato #1711, relacionado #1632; datos del formulario se pierden también por #1951). Criterio de dependencias: actualizar FY al cambiar compañía; no se tomó la decisión por el producto. |

Conteo reconciliado: **95/564 rutas completas, 469 parciales; HTML/Jinja 56/252 completas y 196 parciales**.


### `cacao_accounting/admin/templates/admin/item_prices.html` — cobertura cerrada — 2026-11-06

| Ruta | SHA-256 | Estado | Evidencia |
|---|---|---|---|
| `cacao_accounting/admin/templates/admin/item_prices.html` | `3414cdb58c6b9cdd6f94880f4b61688049d651ebc814d237a9b4c80e314353c8` | Completa | Detalle de revisión documentado a continuación. |

La plantilla, `precios_item()`, `actualizar_precio_item()`, `_require_price_list_editor()`, `_can_manage_price_list()`, `PriceList`/`ItemPrice`, `resolve_item_price_record()` y el consumidor O2C `resolve_sales_catalog_price()` quedaron cotejados. QA independiente confirmó el alcance del formulario y la ausencia de hallazgos nuevos. HTTP Flask/SQLite previo: anónimo 302, usuario sin rol 403 y administrador 200; el GET no incluye tokens CSRF en sus tres formularios y el POST sin token da 400 (#1743/#1711). Con token protegido obtenido en otra pantalla se verificaron alta válida, rechazo de NaN, persistencia de precio negativo y rango invertido, excepción HTTP 500 para `price=abc` (#1742/#1650), y edición de tarifas de listas inactivas que el GET oculta. El POST de edición también sobrescribe `min_qty` y vigencias desde campos ocultos; si se omiten, elimina los criterios anteriores. Los campos ocultos no ofrecen edición explícita de esos criterios.

El resolver filtra por artículo/lista, fecha inclusiva (`valid_from <= posting_date <= valid_upto`), mínimo de cantidad (`min_qty <= qty`) y UOM exacta o genérica; ordena por mayor mínimo, vigencia más reciente y coincidencia de UOM. La lista de ventas se elige por asignación activa del cliente cuando es activa, de venta y global/de la compañía; si no, usa la default activa de venta de compañía/global. La plantilla no valida estas reglas de negocio, solo administra sus registros. Defectos y decisiones pendientes permanecen vinculados a #1742/#1650/#1743/#1711/#1764; la tabla expone ID técnico de lista, carece de selector humano de lista/artículo/UOM y de estado vacío. La cobertura del archivo queda cerrada; los defectos continúan abiertos. Probe temporal ya retirado; sin cambios de producto ni pruebas permanentes. SHA `3414cdb58c6b9cdd6f94880f4b61688049d651ebc814d237a9b4c80e314353c8`.

Conteo reconciliado: **96/564 rutas completas, 468 parciales; HTML/Jinja 57/252 completas y 195 parciales**.


### `cacao_accounting/admin/templates/admin/purchase_reconciliation_config.html` — cobertura cerrada — 2026-11-06

| Ruta | SHA-256 | Estado | Evidencia |
|---|---|---|---|
| `cacao_accounting/admin/templates/admin/purchase_reconciliation_config.html` | `d62911adcdf7a7a51b16fbe012feb5c88debd734092bda200f862d627fc7be8e` | Completa | Detalle de revisión documentado a continuación. |

La plantilla quedó cotejada con `config_conciliacion_compras()`, `update_matching_config()`, `require_review()`, `PurchaseMatchingConfig`, `CompanyDefaultAccount` y los consumidores de compras/anticipos. HTTP Flask/SQLite con CSRF: anónimo 302, usuario sin system-admin 403 y administrador 200; POST sin token 400. La UI presenta un formulario vacío titulado “Nueva configuración” incluso para compañías configuradas: al guardar se sobrescriben campos con defaults estáticos (#2012, comentario actual #1711); no hidrata el flag de anticipos. El control `apply_advances_automatically` se confirma aparte del cambio de matching, que en Cloud puede quedar Pending Approval (#1567, needs-review). El selector muestra enums, pero el servicio no valida enums/rangos: un valor de matching desconocido cae al flujo 3-way y tolerancia desconocida se interpreta como absoluta (#1362, needs-review, corroborado en comentario `6678695139`). `_decimal_form()` puede propagar InvalidOperation no capturado para tolerancia malformada (#1742). Valores raw de porcentaje/absoluto permanecen visibles (#1711). Ningún hallazgo requiere issue duplicado. El archivo queda completo por cobertura; la política de aprobación y recuperación de valores históricos inválidos sigue pendiente de decisión. SHA `d62911adcdf7a7a51b16fbe012feb5c88debd734092bda200f862d627fc7be8e`.

Conteo reconciliado: **97/564 rutas completas, 467 parciales; HTML/Jinja 58/252 completas y 194 parciales**.


### `cacao_accounting/admin/templates/admin/sales_matching_config.html` — cobertura cerrada — 2026-11-06

| Ruta | SHA-256 | Estado | Evidencia |
|---|---|---|---|
| `cacao_accounting/admin/templates/admin/sales_matching_config.html` | `65b995a62f087508665b803c5b417882d24a88a0c33e15bb174403f754e51771` | Completa | Detalle de revisión documentado a continuación. |

La plantilla quedó cotejada con `config_conciliacion_ventas()`, `update_matching_config()`, el modelo `SalesMatchingConfig` y sus consumidores en `ventas/services.py`. HTTP Flask/SQLite previo con curl confirmó anónimo 302, usuario sin system-admin 403, administrador 200 con CSRF, POST sin token 400 y POST válido sobre una configuración existente 302; el form vacío reinicia 2-way/absolute/5/OV opcional/allow-diff a 3-way/percentage/0/OV requerido/no-diff (#2012). La ruta convierte tolerancia con `_decimal_form()` sin capturar `InvalidOperation` (#1742) y el servicio compartido acepta enums no reconocidos (#1362). Revisión del caller actual confirmó que `matching_type` se persiste pero ningún validador operativo de Ventas lo consulta; el formulario promete 3-way OV+Nota de Entrega+Factura y aun así no exige Nota de Entrega (#1813, comentario `6678716583`). El issue #1567 concierne solo el formulario de Compras, no se replica aquí. Defectos mapeados y sin duplicados; cobertura cerrada, sin cambio de producto ni pruebas permanentes. SHA `65b995a62f087508665b803c5b417882d24a88a0c33e15bb174403f754e51771`.

Conteo reconciliado: **98/564 rutas completas, 466 parciales; HTML/Jinja 59/252 completas y 193 parciales**.

### Cierre posterior — plantilla de validación pública QR — 2026-11-06

| `cacao_accounting/templates/public/validation_result.html` | `d611e5b76817f63cc36ab3b0c83a97f9ff634c9527c0c00bf634b1f7c2586a8c` | Completa por cobertura | Caller `/public/validate_doc/<token>`, `ValidationService`, `PublicValidationView`, modelo `PublicDocumentValidation` y tipos fuente cotejados. Flask/SQLite aislada + `curl`: token inexistente HTTP 404; token anónimo válido HTTP 200, render success; mismatch de hash HTTP 200, render invalid (#2019); docstatus cancelado HTTP 200 con estado `CANCELLED`; comprobante `journal_entry` reverted HTTP 200 con estado `REVERTED`. QR es público por contrato y depende del token, no RBAC. Strings traducibles cotejadas; estado enum aparece raw uppercase en inglés, comentado en #1711 (`6679120929`). Defecto de canonicalización reportado en #2019 (comentarios `6679111181`, `6679120687`). SHA cotejado; sin cambios productivos. |

Conteo reconciliado: **99/564 rutas completas, 465 parciales; HTML/Jinja 60/252 completas y 192 parciales**.

### Cierre posterior — `admin/tax_template_items.html` — 2026-11-06

| `cacao_accounting/admin/templates/admin/tax_template_items.html` | `7effa7e0c9c9d62fdc38e75fea35236ccb86049056a2b8fe0b84fed3ee039be9` | Completa por cobertura | Ruta `/settings/tax-templates/<template_id>/items`, handler, TaxTemplate/TaxTemplateItem/Tax, callers `calculate_taxes()`, `_tax_rules_from_template()`, purchase/sales context builders y posting service cotejados. Auth/CSRF y alta previamente probados; formulario no trae hidden CSRF y POST protegido responde 400 (#1743/#1950). Enum alterado se interpreta aditivo (#1745); secuencia malformada da 500, tax_id huérfano varía con enforcement FK (#1764/#1717). Tabla omite nombre e `is_inclusive`, muestra ULID/enums raw (#1911). SQLite aislada reprodujo efecto del impuesto inactive intermedio: legacy withholding 22.00; context builder/FiscalEngine cae a 20.00 en compra y venta; `_post_with_calculation_engine_payload()` produjo GLEntry: O2C AR 90 en vez de total esperado 88 y S2P AP 90 en vez de payable 88 (#2020, comentarios `6679181368`, `6679181599`, `6679263917`, `6679308579`; root candidato #1707 y adapter legacy #1686). Los imports/macros no aplican. SHA cotejado; no cambios productivos ni persistencia de DB temporal. |

Conteo reconciliado: **100/564 rutas completas, 464 parciales; HTML/Jinja 61/252 completas y 191 parciales**.

### Cierre posterior — `admin/tax_templates.html` — 2026-11-06

| `cacao_accounting/admin/templates/admin/tax_templates.html` | `602cd8aeba6fe8000a573c7a12ee56ae07b7321a20ccbe4bd286b2d4a3245d70` | Completa por cobertura | Ruta `/settings/tax-templates` y consumidores de creación/validación/cálculo cotejados. Auth/CSRF y POST previo: anónimo 302, admin 200, POST sin token 400; checkbox desmarcada se persiste activa (#1962); compañía/moneda inexistentes causan FK huérfana o 500 según enforcement (#1764/#1717); template_type manipulado se persiste y se muestra raw (#1911); tabla omite estado y moneda. Reproducción SQLite de aplicabilidad: Tax `applies_to=sales` en plantilla `buying` de compra pasa `_validate_purchase_tax_template()` y `purchase_invoice_draft_service._resolve_tax_total()`, suma 15 sobre 100; extensión directa a #1015 (`6679369078`). Tipo alias `purchase`: estándar lo rechaza, draft helper lo acepta, pero `purchase_invoice_draft_service.py` no tiene callers locales; evidencia agregada a #1658 (`6679383280`), no se abre bug separado para servicio desconectado. `tax_templates.html` permite solo `buying/selling`; defectos visuales/default quedan abiertos en #1911/#1962. SHA cotejado; sin cambios productivos. |

Conteo reconciliado: **101/564 rutas completas, 463 parciales; HTML/Jinja 62/252 completas y 190 parciales**.

### Cierre posterior — `admin/taxes.html` — 2026-11-06

| `cacao_accounting/admin/templates/admin/taxes.html` | `f0537f26ce266eac61fddff18bff7d7397895b9c5d11583748b67ed8eab14915` | Completa por cobertura | Handler de impuestos y consumidores Tax/TaxTemplate, cálculo, builders y posting cotejados. Auth/CSRF y POST previamente probados. Enum `tax_type=junk` se persiste y cae a percentage (#1685); applies_to inválido y Tax↔Template no se filtran (#1015). `rate=abc` 500 (#1742), NaN rechazado; account_id FK inexistente huérfano/500 según enforcement (#1764/#1717); checkbox unchecked persiste activo (#1962); tablas imprimen enum/ID/booleano raw (#1911). Confirmación SQLite hasta GLEntry: Tax sales-only aplicado a plantilla buying genera en PurchaseInvoice gasto débito 100, TAX débito 15, AP crédito 115; evidencia #1015 comentario `6679420934`. Issues existentes cubren hallazgos, sin duplicado. SHA cotejado; DB temporal descartada, sin cambios de producto. |

Conteo reconciliado: **102/564 rutas completas, 462 parciales; HTML/Jinja 63/252 completas y 189 parciales**.

### Cierre posterior — `admin/tax_rules.html` — 2026-11-06

| `cacao_accounting/admin/templates/admin/tax_rules.html` | `81c4944f171b032badd1784a9de497818676e7400b3024af079a9c9a22fee47c` | Completa por cobertura | Template, handlers GET/POST/edit/delete, `tax_rule_service`, builders de compra/venta, FiscalEngine y posting GL cotejados. `curl` real contra servidor Flask efímero: anónimo 302, sesión autenticada sin system-admin 403, system-admin 200. Alta/edición válidas persisten con CSRF según probe HTTP previo. POST eliminar con CSRF da 500 y no muta la fila (#2014 `needs-review`; decisión auditada vs inactivar vs retirar acción sigue abierta). Los errores controlados de alta/edición descartan los valores enviados al re-render (#2017); enums inválidos persistidos #2005; referencias/FK y cuenta de otra compañía #2018; tasa no finita #1010; display raw #1911; quantity sin rate útil #1436. `tax_rule_service._date_value()` captura ISO inválido y `_int_value()` rechaza secuencia no entera. Sonda efímera `.venv`/SQLite: regla válida del formulario (efecto equivalente) al pasar SalesInvoice de 100 produjo líneas GL AR débito 115, Ingresos crédito 100, Tax crédito 15; débito=crédito. Regla de control seleccionada por `build_tax_rule_contexts()` fue solo `valid`, excluyendo inactiva, applies_to purchase, otra compañía, otra moneda, evento distinto y vigencia futura. Persistencia fiscal y filtros corrieron en SQLite efímera; no extrapolar NaN a PostgreSQL. QA independiente confirmó el alcance pendiente y la suficiencia del recorrido GL. Sin cambios de producto/tests permanentes; SHA cotejado y datos descartados. |

Conteo reconciliado: **103/564 rutas completas, 461 parciales; HTML/Jinja 64/252 completas y 188 parciales**.


### Cierre posterior — `admin/usuario_companias.html` — 2026-11-06

| `cacao_accounting/admin/templates/admin/usuario_companias.html` | `9a6974337dd3e48d634d5ff6767ee4e6f3b7d104b81d07b5c1ede957cbee9df5` | Completa por cobertura | Template, `usuario_companias()`, `UserCompanyAccessForm`, modelo y consumidores `Permisos` cotejados. `curl` real Cloud/SQLite: anónimo 302, autenticado sin system-admin 403, admin 200; el HTML contiene CSRF, muestra la compañía habilitada y omite la deshabilitada. Con usuario asignado a ambas, probe de `Permisos`: compañía habilitada concede acceso; la deshabilitada no concede y no aparece en `obtener_companias_autorizadas()`, aunque su fila histórica persiste. Reproducción de POST con CSRF válido y elección inválida: HTTP 200, asignación intacta, error de WTForms no aparece en HTML; se abrió #2021 y se comentó candidato a #1711 (`6679672907`). La edición/revocación de asignaciones existentes falla por `_guard_sensitive_delete()` (#1700, ya caracterizado y comentado); cambio de compañía a disabled sí elimina acceso efectivo. QA independiente confirmó la brecha de cobertura y el resultado. Sin cambios de producto ni tests permanentes; SHA cotejado y base temporal descartada. |

Conteo reconciliado: **104/564 rutas completas, 460 parciales; HTML/Jinja 65/252 completas y 187 parciales**.


### Cierre posterior — `admin/usuario_password.html` — 2026-11-06

| `cacao_accounting/admin/templates/admin/usuario_password.html` | `ad2ee6fda32ad23076e76c38deaa0596cbcc6e89d4b845c46104f4d644075341` | Completa por cobertura | Template y caller `usuario_password()` cotejados con `UserPasswordForm`, `validar_clave_segura()`, `proteger_passwd()` y lista de usuarios. Sondas HTTP/SQLite previas con CSRF: anónimo 302/login, admin 200, débil y confirmación desigual re-renderizan sin cambiar hash; contraseña válida cambia hash y redirige. QA independiente confirma CSRF, autoescape, labels/errores y guardas `login_required` + admin de sistema; sin tests directos localizados. La ruta solo actualiza hash y no invalida token/sesión del objetivo (#1355, política `needs-review`; candidato de sesión #1732). El error de contraseña débil no está traducido (#1740). Estos hallazgos quedan abiertos y caracterizados; la cobertura del archivo está cerrada. No hubo cambios de producto ni pruebas permanentes. SHA cotejado. |

Conteo reconciliado: **105/564 rutas completas, 459 parciales; HTML/Jinja 66/252 completas y 186 parciales**.


### Cierre posterior — `admin/usuario_roles.html` — 2026-11-06

| `cacao_accounting/admin/templates/admin/usuario_roles.html` | `8548fddbc3654b314ded4b20bdbb95ed13bae9d6512408bc08b379b587caa9a3` | Completa por cobertura | Template, `usuario_roles()`, `UserRoleForm`, `RolesUser`, `_obtener_roles_por_usuario()`, `_obtener_roles_disponibles()`, `Permisos` y `tiene_rol()` cotejados. Sondas Flask/SQLite previas: anónimo 302, admin 200 con CSRF, usuario portal redirige; POST con asignación previa da HTTP 500/rollback por guard de borrado (#2006), y usuario sin filas con ID duplicado inserta duplicados (#1682). Sonda adicional: `Roles` no tiene `active`; `RolesUser.active=False` no habilita una ruta que requiere permiso `create` (403/no persistencia), mientras la misma asignación activa permite el control positivo (302/persistencia). Evidencia comentada en #1716 (`6679946138`); no se atribuye un bypass al root. QA independiente confirma cobertura; no hay tests directos del CRUD. Los hallazgos permanecen abiertos; la plantilla queda cerrada por alcance auditado. Sin cambios de producto ni tests permanentes; DB en memoria descartada. SHA cotejado. |

Conteo reconciliado: **106/564 rutas completas, 458 parciales; HTML/Jinja 67/252 completas y 185 parciales**.


### Cierre posterior — `admin/usuarios.html` — 2026-11-06

| `cacao_accounting/admin/templates/admin/usuarios.html` | `e98aab6ce510aafca2ffd152d926678aa95745229e40feb495d1b6b5d73b611d` | Completa por cobertura | Template, `lista_usuarios()`, enlace desde navegación/admin y helpers de conteo/roles cotejados. `curl` real a Flask/SQLite: anónimo 302 `/login`, sesión autenticada sin system-admin 403 y admin 200. La página autoescapa usuarios/roles, traduce textos y muestra al usuario inactivo y su asignación de rol inactiva. QA independiente confirma que la cuenta admin que consulta aparece normalmente en la tabla y que no hay estado vacío ni JS; el límite de alta Desktop está cubierto por la sonda previa. Toggle POST y efectos comprobados: se puede desactivar al único admin (#1767), se limpia JWT pero la cookie Flask sigue activa (#1732). Sin issue nuevo por mostrar roles asignados, pues el encabezado no afirma listar permisos efectivos. No hay cambios de producto/tests permanentes; DB efímera descartada. SHA cotejado. |

Conteo reconciliado: **107/564 rutas completas, 457 parciales; HTML/Jinja 68/252 completas y 184 parciales**.


### Cierre posterior — `admin/usuario_form.html` — 2026-11-06

| `cacao_accounting/admin/templates/admin/usuario_form.html` | `8daddeffd5d833ebd937bddd5e05bc7151ab0840f017e005f36423eceffd4840` | Completa por cobertura | Template, `crear_usuario()`/`editar_usuario()`, ambos WTForms y servicios inmediatos cotejados. Flask/SQLite Cloud + curl: anónimo 302, usuario autenticado sin system-admin 403, admin 200 con CSRF; la opción `admin` solo existe en edición. POST de alta Cloud con email vacío y clave válida persiste. Party customer enviado como supplier y compañía deshabilitada manipulada re-renderizan sin mutación; conversión a portal con RolesUser queda bloqueada. Desktop: GET de alta redirige al listado y POST devuelve 403 sin crear segundo usuario. Desactivar desde edit persiste `active=False`, pero la cookie preexistente mantiene acceso al perfil (HTTP 200), extensión de #1732; el writer tampoco limpia JWT (#1443). Se caracterizan #1948 (email-validator falta y email no vacío da HTTP 500), #1913 (límites de campo frente a DB), #1740 (errores sin gettext) y #2022 (botones `accion` en español con locale EN; issue #2022 contiene la evidencia curl). QA independiente confirma cobertura. No hay nuevos issues; defectos existentes quedan abiertos. Sin cambios de producto/tests permanentes; DB y cookies temporales descartadas. SHA cotejado. |

Conteo reconciliado: **108/564 rutas completas, 456 parciales; HTML/Jinja 69/252 completas y 183 parciales**.


### Cierre posterior — `auth/forgot_password.html` — 2026-11-06

| `cacao_accounting/auth/templates/forgot_password.html` | `ac55311dc9feb029ff5c732a99846feceb2376ada29089c69981ae5706723eb6` | Completa por cobertura | Template, enlace desde login, `forgot_password()`, `ForgotPasswordForm`, `generar_token_recuperacion()`, `enviar_token_recuperacion_email()`, modelo reset y `send_email()` cotejados. Curl real: GET 200; POST sin CSRF 400 (previo, #1948); con email-validator 2.3.0 instalado solo en `.venv`, POST activo, inexistente e inactivo terminan en HTTP 200 y muestran el mismo flash genérico. SMTP se dejó deliberadamente ausente. En solicitud activa los logs muestran token generado y fallo SMTP; DB efímera dejó token no consumido, el previo quedó consumido al repetir y `email_queue` permaneció vacío. Se abrió #2023 (`needs-work`, candidato #1710; comentario root `6680192947`), la raíz conserva `needs-review`. #1948 sigue vigente porque email-validator no está declarado por el producto; #1444 cubre lookup case-insensitive ambiguo, #1695 persistencia de token en texto plano, #1918/#1711 `<html lang>` desacoplado del locale efectivo. No hay tests directos del template/form. La respuesta externa no enumera cuentas; el link de reset no pudo enviarse al no existir SMTP. No se envió correo real; servidor y DB temporales descartados. `email-validator==2.3.0` quedó solo en `.venv`, sin cambios a manifiestos. SHA cotejado. |

Conteo reconciliado: **109/564 rutas completas, 455 parciales; HTML/Jinja 70/252 completas y 182 parciales**.


### Cierre posterior — `auth/reset_password.html` — 2026-11-06

| `cacao_accounting/auth/templates/reset_password.html` | `c73ccbd53a51b6535cda14d3785659a899d6472d427dc5b6178d91bd91a540b0` | Completa por cobertura | Template/caller `reset_password()`, `ResetPasswordForm`, `PasswordResetToken`, `validar_token_recuperacion()` y hash de contraseña cotejados. HTTP/curl previo: token válido GET 200; expirado/reusado 302; POST sin CSRF rechazado; confirmación desigual y contraseña débil re-renderizan sin mutar hash/consumir token; éxito cambia hash y consume token. QA independiente hizo probes concurrentes en PostgreSQL 16.15: dos claims condicionales produjeron `[0,1]`; hash cambió solo en el ganador. Fallo antes del commit revierte hash y consumo juntos. Token expirado permanece `consumed=False` por rollback al terminar el GET, pero la comparación `expires_at` bloquea su reuso; no se demostró impacto más allá de limpieza/retención. #1355 cubre la ausencia de revocación de JWT/sesiones; #1695 registra token de reset en texto plano; #1918/#1711 `<html lang>` sigue `session.lang` en vez del locale efectivo. No hay tests directos del handler/template. QA independiente confirma cobertura; probe temporal PostgreSQL retirado, sin cambios de producto ni tests. SHA cotejado. |

Conteo reconciliado: **110/564 rutas completas, 454 parciales; HTML/Jinja 71/252 completas y 181 parciales**.


### Cierre posterior — `auth/profile.html` — 2026-11-06

| `cacao_accounting/auth/templates/profile.html` | `c4ff681c7ce49c913540e15872809e02baa6d5cec4bfe2ef26d05e3b008a5bff` | Completa por cobertura | Template y ruta `profile()`/dispatch/handlers con `ProfileForm`/`PasswordChangeForm` cotejados; ambos formularios incluyen CSRF, errores por campo, gettext y autoescape. Curl Flask/SQLite con CSRF activo: login/GET perfil 200; POST sin token 400; email duplicado exacto con token 200 sin mutación, pero flash aparece en `alert-success` (#1908, comentario `6680316384`; sin issue duplicado). Cambio válido de datos 302/persistencia (`name`, teléfono, correo vacío, `language=en`); respuesta posterior muestra “My Profile” pero `<html lang="es">` (#1918). POST válido de cambio de contraseña 302; la misma cookie conserva acceso al perfil HTTP 200 (#1355, comentario `6680369408`); contraseña actual incorrecta ya tiene repro y error por campo. QA independiente confirmó extensión #1444: perfil acepta `B@EXAMPLE.ORG` aunque otra cuenta tiene `b@example.org`; esto causa `MultipleResultsFound` al buscar recuperación insensible a mayúsculas (comentario `6680369095`). #1913 cubre límites de campos; #1948 Email validator ausente en manifiesto aunque se instaló solo en `.venv` para sondas. No hay tests directos de estos forms. Sin cambios de producto/tests; DB temporal retirada. SHA cotejado. |

Conteo reconciliado: **111/564 rutas completas, 453 parciales; HTML/Jinja 72/252 completas y 180 parciales**.


### Cierre posterior — `auth/templates/test_roles.html` — 2026-11-06

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/auth/templates/test_roles.html` | `c275c0c5ed3963152669c23e6d124a2da741a57b547dd2d21896d36229953ee3` | Completa por cobertura. `/permisos_usuario`: anónimo 302, usuario autenticado 200; muestra solo su propia identidad/roles y escapa nombre y contenido de rol. Con rol activo y módulo activo muestra `crear` autorizado; asignación inactiva aparece en “Roles Asignados” pero no autoriza; módulos deshabilitados se presentan con permisos denegados. Defectos abiertos: atributo `modulo.modulo` no existe en `Modules` (#2007, comentario `6680681404`); se expone “Validar Solicitud” sin propiedad calculada (#1576, comentario `6680681717`). Sin callers/enlaces internos detectados; función desconectada queda candidata bajo #1658 `needs-review`, pendiente de confirmar contrato externo. Sin cambios de producto/tests permanentes. Hash actual cotejado. |

Conteo vigente: **112/564 rutas completas, 452 parciales; HTML/Jinja 73/252 completas y 179 parciales**.


### Cierre posterior — `auth/templates/login.html` — 2026-11-06

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/auth/templates/login.html` | `5474e78f215c63091d7950bb534c917b3ffb7a77a8eec2c0c293f4f1d6006ca9` | Completa por cobertura. Credenciales válidas Cloud autentican; usuario no-admin Desktop no; existente/no-existente usan mensaje genérico. OTP end-to-end con transport local: solicitud no autentica hasta código; código incorrecto muestra error y su contador no persiste (#1762); código correcto consume OTP, inicia sesión y crea dispositivo. Cookie reconocida vigente evita OTP; token expirado la exige. Lockout activo niega credenciales correctas y se muestra con estilo success (#1908). Sesión OTP perdida vuelve a login. Vacíos validan HTTP 200 sin mostrar errores; se anotó como candidato de feedback/contrato bajo #1711 (`6680749686`). Con `SETUP_LANGUAGE=en`, textos se traducen a inglés mientras `lang` queda `es` (#1918/#1711). Hash cotejado; sin SMTP externo, producto ni tests permanentes modificados. Issues existentes abiertos. |

Conteo vigente: **113/564 rutas completas, 451 parciales; HTML/Jinja 74/252 completas y 178 parciales**.


### Cierre posterior — `bancos/templates/bancos.html` — 2026-11-06

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/bancos/templates/bancos.html` | `9e239d71442c3d84e6c8ef6b6b0d0f73a2336db17cb300308701eb4ab2b149fb` | Completa por cobertura. Home `/cash_management/cash`: anónimo 302, usuarios autenticados 200; plantilla evalúa los grupos, permisos y badges; rutas se construyen correctamente. Desktop oculta forecast, y los destinos forecast redirigen a home en desktop (validación de lote anterior). Dos defectos reproducidos en SQLite y registrados como hijos de #1711: #2024, rol `reportes` autorizado a las compañías puede abrir ambos endpoints de informe, pero el dashboard los esconde porque el bloque depende de `acceso.autorizado`; #2025, rol con `access` sin `consultar` ve enlace forecast con badge no-access y recibe 403 al seguirlo. Comentarios root `6680825322`, `6680851819`. Sin forms, SMTP ni mutaciones; no se tocó producto/tests. Hash cotejado. |

Conteo vigente: **114/564 rutas completas, 450 parciales; HTML/Jinja 75/252 completas y 177 parciales**.

### Cierre posterior — Detalle de banco — 2026-11-06

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/bancos/templates/bancos/banco.html` | `efec684e2fc712ccda8243c3efe7302adaeeb7dc4249f1cd41eb9b99ee66f0bc` | Completo por cobertura: se cotejó el detalle con `bancos_banco()`, el modelo global `Bank` (sin propietario de compañía), y los destinos de navegación. La vista muestra nombre, SWIFT y estado activo/inactivo; Jinja autoescapa los valores, no hay formulario ni mutación. Curl/SQLite previo: anónimo GET 302 a login, usuario autenticado sin RBAC GET 200 y admin 200. Esa ruta carece de guard RBAC de consulta; el enlace “Nuevo” se muestra a todos los usuarios autenticados y la ruta de alta permitió POST con CSRF válido sin `cash/crear` (#1526, extendido a #1601; comentarios `6669567844`, `6669568328`). El defecto corresponde al contrato de acceso del catálogo, no a lógica propia de esta plantilla; queda abierto. SHA verificado contra HEAD. No se repitió servidor ni sonda; no hubo cambios de producto/tests. |

Conteo vigente: **115/564 rutas completas, 449 parciales; HTML/Jinja 76/252 completas y 176 parciales**.


### Cierre Jinja — `banco_lista.html` — 2026-11-06

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/bancos/templates/bancos/banco_lista.html` | `f3e87b23aac8d2db3a972ecfa7d2c590db52dfdd1c4206528b0d6eafa2a9d0b6` | Completa por cobertura. Cotejados el handler `bancos_banco_lista()`, `_paginate_list`, `apply_list_filters`, macros de filtros/paginación, modelo global `Bank`, enlaces y traducciones. Curl real contra Flask/SQLite: anónimo 302 a login; sesión autenticada sin roles 200. Búsqueda con 12 filas navega en 2 páginas y conserva `search`; una búsqueda inexistente devuelve `0 items encontrados` y `Página 1 de 0`, sin estado vacío (#2026, issue hijo candidato de #1711; comentario root `6681035995`). Swift `<script>x</script>` se sirve escapado. `aria-label="breadcrumb"` queda literal en inglés para el locale español (#2027, candidato i18n/accesibilidad bajo #1711; comentario root `6681054700`). CTA “Nuevo” visible a la sesión sin permisos, pero creación sin `cash.crear` ya está cubierta por #1526/#1601. No hay mutación propia en la lista. SHA cotejado; DB/servidor efímeros se cerraron y no hubo cambios de producto/tests. |

Conteo vigente: **116/564 rutas completas, 448 parciales; HTML/Jinja 77/252 completas y 175 parciales; 1024 issues abiertos (24 root/1000 code)**.


### Cierre Jinja — alta de banco — 2026-11-06

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/bancos/templates/bancos/banco_nuevo.html` | `51622111ad6dea0f6bf6ef9cff5bd8c94b47722e13a796479733db564da20d00` | Completa por cobertura. Cotejados campos visibles, WTForms, CSRF, endpoint y modelo. Evidencia previa Flask/SQLite: GET anónimo 302, usuario sin RBAC 200; POST válido con CSRF creó un banco incluso sin `cash.crear` (#1526/#1601). Probe curl actual sin token CSRF devolvió 400 y dejó la cuenta de bancos en cero. QA independiente confirmó POST `name=""` y `name="   "`: HTTP 200 sin fila nueva, pero el template no muestra el error de `DataRequired` (#2029, hijo candidato #1711, comentario root `6681172389`). SWIFT de 21 caracteres fue aceptado por SQLite, mientras PostgreSQL produjo HTTP 500 `StringDataRightTruncation` por `String(20)` (#2028, candidato #1717, comentario root `6681156190`). Se registraron límites sin modificar producto. Hash cotejado; app/DB/probes efímeros retirados. |

Conteo vigente: **117/564 rutas completas, 447 parciales; HTML/Jinja 78/252 completas y 174 parciales; 1026 issues abiertos (24 root/1002 code)**.


### Cierre Jinja — gasto de caja chica — 2026-11-06

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/bancos/templates/bancos/caja_chica_gasto_nuevo.html` | `bd19cb488889111c8e349acc4f3671db3dd0a80c1f81a7447ead8be2c16e24a5` | Completa por cobertura. Cotejados template, macro `smart_select`, `FormularioPettyCashExpense`, `caja_chica_gasto_nuevo()` y writers `create_petty_cash_expense()`/`cancel_petty_cash_expense()`. Curl/Flask/SQLite: anónimo 302, usuario sin `cash.crear` 403, usuario autorizado 200; POST sin CSRF 400; POST negativo no persiste. El GET de `voucher_id` de otra compañía filtra beneficiario/concepto/importe (#1989 → #1649). El POST conserva `voucher_id` en query string, pero la ruta toma solo `request.form`, de modo que el vale no llega al writer (#1945, comentario `6681149737`; root #1711 `6681151591`). Se probó el camino válido de gasto directo y gasto ligado a vale con asientos GL. Fallo inyectado tras commit GL dejó diario durable sin `PettyCashExpense` (#1991 → #1653); fallo inyectado durante actualización de estado de gasto tras reversión dejó GL cancelado, gasto `docstatus=1` y vale `liquidado` (#2030 → #1653; comentarios root `6681302275`, hijo `6681302607`). Ambos son fallos de atomicidad entre ledger y subledger; no se modificó producto. Chromium real confirmó que al cambiar compañía se limpia el fondo, pero moneda visible conserva NIO hasta elegir el fondo nuevo (#2031, candidato #1711; root `6681439259`). El campo de centro de costo aparece obligatorio, pero el macro no recibe `required=True`; issue #2032 candidato #1711, comentario root `6681482400`. Selector `naming_series` también se muestra y se ignora al persistir; extensión de decisión de negocio #1992, comentario `6681439582` (mantener `needs-review`). La búsqueda de centro de costo en una sonda inicialmente vacía se explicó por el fixture que dejó `CostCenter.group=None`; al corregirlo a `False`, el catálogo devolvió `MAIN - Principal`, por lo que no se abrió issue por ese resultado. Persisten issues de permisos/alcance, transferencia de voucher, atomicidad, UX, y selección de serie; el cierre solo señala cobertura auditada. Hash cotejado; DB y proceso efímeros retirados, sin cambios de producto/tests permanentes. |

Conteo vigente: **118/564 rutas completas, 446 parciales; HTML/Jinja 79/252 completas y 173 parciales**.


### Cierre Jinja — reposición de caja chica — 2026-11-06

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/bancos/templates/bancos/caja_chica_reposicion_nueva.html` | `ceb56fa7da8d36437af5f3beb8f1d278aaf6d641f725adc7fbb632d6f5ccc6f8` | Completa por cobertura. Cotejados markup, callbacks Smart Select, `caja_chica_reposicion_nueva()`, `create_petty_cash_replenishment()`, lectores de gastos, estado y servicio de reposición. Evidencia HTTP/SQLite existente: anon 302; editor/admin 200; viewer/no-role 403; POST sin CSRF 400; fecha inválida y gasto ajeno rechazados. GET con `petty_cash_id` de otra compañía filtra conceptos/importes de esa compañía antes de validar acceso (#1986 → #1649; corroborado a root `6681580533`). POST válido con expense posteado alcanza guard append-only al asignar `replenishment_id`, devuelve 500 y revierte solicitud/reserva (#1987 → #1706, needs-review por contrato del vínculo; corroboración `6681580804`). Chromium y Flask/SQLite GET con query `petty_cash_id` y `company` retornó 200, pero los inputs hidden de ambos Smart Select quedan vacíos después de la navegación; el callback vuelve a recargar al seleccionar fondo, por lo que no se conserva estado para enviar (#2033, candidato #1711; comentario root `6681563054`). `naming_series` visible no se lee en la ruta y el writer asigna `naming_series_id=None`; extensión documentada en #1992 (`6681580221`, needs-review). Ramas `if reposicion` y `attached_ids` no tienen caller local: único `render_template` es la ruta de creación, que no recibe ni pasa esos valores; issue #2034 `needs-review`, candidato #1658, root `6681579859`. Sin cambios productivos/tests. QA independiente confirmó findings y hash. Hash cotejado.

Conteo vigente: **119/564 rutas completas, 445 parciales; HTML/Jinja 80/252 completas y 172 parciales**.


### Cierre Jinja — alta de vale de caja chica — 2026-11-06

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/bancos/templates/bancos/caja_chica_vale_nuevo.html` | 57bedfae520653f90c8248510e77741753a13f6eaadcd225bc19018197a525c7 | Completa por cobertura. Cotejados template, smart_select, WTForms, caja_chica_vale_nuevo(), create_petty_cash_voucher() y set_petty_cash_voucher_status(). Curl/SQLite previo confirmó anon 302, sin permiso 403, editor/admin 200, CSRF y alta en borrador sin GL; estados inválidos y compañía/fondo ajenos no persisten. Payload de dimensiones cost_center/unit/project de otra compañía sí se guardó (#1988 → #1649); usuario cash-only recibe 403 en catálogos contables (#1327, criterio cross-module). amount=abc da 500 (#1185). La serie alternativa elegida se serializa en hidden input, pero ruta/servicio la ignoran y usan default (#1992, needs-review; corroboraciones 6681439582, 6681580221, 6681711909). La rama de edición if vale no tiene caller/contexto ni endpoint; el enlace de lista produce BuildError (#1647), candidato de dead code bajo #1658 (6681579859, antecedente 6673186051). Chromium real confirmó que company/fund se seleccionan y el callback muestra NIO/USD, pero al cambiar compañía se limpia el fondo y permanece moneda obsoleta hasta escoger el nuevo (#2031, extensión comentada 6681711585). Chromium POST amount=0: HTTP 200, no se persiste vale; el re-render pierde company y petty_cash_id, aunque conserva el importe, nuevo #2035 candidato #1711 (root 6681710816, relación #1951 comentada 6681711162). aria-label se traduce desde msgid breadcrumb cuyo msgstr es también breadcrumb; defecto compartido con #2027, se añadió a la evidencia de ese issue. QA independiente coincidió en findings/alcance. Sin cambios productivos/tests permanentes; hash cotejado. |

Conteo vigente: **120/564 rutas completas, 444 parciales; HTML/Jinja 81/252 completas y 171 parciales**.


### Cierre Jinja — comparación de pronósticos de caja — 2026-11-06

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/bancos/templates/bancos/cash_forecast_comparar.html` | `751de88027fbb75239919550c504977ff38b7148b8e5047d3845dbfc0c63365b` | Completa por cobertura. Cotejados template, `cash_forecast_compare()`, `_cash_forecast_comparison()`, `get_forecast_comparison()`, `get_cash_forecast_matrix()` y formatter monetario. Curl/SQLite previo: anon 302, sin RBAC 403, viewer/admin de compañía autorizada 200; ID de otra compañía produce 404. Playwright con dos pronósticos reales del fixture confirmó GET 200, selección DOM efectiva de `base_id` y `compare_id`, doce filas del ejercicio y zonas `Real`/`Current`/`Projected`; aunque el markup también marca el placeholder `selected`, Chromium eligió correctamente el ID solicitado, sin defecto visible observado. La comparación puede emparejar semanas por etiqueta sin año y sustituir filas no coincidentes por cero entre años/frecuencias (#1084, `needs-review`; candidato de criterio). Importe se calcula en moneda funcional pero el template no pasa moneda al formatter y omite código (`800.00` en evidencia previa; #2015, comentarios `6681826235`, #1655/#1711 candidatos; #1942 relacionado). Zonas y estados internos `Draft`/`Approved`/`Closed`/`Archived` salen crudos sin gettext; msgids equivalentes no se encontraron (#2037 candidato #1711, root `6681825635`). `aria-label="breadcrumb"` está literal y se agregó a #2027 (`6681825927`). Sin cambios productivos/tests permanentes; hash cotejado. |

Conteo vigente: **121/564 rutas completas, 443 parciales; HTML/Jinja 82/252 completas y 170 parciales**.


### Cierre Jinja — importación legacy de extractos bancarios — 2026-11-06

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/bancos/templates/bancos/extracto_importar.html` | `a6152a0bee480fd3f28a088220020b69551b1810f3c800c147cdd45339ee0b82` | Completa por cobertura y clasificada como plantilla sin consumidor local. Búsqueda de referencias no encontró `render_template` ni otra inclusión; la traducción PO conserva referencias históricas, no ejecución. La única ruta `/bank-statement/import` redirige a `imports.new`, y el flujo activo registra `BankStatementAdapter`; el menú aún usa el shim. Curl/auth existentes: anónimo 302 login; admin 302 al wizard; usuario sin permiso Imports llega al shim y el destino responde 403. No hay formulario ni carga propia en esta plantilla. Hallazgo agrupado bajo #1046 (`6682010582`); no se retiró el template ni el shim porque el contrato externo de URL sigue en revisión bajo #1658. SHA coincide. Sin cambios de producto/tests. |

Conteo vigente: **122/564 rutas completas, 442 parciales; HTML/Jinja 83/252 completas y 169 parciales**.


### Cierre Jinja — listado compartido de pagos — 2026-11-06

| Ruta | SHA-256 | Estado/evidencia |
|---|---|---|
| `cacao_accounting/bancos/templates/bancos/pago_lista.html` | `db8c3b2126b41d75c1f1b2bcf6adec1e8b95f5255a2c6d4651f0450371bef480` | Completa por cobertura de plantilla y cuatro callers: pago, transferencia, nota de débito y nota de crédito. Revisados markup, columnas, CTA/contexto, filtros, status y paginación; `_paginate_list()` filtra por tipo y scope de compañía/período. Flask/SQLite/curl ya documentado confirma anon 302, scope por compañía, acceso a filas propias, enlaces a detalle 200, filtros por tipo/status/búsqueda/período, página inválida normalizada, otras compañías ocultas y período sin compañía rechazado en multiempresa. Sin RBAC de consulta retorna lista vacía. Hallazgos abiertos caracterizados: estado vacío #2041; paginación de las tres rutas especializadas apunta a `/payment/list` #2042; monto/tipo mal presentados para receive/credit note y enums sin gettext #1949; unidad/pierna de transferencia pendiente de decisión #2043 (`needs-review`, candidato #1655/#1711). Se comentaron las causas candidatas con los roots, sin confirmarlas. La plantilla no tiene interacción JavaScript propia. SHA cotejado; sin cambio de producto/tests permanentes. |

Conteo vigente: **123/564 rutas completas, 441 parciales; HTML/Jinja 84/252 completas y 168 parciales**.
