"""Extract auditable Jinja and HTML units without assigning audit states.

Inline scripts and Alpine expressions are parsed with Node’s bundled Acorn.
Expressions that cannot be parsed are explicitly marked for manual review.
"""

import re
import subprocess
from collections import Counter
from html.parser import HTMLParser

from jinja2 import Environment
from jinja2.visitor import NodeVisitor

ENVIRONMENT = Environment(extensions=["jinja2.ext.i18n", "jinja2.ext.do", "jinja2.ext.loopcontrols"])


class JinjaUnits(NodeVisitor):
    """Collect template definitions and executable control blocks."""

    def __init__(self):
        """Initialize the definition list and lexical scope stack."""
        self.units = []
        self.scopes = []

    def _named(self, node, kind):
        name = ".".join([*self.scopes, node.name])
        self.units.append((node.lineno, f"{kind} {name}"))
        self.scopes.append(node.name)
        self.generic_visit(node)
        self.scopes.pop()

    def visit_Macro(self, node):
        """Collect a macro and its nested executable units."""
        self._named(node, "macro")

    def visit_Block(self, node):
        """Collect a block and its nested executable units."""
        self._named(node, "bloque")

    def _control(self, node, kind):
        scope = ".".join(self.scopes)
        prefix = f"{scope}: " if scope else ""
        self.units.append((node.lineno, f"{prefix}{kind} [línea {node.lineno}]"))
        self.generic_visit(node)

    def visit_If(self, node):
        """Collect a conditional branch."""
        self._control(node, "condicional Jinja")

    def visit_For(self, node):
        """Collect a template loop."""
        self._control(node, "bucle Jinja")

    def visit_CallBlock(self, node):
        """Collect a caller block."""
        self._control(node, "llamada Jinja")


def mask_jinja(source):
    """Remove Jinja markup while retaining line positions for the HTML parser."""
    pattern = re.compile(r"{[{%#].*?[}%#]}", re.DOTALL)

    def replace(match):
        text = match.group()
        masked = re.sub(r"[^\n]", " ", text)
        if text.startswith("{{"):
            return "0" + masked[1:]
        return masked

    return pattern.sub(replace, source)


JINJA_STATEMENT = re.compile(r"{%-?\s*(\w+)\b.*?-?%}", re.DOTALL)


def _blank(text):
    """Preserve source offsets and lines while disabling a template branch."""
    return re.sub(r"[^\n]", " ", text)


def jinja_variants(source, limit=32):
    """Expand conditional branches for static JS parsing, or fail visibly.

    Conditions are not evaluated: all branches and the implicit empty branch
    are parsed. Unsupported control structures and excessive combinations are
    left for manual inspection instead of hiding unexamined JavaScript.
    """
    tags = list(JINJA_STATEMENT.finditer(source))

    def expand(start, end):
        first = next((i for i in range(start, end) if tags[i].group(1) == "if"), None)
        if first is None:
            if start < end:
                raise ValueError("unsupported Jinja statement in JavaScript")
            return [source]
        if first != start:
            raise ValueError("unsupported Jinja statement in JavaScript")
        depth, split, closing = 0, [first], None
        for i in range(first, end):
            kind = tags[i].group(1)
            if kind == "if":
                depth += 1
            elif kind == "endif":
                depth -= 1
                if depth == 0:
                    closing = i
                    break
            elif kind in {"else", "elif"} and depth == 1:
                split.append(i)
            elif kind not in {"else", "elif"}:
                raise ValueError("unsupported Jinja statement in JavaScript")
        if closing is None:
            raise ValueError("unclosed Jinja conditional")
        split.append(closing)
        branch_choices = list(range(len(split) - 1))
        if tags[split[-2]].group(1) != "else":
            branch_choices.append(None)
        output = []
        for chosen in branch_choices:
            value = list(source)
            for branch, (left, right) in enumerate(zip(split, split[1:])):
                if branch != chosen:
                    value[tags[left].end() : tags[right].start()] = _blank(source[tags[left].end() : tags[right].start()])
            for i in range(first, closing + 1):
                if chosen is None or not (split[chosen] < i < split[chosen + 1]):
                    value[tags[i].start() : tags[i].end()] = _blank(tags[i].group())
            candidate = "".join(value)
            remaining = [m for m in JINJA_STATEMENT.finditer(candidate)]
            if remaining:
                variants = jinja_variants(candidate, limit)
            else:
                variants = [candidate]
            output.extend(variants)
            if len(output) > limit:
                raise ValueError("too many Jinja branch combinations")
        return output

    if not tags:
        return [mask_jinja(source)]
    return [mask_jinja(value) for value in expand(0, len(tags))]


