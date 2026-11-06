#!/usr/bin/env python3
"""Locate historical audit evidence without inferring symbol coverage.

Output is derived from tracked source documents and is not an audit state store.
Exact paths are required to avoid attributing a similarly named file's evidence.
"""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

DOCUMENTS = ("AUDIT_PENDING.md", "AUDIT_COMPLETE.md", "AUDIT_PROGRESS.md")
PATH_REFERENCE = re.compile(r"`([^`\n]+)`")
SHA256 = re.compile(r"\b[0-9a-f]{64}\b")


def read_document(root, document):
    """Read a local historical document or its committed HEAD version."""
    path = root / document
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return subprocess.check_output(["git", "show", f"HEAD:{document}"], cwd=root, text=True, encoding="utf-8")


def current_digest(root, path):
    """Return the SHA-256 of a regular file, or None when it no longer exists."""
    file = root / path
    if not file.is_file():
        return None
    return hashlib.sha256(file.read_bytes()).hexdigest()


def collect_evidence(root, paths):
    """Find exact path references, reporting all candidates and hash matches.

    Lines with multiple hashes are ambiguous: a hash match then establishes only
    that the line mentions the current digest, not which path that hash describes.
    """
    paths = set(paths)
    digests = {path: current_digest(root, path) for path in paths}
    for document in DOCUMENTS:
        for line_number, line in enumerate(read_document(root, document).splitlines(), 1):
            references = paths.intersection(PATH_REFERENCE.findall(line))
            hashes = SHA256.findall(line)
            for path in sorted(references):
                yield {
                    "archivo": path,
                    "documento": document,
                    "línea": line_number,
                    "texto": line,
                    "sha256_actual": digests[path],
                    "sha256_mencionados": hashes,
                    "sha256_coincide": digests[path] in hashes if digests[path] is not None else False,
                }


def partial_symbol_evidence(symbol, entries):
    """Return narrowly explicit review evidence for a symbol, without inferring completion.

    Only an exact qualified name directly followed by an affirmative review verb
    is accepted; a file-level review or a mere mention is insufficient. A hash
    must uniquely identify the current file in the same line. The returned entry
    is a candidate for human reconciliation, not proof of complete coverage.
    """
    name = symbol.removesuffix("()")
    pattern = re.compile(
        rf"`{re.escape(name)}(?:\(\))?`\s+(?:fue\s+|ha sido\s+)?"
        r"(?:revisad[oa]s?|auditad[oa]s?|cotejad[oa]s?|verificad[oa]s?)\b",
        re.IGNORECASE,
    )
    for entry in entries:
        hashes = entry["sha256_mencionados"]
        if len(hashes) == 1 and entry["sha256_coincide"] and pattern.search(entry["texto"]):
            return entry
    return None


def main():
    """Print JSON lines for the exact repository paths supplied by the caller."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="Rutas exactas relativas a la raíz del repositorio")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    for item in collect_evidence(root, args.paths):
        print(json.dumps(item, ensure_ascii=False))


if __name__ == "__main__":
    main()
