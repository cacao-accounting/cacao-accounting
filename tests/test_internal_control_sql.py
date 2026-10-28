"""Tests for SQL dialect handling in the financial evidence guard."""

import pytest

from cacao_accounting.internal_control_sql import raw_sql_mutates_protected_table

PROTECTED_TABLE = "import_landed_cost_charge"


@pytest.mark.parametrize(
    ("dialect", "statement"),
    [
        ("postgresql", "SELECT 'x\\'; UPDATE import_landed_cost_charge SET amount = 0"),
        ("postgresql", "SELECT $$#x$$; UPDATE import_landed_cost_charge SET amount = 0"),
        ("postgresql", "WITH foo$tag$ AS (SELECT 1) UPDATE import_landed_cost_charge SET amount = 0"),
        ("postgresql", "DO $$ BEGIN UPDATE import_landed_cost_charge SET amount = 0; END $$"),
        ("mysql", "/*!80000 UPDATE import_landed_cost_charge SET amount = 0 */"),
        ("mariadb", "/*M!100100 DELETE FROM import_landed_cost_charge */"),
        ("mysql", "UPDATE#comment\n import_landed_cost_charge SET amount = 0"),
        ("mysql", "UPDATE ordinary_table o JOIN import_landed_cost_charge p ON p.id=o.id SET p.amount=0"),
        ("mysql", "PREPARE stmt FROM 'UPDATE import_landed_cost_charge SET amount=0'"),
        ("mysql", "EXECUTE stmt"),
        (
            "mysql",
            "DELETE p FROM ordinary_table o JOIN (SELECT id FROM foo WHERE id > 0) s ON s.id=o.id "
            "JOIN import_landed_cost_charge p ON p.id=s.id WHERE p.id > 0",
        ),
        ("mysql", "DELETE p\nFROM ordinary_table o JOIN import_landed_cost_charge p ON p.id=o.id"),
        (
            "mysql",
            "DELETE FROM ordinary_table, import_landed_cost_charge USING ordinary_table "
            "JOIN import_landed_cost_charge ON ordinary_table.id=import_landed_cost_charge.id WHERE ordinary_table.id=1",
        ),
        (
            "mysql",
            "DELETE FROM o, p USING ordinary_table AS o JOIN import_landed_cost_charge AS p "
            "ON ordinary_table.id=import_landed_cost_charge.id WHERE ordinary_table.id=1",
        ),
        (
            "mysql",
            "DELETE FROM p USING ordinary_table AS o JOIN import_landed_cost_charge "
            "PARTITION (p0) AS p ON ordinary_table.id=import_landed_cost_charge.id",
        ),
        (
            "mysql",
            "WITH cte AS (SELECT 1) UPDATE ordinary_table o JOIN import_landed_cost_charge p " "ON p.id=o.id SET p.amount=0",
        ),
    ],
)
def test_raw_sql_blocks_protected_writes_across_dialects(dialect: str, statement: str) -> None:
    """Reject protected writes hidden by dialect-specific SQL syntax."""
    assert raw_sql_mutates_protected_table(statement, {PROTECTED_TABLE}, dialect)


@pytest.mark.parametrize(
    ("dialect", "statement"),
    [
        ("postgresql", "SELECT 'UPDATE import_landed_cost_charge SET amount = 0'"),
        ("postgresql", "SELECT $$UPDATE import_landed_cost_charge SET amount = 0$$"),
        ("postgresql", "/*!80000 UPDATE import_landed_cost_charge SET amount = 0 */"),
        ("mysql", "SELECT 'UPDATE import_landed_cost_charge SET amount = 0'"),
        ("mysql", "UPDATE ordinary_table SET amount=(SELECT amount FROM import_landed_cost_charge)"),
        ("mysql", "DELETE FROM o USING ordinary_table AS o JOIN import_landed_cost_charge AS p ON p.id=o.id"),
    ],
)
def test_raw_sql_ignores_literals_and_non_executable_comments(dialect: str, statement: str) -> None:
    """Do not mistake values and ordinary comments for protected writes."""
    assert not raw_sql_mutates_protected_table(statement, {PROTECTED_TABLE}, dialect)
