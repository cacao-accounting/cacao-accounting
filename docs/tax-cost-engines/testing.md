# Testing Strategy

The calculation engines are tested by providing various `CalculationContext` objects and asserting the expected `Result` structures.

## 1. Unit Tests
- `tests/engines/test_fiscal_engine.py`
- `tests/engines/test_landed_cost_engine.py`
- `tests/engines/test_settlement_engine.py`

## 2. Mandatory Reference Test
- `tests/engines/test_golden_import.py`: Verifies the DAI/ISC/IVA import case.
