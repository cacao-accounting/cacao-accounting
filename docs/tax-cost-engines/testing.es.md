# Estrategia de pruebas

Los motores de cálculo se prueban proporcionando varios objetos `CalculationContext` y verificando las estructuras `Result` esperadas.

## 1. Pruebas unitarias
- `tests/engines/test_fiscal_engine.py`
- `tests/engines/test_landed_cost_engine.py`
- `tests/engines/test_settlement_engine.py`

## 2. Prueba de referencia obligatoria
- `tests/engines/test_golden_import.py`: Verifica el caso de importación DAI/ISC/IVA.
