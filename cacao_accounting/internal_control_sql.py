"""Lex and inspect raw SQL before it can change protected accounting tables."""

import re
from collections.abc import Collection


def _quoted_sql_end(statement: str, start: int, dialect_name: str) -> int:
    """Return the position after a quoted SQL string or identifier."""
    quote = statement[start]
    index = start + 1
    while index < len(statement):
        if _backslash_escapes(statement, start, dialect_name) and statement[index] == "\\":
            index += 2
            continue
        if statement[index] == quote:
            if index + 1 < len(statement) and statement[index + 1] == quote:
                index += 2
                continue
            return index + 1
        index += 1
    return len(statement)


def _backslash_escapes(statement: str, quote_start: int, dialect_name: str) -> bool:
    """Return whether this SQL dialect treats backslash as a quote escape."""
    if dialect_name in {"mysql", "mariadb"}:
        return True
    if dialect_name != "postgresql" or statement[quote_start] != "'" or quote_start == 0:
        return False
    return statement[quote_start - 1] in {"e", "E"} and (
        quote_start == 1 or not (statement[quote_start - 2].isalnum() or statement[quote_start - 2] == "_")
    )


def _dollar_quote_end(statement: str, start: int) -> int | None:
    """Return the position after a PostgreSQL dollar-quoted string."""
    if start and (statement[start - 1].isalnum() or statement[start - 1] in "_$"):
        return None
    delimiter_match = re.match(r"\$(?:[A-Za-z_][A-Za-z_0-9]*)?\$", statement[start:])
    if delimiter_match is None:
        return None
    delimiter = delimiter_match.group()
    closing = statement.find(delimiter, start + len(delimiter))
    return len(statement) if closing < 0 else closing + len(delimiter)


def _block_comment_end(statement: str, start: int) -> int:
    """Skip a possibly nested SQL block comment."""
    depth = 1
    index = start + 2
    while index < len(statement) and depth:
        if statement.startswith("/*", index):
            depth += 1
            index += 2
        elif statement.startswith("*/", index):
            depth -= 1
            index += 2
        else:
            index += 1
    return index


def _line_comment_end(statement: str, start: int) -> int:
    """Skip a SQL line comment through its newline or end of input."""
    newline = statement.find("\n", start)
    return len(statement) if newline < 0 else newline + 1


def _versioned_comment(statement: str, start: int) -> tuple[str, int]:
    """Return executable SQL and the end of a MySQL versioned comment."""
    prefix_size = 4 if statement[start : start + 4].lower() == "/*m!" else 3
    end = statement.find("*/", start + prefix_size)
    if end < 0:
        return "", len(statement)
    body = statement[start + prefix_size : end]
    body = re.sub(r"^\s*\d+\s*", " ", body, count=1)
    return body, end + 2


def _strip_comments(statement: str, dialect_name: str) -> str:
    """Replace SQL comments with spaces while preserving quoted content."""
    result: list[str] = []
    index = 0
    while index < len(statement):
        if dialect_name in {"mysql", "mariadb"} and (
            statement.startswith("/*!", index) or statement[index : index + 4].lower() == "/*m!"
        ):
            body, index = _versioned_comment(statement, index)
            result.append(_strip_comments(body, dialect_name))
        elif statement.startswith("/*", index):
            result.append(" ")
            index = _block_comment_end(statement, index)
        elif statement.startswith("--", index) or (dialect_name in {"mysql", "mariadb"} and statement[index] == "#"):
            result.append(" ")
            index = _line_comment_end(statement, index)
        elif dialect_name == "postgresql" and statement[index] == "$":
            end = _dollar_quote_end(statement, index)
            if end is None:
                result.append(statement[index])
                index += 1
            else:
                result.append(statement[index:end])
                index = end
        elif statement[index] in {"'", '"', "`"}:
            end = _quoted_sql_end(statement, index, dialect_name)
            result.append(statement[index:end])
            index = end
        else:
            result.append(statement[index])
            index += 1
    return "".join(result)


def _remove_string_literals(statement: str, dialect_name: str) -> str:
    """Remove single-quoted values while keeping quoted SQL identifiers."""
    result: list[str] = []
    index = 0
    while index < len(statement):
        dollar_end = _dollar_quote_end(statement, index) if dialect_name == "postgresql" and statement[index] == "$" else None
        if dollar_end is not None:
            result.append(" ")
            index = dollar_end
        elif statement[index] == "'":
            result.append(" ")
            index = _quoted_sql_end(statement, index, dialect_name)
        else:
            result.append(statement[index])
            index += 1
    return "".join(result)


def _sql_code(statement: str, dialect_name: str) -> str:
    """Return SQL with comments and string values removed."""
    return _remove_string_literals(_strip_comments(statement, dialect_name), dialect_name)


