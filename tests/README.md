# Suite de pruebas — documento de trabajo

Este archivo define cómo se construye la suite nueva de Cacao Accounting.

## Estado

- **2026-11-13:** se eliminaron los 195 archivos de prueba anteriores (borrado
  staged, sin commit). Se conservó `tests/setup_mysql.sql` porque
  `.github/workflows/databases.yml` lo usa.
- **Respaldo:** `/tmp/opencode/tests-backup-20261113-130622.tar.gz`.
- **Decisión:** no se restaura la suite anterior. Se construye una suite de
  **casos de negocio reales**, no una prueba por issue ni pruebas sintéticas
  para subir cobertura.

## Principio

> Las pruebas validan **casos de negocio reales de los flujos O2C, S2P, I2F,
> CTM y R2R**. No se escriben pruebas sintéticas cuyo único fin sea decir que el
> código "tiene pruebas" que lo cubren o inflar la métrica de cobertura.

Una prueba es válida cuando representa una operación que un usuario real haría
y verifica su resultado contable, financiero o de inventario:

- Facturar a crédito, abonar parcialmente, anular el abono y comprobar que el
  saldo vuelve al valor original y que el GL conserva el registro y su
  contraasiento.
- Comprar, recibir mercancía, facturar y pagar, verificando costo, stock y
  cuentas por pagar.
- Transferir inventario entre bodegas y comprobar existencias y costo.
- Registrar un gasto de caja chica, reponer el fondo y anular el gasto sin
  romper la atomicidad del GL.
- Cerrar un período y verificar que los reportes R2R cuadran.

Datos de prueba: realistas y mínimos (tercero, artículo, moneda, fecha y monto
coherentes con el caso). Nada de filas sueltas creadas solo para que el test
“pase”.

## Organización

```text
tests/
├── conftest.py              # app real y sesión aislada por test
├── setup_mysql.sql          # infraestructura CI (no borrar)
├── test_o2c_*.py            # ciclo de venta
├── test_s2p_*.py            # ciclo de abastecimiento
├── test_i2f_*.py            # inventario
├── test_ctm_*.py            # caja, bancos y tesorería
├── test_r2r_*.py            # reportes y cierre
└── README.md
```

Los issues **no** definen archivos de prueba. Un issue documenta un defecto; su
corrección se valida ampliando el caso de negocio del flujo correspondiente con
el escenario que reprodujo el defecto. Si el caso no existe, se crea el caso de
negocio completo, no un test aislado del issue.

## Qué debe verificar cada caso

- El resultado de negocio: saldo, asiento, stock, costo, estado del documento.
- Los invariantes del sistema: append-only, anulación/reversa, multilibro,
  multimoneda, aislamiento por compañía.
- Al menos un caso límite real: pago parcial, anulación, reversa en otro
  período, tasa de cambio faltante, concurrencia o cierre de período.

No se valida la implementación interna ni se usan mocks del dominio. La prueba
corre contra base de datos real y falla si la regla de negocio se rompe.

## Matriz de motores

| Motor | Tier | Uso |
|---|---|---|
| SQLite | 1 (Desktop) | corrida normal de desarrollo |
| PostgreSQL | 1 (Cloud) | validación obligatoria |
| MySQL | 2 | validación en CI |

Las pruebas de los tres motores deben ejecutarse contra bases desechables
reservadas exclusivamente para pruebas. No restablezcas una base compartida ni
una base con datos de usuario.

Comando de referencia para un motor aislado (desde la raíz del repositorio):

```bash
# CACAO_TEST_DATABASE_URL debe apuntar a una base desechable y exclusiva.
CHECK_DATABASE=true DATABASE_URL="$CACAO_TEST_DATABASE_URL" \
  .venv/bin/python -m pytest tests/test_o2c_credit_sale.py -q
```

- Define `CACAO_TEST_DATABASE_URL` con la URI de SQLite, PostgreSQL o MySQL
  apuntando a una base exclusiva para pruebas; no incluyas credenciales reales
  en el repositorio.

## Cobertura

La cobertura es una consecuencia de probar los flujos reales, no el objetivo.
Mínimos exigidos: 90 % del código nuevo del fix y 85 % del preexistente editado.
Si un caso de negocio no se puede cubrir sin datos artificiales, se documenta la
limitación en el issue; no se inventa la prueba.

## Seguimiento

| Flujo | Caso de negocio | Archivo | Estado |
|---|---|---|---|
| O2C | _pendiente_ | | |
| S2P | _pendiente_ | | |
| I2F | _pendiente_ | | |
| CTM | Importar entradas de pronóstico y rechazar monedas inexistentes | `test_ctm_cash_forecast_import.py` | Inicial, matriz de 3 motores |
| R2R | Autorizar gastos y rechazar previews de presupuesto obsoletos sin duplicar montos | `test_r2r_budget_line_integrity.py` | Inicial, matriz de 3 motores |
| R2R | Revaluar exposición bancaria y anular corridas anteriores | `test_r2r_exchange_revaluation.py` | Inicial |
