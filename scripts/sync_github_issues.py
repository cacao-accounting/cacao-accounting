#!/usr/bin/env python3
"""Sincroniza los issues de GitHub a una base SQLite local.

Permite consultar y buscar el backlog completo sin consumir la cuota de la API
de GitHub. La base se reconstruye en cada ejecución; las notas locales viven en
una tabla aparte y no se tocan.

Uso:
    python scripts/sync_github_issues.py
    python scripts/sync_github_issues.py --state all
    python scripts/sync_github_issues.py --no-comments --limit 50
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_OWNER = "cacao-accounting"
DEFAULT_REPO = "cacao-accounting"
DEFAULT_DB = Path(".local/github/issues.db")
PAGE_SIZE = 100

ISSUES_QUERY = """
query($owner: String!, $repo: String!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    issues(first: %d, after: $cursor, states: %s, orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        body
        state
        stateReason
        url
        createdAt
        updatedAt
        closedAt
        author { login }
        issueType { name }
        milestone { title dueOn }
        labels(first: 30) { nodes { name color description } }
        assignees(first: 10) { nodes { login } }
        comments { totalCount }
        parent { number title }
        subIssuesSummary { total completed }
      }
    }
  }
}
"""

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS issues (
    number INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    body TEXT,
    state TEXT NOT NULL,
    state_reason TEXT,
    author TEXT,
    issue_type TEXT,
    milestone TEXT,
    milestone_due TEXT,
    comments_count INTEGER DEFAULT 0,
    sub_issues_total INTEGER DEFAULT 0,
    sub_issues_completed INTEGER DEFAULT 0,
    parent_number INTEGER,
    parent_title TEXT,
    url TEXT,
    created_at TEXT,
    updated_at TEXT,
    closed_at TEXT,
    raw_json TEXT,
    synced_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS labels (
    name TEXT PRIMARY KEY,
    color TEXT,
    description TEXT
);

CREATE TABLE IF NOT EXISTS issue_labels (
    issue_number INTEGER NOT NULL REFERENCES issues(number) ON DELETE CASCADE,
    label TEXT NOT NULL REFERENCES labels(name) ON DELETE CASCADE,
    PRIMARY KEY (issue_number, label)
);

CREATE TABLE IF NOT EXISTS assignees (
    issue_number INTEGER NOT NULL REFERENCES issues(number) ON DELETE CASCADE,
    login TEXT NOT NULL,
    PRIMARY KEY (issue_number, login)
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY,
    issue_number INTEGER NOT NULL,
    author TEXT,
    body TEXT,
    created_at TEXT,
    updated_at TEXT,
    url TEXT
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_number INTEGER,
    created_at TEXT NOT NULL,
    body TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    state TEXT NOT NULL,
    total_issues INTEGER DEFAULT 0,
    total_comments INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_issue_labels_label ON issue_labels(label);
CREATE INDEX IF NOT EXISTS idx_issues_parent ON issues(parent_number);
CREATE INDEX IF NOT EXISTS idx_issues_state ON issues(state);
CREATE INDEX IF NOT EXISTS idx_comments_issue ON comments(issue_number);

CREATE VIRTUAL TABLE IF NOT EXISTS issues_fts USING fts5(
    title,
    body,
    content='issues',
    content_rowid='number',
    tokenize='unicode61 remove_diacritics 2'
);
"""

VIEWS = """
DROP VIEW IF EXISTS v_issues;
CREATE VIEW v_issues AS
SELECT
    i.number,
    i.title,
    i.state,
    i.author,
    i.parent_number,
    i.comments_count,
    i.updated_at,
    (SELECT group_concat(l.label, ', ') FROM issue_labels l WHERE l.issue_number = i.number) AS labels,
    (SELECT group_concat(a.login, ', ') FROM assignees a WHERE a.issue_number = i.number) AS assignees
FROM issues i;

DROP VIEW IF EXISTS v_phases;
CREATE VIEW v_phases AS
SELECT p.number, p.title, p.sub_issues_total, p.sub_issues_completed
FROM issues p
WHERE p.number IN (2240, 2241, 2242, 2243, 2244, 2245, 2246, 2247);

DROP VIEW IF EXISTS v_umbrellas;
CREATE VIEW v_umbrellas AS
SELECT i.number, i.title, i.parent_number, i.sub_issues_total, i.sub_issues_completed
FROM issues i
JOIN issue_labels l ON l.issue_number = i.number
WHERE l.label = 'root';
"""