def _sql_targets(code: str) -> list[str]:
    """Return target table names covered by supported SQL write forms."""
    qualified_table = r'(?:["`]?\w+["`]?\.)?["`]?([\w]+)'
    patterns = (
        r"\b(?:INSERT(?:(?:\s+OR\s+\w+)|(?:\s+(?:LOW_PRIORITY|DELAYED|HIGH_PRIORITY|IGNORE)))*"
        r"\s+(?:INTO\s+)?|REPLACE(?:\s+(?:LOW_PRIORITY|DELAYED|HIGH_PRIORITY))*\s+(?:INTO\s+)?)" + qualified_table,
        r"\bUPDATE(?:(?:\s+OR\s+\w+)|(?:\s+(?:LOW_PRIORITY|IGNORE)))*\s+(?:ONLY\s+)?" + qualified_table,
        r"\bDELETE(?:\s+(?:LOW_PRIORITY|QUICK|IGNORE))*\s+FROM\s+(?:ONLY\s+)?" + qualified_table,
        r"\bDELETE(?:\s+(?:LOW_PRIORITY|QUICK|IGNORE))*\s+[\w`\".*]+(?:\s*,\s*[\w`\".*]+)*"
        + r"\s+FROM\s+(?:ONLY\s+)?"
        + qualified_table,
        r"\bTRUNCATE(?:\s+TABLE)?\s+(?:ONLY\s+)?" + qualified_table,
        r"\bMERGE\s+INTO\s+(?:ONLY\s+)?" + qualified_table,
        r"\bCOPY(?:\s+BINARY)?\s+" + qualified_table + r"\b[^;]*?\bFROM\b",
        r"\bLOAD\s+(?:DATA|XML)\b[^;]*?\bINTO\s+TABLE\s+" + qualified_table,
    )
    return [table for pattern in patterns for table in re.findall(pattern, code, flags=re.IGNORECASE)]


def _mysql_multi_delete_references_protected_table(code: str, protected: set[str], dialect_name: str) -> bool:
    """Detect protected tables anywhere in a MySQL multi-table DELETE source."""
    match = re.search(r"\bDELETE(?:\s+(?:LOW_PRIORITY|QUICK|IGNORE))*\s+(?!FROM\b)[\s\S]+?\s+FROM\s+", code, re.I)
    if match is None:
        return False
    sources = _text_before_top_level_clause(code, match.end(), r"WHERE|ORDER\s+BY|LIMIT", dialect_name)
    return any(re.search(rf"(?<!\w)[\"`]?{re.escape(table)}[\"`]?(?!\w)", sources, re.I) for table in protected)


def _mysql_delete_using_targets_protected_table(code: str, protected: set[str]) -> bool:
    """Detect protected targets in MySQL's DELETE FROM ... USING form."""
    match = re.search(
        r"\bDELETE(?:\s+(?:LOW_PRIORITY|QUICK|IGNORE))*\s+FROM\s+(?P<targets>[\s\S]+?)\s+USING\b",
        code,
        re.I,
    )
    if match is None:
        return False
    target_list = match.group("targets")
    target_names = {name.lower() for name in re.findall(r'["`]?([\w]+)["`]?', target_list)}
    if protected.intersection(target_names):
        return True

    sources = _text_before_top_level_clause(code, match.end(), "WHERE", "mysql")
    reserved_words = {"as", "cross", "inner", "join", "left", "natural", "on", "outer", "right"}
    for table in protected:
        source_table = (
            rf"(?<!\w)(?:[\"`]?\w+[\"`]?\.)?[\"`]?{re.escape(table)}[\"`]?"
            rf"(?:\s+PARTITION\s*\([^)]*\))?(?:\s+(?:AS\s+)?([\"`]?\w+[\"`]?))?"
        )
        for alias in re.findall(source_table, sources, re.I):
            normalized_alias = alias.strip('"`').lower()
            if normalized_alias and normalized_alias not in reserved_words and normalized_alias in target_names:
                return True
    return False


def _text_before_top_level_clause(code: str, start: int, clause_pattern: str, dialect_name: str) -> str:
    """Read SQL text until a clause keyword at parenthesis depth zero."""
    depth = 0
    index = start
    while index < len(code):
        if code[index] in {'"', "`"}:
            index = _quoted_sql_end(code, index, dialect_name)
            continue
        if code[index] == "(":
            depth += 1
        elif code[index] == ")":
            depth = max(depth - 1, 0)
        elif depth == 0 and code[index] == ";":
            return code[start:index]
        elif depth == 0 and code[index].isspace():
            clause = re.match(rf"\s+(?:{clause_pattern})\b", code[index:], re.I)
            if clause is not None:
                return code[start:index]
        index += 1
    return code[start:]


def _multi_table_update_references_protected_table(code: str, protected: set[str], dialect_name: str) -> bool:
    """Detect protected tables among sources in multi-table UPDATE statements."""
    if not re.match(r"\s*(?:UPDATE|WITH)\b", code, re.I):
        return False
    updates = re.finditer(r"\bUPDATE(?:(?:\s+OR\s+\w+)|(?:\s+(?:LOW_PRIORITY|IGNORE)))*\s+", code, re.I)
    for update in updates:
        sources = _text_before_top_level_clause(code, update.end(), "SET", dialect_name)
        if any(re.search(rf"(?<!\w)[\"`]?{re.escape(table)}[\"`]?(?!\w)", sources, re.I) for table in protected):
            return True
    return False


def raw_sql_mutates_protected_table(statement: str, protected_tables: Collection[str], dialect_name: str = "sqlite") -> bool:
    """Detect raw SQL writes to protected tables, including unfamiliar DML syntax."""
    code = _sql_code(statement, dialect_name)
    protected = {table.lower() for table in protected_tables}
    if re.match(r"\s*(?:DO|PREPARE|EXECUTE|EXEC|CALL)\b", code, re.I):
        return True
    targets = _sql_targets(code)
    if (
        _mysql_delete_using_targets_protected_table(code, protected)
        or _mysql_multi_delete_references_protected_table(code, protected, dialect_name)
        or _multi_table_update_references_protected_table(code, protected, dialect_name)
        or any(target.lower() in protected for target in targets)
    ):
        return True
    if targets or not re.match(r"\s*(?:INSERT|UPDATE|DELETE|REPLACE|TRUNCATE|MERGE|COPY|LOAD)\b", code, re.I):
        return False
    return any(re.search(rf"(?<!\w)[\"`]?{re.escape(table)}[\"`]?(?!\w)", code, re.I) for table in protected)