class HtmlUnits(HTMLParser):
    """Collect forms, actions, Alpine components and handlers from HTML markup."""

    def __init__(self, source):
        """Initialize parser state while retaining original source line offsets."""
        super().__init__(convert_charrefs=True)
        self.source_lines = source.splitlines(keepends=True)
        self.units = []
        self.sequence = 0
        self.script_line = None
        self.script_content = []
        self.script_errors = []

    def _add(self, line, kind):
        self.sequence += 1
        label = f"{kind} [línea {line}, elemento {self.sequence}]"
        self.units.append((line, label))
        return label

    def _alpine_component(self, line, expression, value_line):
        """Identify object methods and callbacks inside an Alpine component."""
        label = self._add(line, "componente Alpine")
        if not expression:
            return
        try:
            entries = set()
            for variant in jinja_variants(expression):
                entries.update(javascript_units(f"({variant})"))
        except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
            self._add(line, "componente Alpine: análisis JS pendiente")
            return
        for relative_line, name in sorted(entries):
            if name != "[módulo JavaScript]":
                self.units.append((value_line + relative_line - 1, f"{label}.{name}"))

    def handle_starttag(self, tag, attrs):
        """Collect executable units declared by a start tag."""
        line = self.getpos()[0]
        attributes = dict(attrs)
        if tag == "form":
            self._add(line, "formulario")
        if tag == "button" or (tag == "input" and attributes.get("type", "").lower() in {"submit", "button", "reset"}):
            self._add(line, "acción HTML")
        if tag == "a" and ("href" in attributes or any(key.startswith(("@", "x-on:")) for key in attributes)):
            self._add(line, "enlace de acción")
        if tag == "script" and "src" not in attributes:
            self.script_line = line
            self.script_content = []
        for name, value in attrs:
            if name == "x-data":
                tag_text = self.get_starttag_text()
                match = re.search(r"\bx-data\s*=\s*[\"']", tag_text)
                value_line = line + tag_text[: match.end()].count("\n") if match else line
                if match:
                    quote = tag_text[match.end() - 1]
                    end = tag_text.find(quote, match.end())
                    if end >= 0:
                        raw_offset = sum(map(len, self.source_lines[: line - 1])) + self.getpos()[1]
                        raw_tag = "".join(self.source_lines)[raw_offset : raw_offset + len(tag_text)]
                        value = raw_tag[match.end() : end]
                self._alpine_component(line, value, value_line)
            elif name.startswith(("@", "x-on:")) or name in {"x-init", "x-effect"} or name.startswith("on"):
                self._add(line, f"handler {name}")

    handle_startendtag = handle_starttag

    def handle_data(self, data):
        """Retain inline script data for JavaScript extraction."""
        if self.script_line is not None:
            self.script_content.append(data)

    def handle_endtag(self, tag):
        """Extract inline JavaScript when its script element closes."""
        if tag != "script" or self.script_line is None:
            return
        line = self.script_line
        try:
            entries = javascript_units("".join(self.script_content))
            if entries == [(1, "[módulo JavaScript]")]:
                self._add(line, "script embebido")
            else:
                for relative_line, name in entries:
                    self.units.append((line + relative_line - 1, f"script [línea {line}].{name}"))
        except (subprocess.CalledProcessError, FileNotFoundError) as error:
            self.script_errors.append((line, str(error)))
            self._add(line, "script embebido: análisis JS pendiente")
        self.script_line = None


def template_units(source):
    """Return source-ordered candidate units; malformed Jinja raises an error."""
    visitor = JinjaUnits()
    visitor.visit(ENVIRONMENT.parse(source))
    parser = HtmlUnits(source)
    parser.feed(mask_jinja(source))
    parser.close()
    units = sorted(visitor.units + parser.units, key=lambda item: item[0])
    if not units:
        return [(1, "[plantilla]")]
    counts = Counter(name for _, name in units)
    seen = Counter()
    result = []
    for line, name in units:
        seen[name] += 1
        if counts[name] > 1:
            name = f"{name} (ocurrencia {seen[name]})"
        result.append((line, name))
    return result


def javascript_units(source):
    """Parse JavaScript through the Acorn bundled with Node; report parser failures."""
    import json
    import subprocess
    from pathlib import Path

    parser = Path(__file__).with_name("audit_javascript_symbols.cjs")
    result = subprocess.run(
        ["node", "--expose-internals", str(parser)], input=source, text=True, capture_output=True, check=True
    )
    units = json.loads(result.stdout)
    return [(unit["line"], unit["name"]) for unit in units] or [(1, "[módulo JavaScript]")]
