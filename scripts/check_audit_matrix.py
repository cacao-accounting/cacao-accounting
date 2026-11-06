#!/usr/bin/env python3
"""Check matrix structure and extractable symbols; print derived coverage metrics."""

import argparse
import csv
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

from audit_frontend_symbols import javascript_units, template_units
from audit_python_symbols import symbols

ROOT = Path(__file__).resolve().parent.parent
HEADER = ["Nombre de archivo", "Clase/Función/Macro", "Estado", "Comentarios"]
STATES = {"Pendiente", "Parcial", "Completo"}
AUXILIARY = """.coveragerc .dockerignore .git-blame-ignore-revs .github/FUNDING.yml
.github/workflows/ci.yml .github/workflows/databases.yml .github/workflows/lint.yml
.github/workflows/publish.yml .github/workflows/python.yml .gitignore .mypy.ini
.pydocstyle .replit Dockerfile MANIFEST.in babel.cfg codecov.yml development.txt
docker-compose.yml docker-entry-point.sh docs.txt docs/examples/cacao-accounting.service
docs/oci_files/Caddyfile docs/oci_files/mysql.sh docs/oci_files/psql.sh
docs/theme_override_home/home.html docs/theme_override_home/main.html mkdocs.yml
pyproject.toml replit.nix requirements.txt run.py scripts/run_server.sh scripts/run_test.sh
scripts/run_tests_by_file.sh scripts/update_translations.sh setup.cfg wsgi.py""".split()


def tracked_scope():
    """Return tracked project files and the agreed auxiliary scope."""
    tracked = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0"))
    return sorted(
        {
            p
            for p in tracked
            if p.startswith("cacao_accounting/")
            and "/static/media/" not in p
            and "/static/test/" not in p
            and not p.endswith(".mo")
        }
        | (set(AUXILIARY) & tracked)
        | {p for p in tracked if p.startswith("scripts/") and p.endswith((".py", ".sh", ".js", ".cjs"))}
        | {
            p.relative_to(ROOT).as_posix()
            for pattern in ("audit_*", "check_audit_matrix.py")
            for p in (ROOT / "scripts").glob(pattern)
            if p.is_file() and p.suffix in {".py", ".js", ".cjs"}
        }
        | {
            p.relative_to(ROOT).as_posix()
            for pattern in ("test_audit_*", "test_check_audit_matrix.py")
            for p in (ROOT / "scripts").glob(pattern)
            if p.is_file() and p.suffix == ".py"
        }
    )


def expected(path):
    """Extract currently supported definitions in source order."""
    source = (ROOT / path).read_text(encoding="utf-8") if not path.endswith(".ods") else ""
    if path.endswith(".py.mako"):
        normalized = re.sub(r"\$\{[^}]*\}", "0", source)
        return ["[plantilla de migración]", *symbols(normalized, path)]
    if path.endswith(".py"):
        return ["[módulo]", *symbols(source, path)]
    if path.endswith(".html"):
        return [name for _, name in template_units(source)]
    if path.endswith((".js", ".cjs")):
        return ["[script]", *[name for _, name in javascript_units(source)]]
    return ["[configuración]"]


def check(rows, paths):
    """Report structural errors and mismatches against the supported extractor."""
    errors = []
    grouped = defaultdict(list)
    for line, row in enumerate(rows, 2):
        if None in row or any(row.get(column) is None for column in HEADER):
            errors.append(f"Línea {line}: número de columnas inválido")
            continue
        path, name, state, comment = (row[column] for column in HEADER)
        if state not in STATES or not name or not comment:
            errors.append(f"Línea {line}: estado o campos inválidos")
        if "análisis JS pendiente" in name:
            errors.append(f"Análisis JavaScript pendiente: {path}: {name}")
        grouped[path].append(name)
    if list(grouped) != sorted(grouped):
        errors.append("Las rutas no están ordenadas")
    for path in sorted(set(paths) | set(grouped)):
        if path not in paths:
            errors.append(f"Ruta fuera del alcance: {path}")
        elif path not in grouped:
            errors.append(f"Ruta ausente: {path}")
        else:
            names = grouped[path]
            if len(set(names)) != len(names):
                errors.append(f"Símbolos duplicados: {path}")
            if names != expected(path):
                errors.append(f"Símbolos u orden diferentes al extractor: {path}")
    return errors


def metrics(rows):
    """Derive counts per file and module without persisting them."""
    files = defaultdict(Counter)
    modules = defaultdict(Counter)
    for row in rows:
        path, state = row[HEADER[0]], row[HEADER[2]]
        files[path][state] += 1
        parts = path.split("/")
        module = "/".join(parts[:2]) if parts[0] == "cacao_accounting" and len(parts) > 2 else parts[0]
        modules[module][state] += 1
    counts = Counter(row[HEADER[2]] for row in rows)
    return {
        "archivos": len(files),
        "símbolos": len(rows),
        "estados": dict(counts),
        "porcentaje_completo": 100 * counts["Completo"] / len(rows) if rows else 0,
        "archivos_completos": sorted(path for path, c in files.items() if c["Completo"] == sum(c.values())),
        "por_archivo": dict(files),
        "por_módulo": dict(modules),
    }


def check_issues(rows):
    """Confirm that every referenced issue exists in the project repository."""
    references = sorted({int(number) for row in rows for number in re.findall(r"#(\d+)", row[HEADER[3]])})
    errors = []
    for number in references:
        result = subprocess.run(
            ["gh", "api", f"repos/cacao-accounting/cacao-accounting/issues/{number}", "--jq", ".number"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode or result.stdout.strip() != str(number):
            errors.append(f"No se pudo verificar el issue #{number}: {result.stderr.strip()}")
    return errors


def main():
    """Validate CSV structure and print JSON metrics."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-issues", action="store_true", help="Verificar referencias mediante GitHub")
    args = parser.parse_args()
    with (ROOT / "AUDIT_MATRIX.csv").open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != HEADER:
            print("Encabezado inválido", file=sys.stderr)
            return 1
        rows = list(reader)
    errors = check(rows, tracked_scope())
    if args.check_issues:
        errors.extend(check_issues(rows))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(json.dumps(metrics(rows), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