def utc_now() -> str:
    """Devuelve la marca de tiempo actual en formato ISO 8601 UTC."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_gh(args: list[str]) -> str:
    """Ejecuta la CLI de GitHub y devuelve su salida estándar."""
    try:
        result = subprocess.run(["gh", *args], check=True, capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit("No se encontró 'gh' en PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"gh falló ({exc.returncode}): {exc.stderr.strip()}") from exc
    return result.stdout


def fetch_page(owner: str, repo: str, states: str, cursor: str | None) -> dict[str, Any]:
    """Descarga una página de issues vía GraphQL."""
    query = ISSUES_QUERY % (PAGE_SIZE, states)
    args = ["api", "graphql", "-f", f"query={query}", "-f", f"owner={owner}", "-f", f"repo={repo}"]
    if cursor:
        args.extend(["-f", f"cursor={cursor}"])
    payload = json.loads(run_gh(args))
    return payload["data"]["repository"]["issues"]


def iter_issues(owner: str, repo: str, states: str, limit: int | None) -> Iterator[dict[str, Any]]:
    """Itera los issues abiertos, cerrados o todos, página por página."""
    cursor: str | None = None
    fetched = 0
    while True:
        page = fetch_page(owner, repo, states, cursor)
        for node in page["nodes"]:
            yield node
            fetched += 1
            if limit is not None and fetched >= limit:
                return
        if not page["pageInfo"]["hasNextPage"]:
            return
        cursor = page["pageInfo"]["endCursor"]


def fetch_comments(owner: str, repo: str) -> list[dict[str, Any]]:
    """Descarga todos los comentarios del repositorio con paginación de la CLI."""
    raw = run_gh(["api", "--paginate", "--slurp", f"repos/{owner}/{repo}/issues/comments?per_page={PAGE_SIZE}"])
    pages = json.loads(raw)
    return [comment for page in pages for comment in page]


def create_schema(conn: sqlite3.Connection) -> None:
    """Crea tablas, índices, vistas y el índice de búsqueda de texto completo."""
    conn.executescript(SCHEMA)
    conn.executescript(VIEWS)


def store_issue(conn: sqlite3.Connection, node: dict[str, Any], synced_at: str) -> None:
    """Inserta un issue con sus etiquetas y responsables."""
    milestone = node.get("milestone") or {}
    parent = node.get("parent") or {}
    summary = node.get("subIssuesSummary") or {}
    author = node.get("author") or {}
    issue_type = node.get("issueType") or {}
    conn.execute(
        """
        INSERT INTO issues (
            number, title, body, state, state_reason, author, issue_type, milestone,
            milestone_due, comments_count, sub_issues_total, sub_issues_completed,
            parent_number, parent_title, url, created_at, updated_at, closed_at, raw_json, synced_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            node["number"],
            node["title"],
            node.get("body"),
            node["state"],
            node.get("stateReason"),
            author.get("login"),
            issue_type.get("name"),
            milestone.get("title"),
            milestone.get("dueOn"),
            (node.get("comments") or {}).get("totalCount", 0),
            summary.get("total", 0),
            summary.get("completed", 0),
            parent.get("number"),
            parent.get("title"),
            node.get("url"),
            node.get("createdAt"),
            node.get("updatedAt"),
            node.get("closedAt"),
            json.dumps(node, ensure_ascii=False),
            synced_at,
        ),
    )
    for label in (node.get("labels") or {}).get("nodes", []):
        conn.execute(
            """
            INSERT INTO labels (name, color, description) VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET color = excluded.color, description = excluded.description
            """,
            (label["name"], label.get("color"), label.get("description")),
        )
        conn.execute("INSERT OR IGNORE INTO issue_labels (issue_number, label) VALUES (?, ?)", (node["number"], label["name"]))
    for assignee in (node.get("assignees") or {}).get("nodes", []):
        conn.execute(
            "INSERT OR IGNORE INTO assignees (issue_number, login) VALUES (?, ?)", (node["number"], assignee["login"])
        )


def store_comments(conn: sqlite3.Connection, comments: list[dict[str, Any]], issue_numbers: set[int]) -> int:
    """Inserta los comentarios que pertenecen a los issues sincronizados."""
    stored = 0
    for comment in comments:
        issue_number = int(comment["issue_url"].rsplit("/", 1)[-1])
        if issue_number not in issue_numbers:
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO comments (id, issue_number, author, body, created_at, updated_at, url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                comment["id"],
                issue_number,
                (comment.get("user") or {}).get("login"),
                comment.get("body"),
                comment.get("created_at"),
                comment.get("updated_at"),
                comment.get("html_url"),
            ),
        )
        stored += 1
    return stored


def sync(args: argparse.Namespace) -> int:
    """Ejecuta la sincronización completa y devuelve el total de issues."""
    states = {"open": "[OPEN]", "closed": "[CLOSED]", "all": "[OPEN, CLOSED]"}[args.state]
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()

    conn = sqlite3.connect(db_path)
    try:
        create_schema(conn)
        conn.execute("BEGIN")
        conn.execute("DELETE FROM issues")
        conn.execute("DELETE FROM issue_labels")
        conn.execute("DELETE FROM assignees")
        conn.execute("DELETE FROM comments")

        synced_at = utc_now()
        issue_numbers: set[int] = set()
        for node in iter_issues(args.owner, args.repo, states, args.limit):
            store_issue(conn, node, synced_at)
            issue_numbers.add(node["number"])

        total_comments = 0
        if not args.no_comments and issue_numbers:
            total_comments = store_comments(conn, fetch_comments(args.owner, args.repo), issue_numbers)

        conn.execute("INSERT INTO issues_fts(issues_fts) VALUES('rebuild')")
        conn.execute(
            "INSERT INTO sync_runs (started_at, finished_at, state, total_issues, total_comments) VALUES (?, ?, ?, ?, ?)",
            (started_at, utc_now(), args.state, len(issue_numbers), total_comments),
        )
        conn.commit()
    finally:
        conn.close()

    print(f"Base: {db_path}")
    print(f"Issues: {len(issue_numbers)} | Comentarios: {total_comments}")
    return len(issue_numbers)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Define y parsea los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(description="Sincroniza issues de GitHub a SQLite.")
    parser.add_argument("--db", default=str(DEFAULT_DB), help=f"Ruta de la base (por defecto {DEFAULT_DB}).")
    parser.add_argument("--owner", default=DEFAULT_OWNER, help="Propietario del repositorio.")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="Nombre del repositorio.")
    parser.add_argument("--state", choices=("open", "closed", "all"), default="open", help="Estado de los issues.")
    parser.add_argument("--limit", type=int, default=None, help="Máximo de issues a descargar (para pruebas).")
    parser.add_argument("--no-comments", action="store_true", help="Omite los comentarios.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada del script."""
    args = parse_args(argv)
    sync(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
