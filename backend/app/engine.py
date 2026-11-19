"""Conservative, deterministic Python source analysis and safe-by-default repairs.

This module NEVER imports or executes the code supplied by the user.
"""
from __future__ import annotations

import ast
import io
import tokenize
from dataclasses import asdict, dataclass
from difflib import unified_diff
import re
from time import perf_counter
from typing import Optional

from . import runtime_diagnostics


@dataclass(frozen=True)
class Edit:
    start: int
    end: int
    replacement: str


@dataclass(frozen=True)
class Finding:
    id: str
    rule: str
    title: str
    detail: str
    severity: str
    category: str
    line: int
    confidence: int
    suggestion: str
    edit: Optional[Edit] = None

    def public(self) -> dict:
        result = asdict(self)
        result.pop("edit", None)
        result["fix_available"] = self.edit is not None
        return result


def _offset(source: str, line: int, col: int) -> int:
    lines = source.splitlines(keepends=True)
    target = lines[line - 1] if 0 < line <= len(lines) else ""
    # CPython AST columns are UTF-8 byte offsets; translate to Unicode characters.
    chars_before = len(target.encode("utf-8")[:col].decode("utf-8", errors="ignore"))
    return sum(len(x) for x in lines[: line - 1]) + chars_before


def _finding(rule: str, title: str, detail: str, severity: str, category: str,
             line: int, confidence: int, suggestion: str, edit: Edit | None) -> Finding:
    unique_id = f"{rule}-L{line}" + (f"-P{edit.start}" if edit is not None else "")
    return Finding(unique_id, rule, title, detail, severity, category,
                   line, confidence, suggestion, edit)


def _is_call(node: ast.AST, function: str, name: str) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == function and len(node.args) == 1 and isinstance(node.args[0], ast.Name) and node.args[0].id == name and not node.keywords


def _len_plus_one(node: ast.AST) -> str | None:
    if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Add):
        return None
    for length, one in ((node.left, node.right), (node.right, node.left)):
        if isinstance(length, ast.Call) and isinstance(length.func, ast.Name) and length.func.id == "len" and len(length.args) == 1 and isinstance(length.args[0], ast.Name) and not length.keywords and isinstance(one, ast.Constant) and type(one.value) is int and one.value == 1:
            return length.args[0].id
    return None


def _missing_closing_delimiters(source: str, error: SyntaxError) -> Finding | None:
    """Suggest closing EOF delimiters only when a Python parse proves it works.

    Tokenize rather than counting characters, so parentheses in strings/comments
    cannot influence the repair. This is an inspectable syntax-only suggestion;
    no source code is executed here.
    """
    if "was never closed" not in (error.msg or "") and "unexpected EOF while parsing" not in (error.msg or ""):
        return None
    opens = {"(": ")", "[": "]", "{": "}"}
    closes = {value: key for key, value in opens.items()}
    stack: list[tuple[str, int]] = []
    tokens: list[tokenize.TokenInfo] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            tokens.append(token)
    except tokenize.TokenError as exc:
        # Only accept an unfinished bracketed expression, never a multiline string.
        if "multi-line statement" not in str(exc):
            return None
    except (IndentationError, SyntaxError):
        return None

    for token in tokens:
        if token.type != tokenize.OP:
            continue
        if token.string in opens:
            stack.append((token.string, token.start[0]))
        elif token.string in closes:
            if not stack or stack[-1][0] != closes[token.string]:
                return None
            stack.pop()
    if not (1 <= len(stack) <= 3):
        return None

    # Insert just after the final substantive token, before comments/newlines.
    # Refuse to move any non-comment content, and keep the change minimal.
    ignored = {tokenize.ENDMARKER, tokenize.NL, tokenize.NEWLINE,
               tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT}
    useful = [token for token in tokens if token.type not in ignored
              and (token.type != tokenize.ERRORTOKEN or token.string.strip())]
    if not useful:
        return None
    last = useful[-1]
    lines = source.splitlines(keepends=True)
    if not 0 < last.end[0] <= len(lines):
        return None
    position = sum(len(line) for line in lines[:last.end[0] - 1]) + last.end[1]
    suffix = source[position:]
    if any(part.strip() and not part.lstrip().startswith("#") for part in suffix.splitlines()):
        return None
    closing = "".join(opens[char] for char, _ in reversed(stack))
    proposed = source[:position] + closing + source[position:]
    try:
        ast.parse(proposed)
    except SyntaxError:
        return None

    names = {"(": "parenthesis", "[": "square bracket", "{": "brace"}
    description = " and ".join(names[char] for char, _ in stack)
    return _finding(
        "PY-SYNTAX-003", "Unclosed Python delimiter",
        f"The expression has an unclosed {description}; Python cannot parse it.",
        "critical", "Syntax", stack[-1][1], 97,
        f"Insert {closing!r} after the expression. Proposed code passes Python syntax parsing; verify behavior separately.",
        Edit(position, position, closing),
    )



def _simple_print_literal_repair(source: str, error: SyntaxError) -> Finding | None:
    """Repair only standalone Python 3 print + a simple quoted literal.

    Examples: print"hello -> print("hello"), print 'hi' -> print('hi').
    This intentionally does NOT guess about unclosed literals inside calls,
    escaped quotes, interpolation, string concatenation, or other expressions.
    The full proposed source must parse before a fix is offered. No execution.
    """
    line_no = error.lineno or 1
    lines = source.splitlines(keepends=True)
    if line_no < 1 or line_no > len(lines):
        return None
    raw = lines[line_no - 1]
    line = raw.rstrip("\r\n")
    match = re.fullmatch(r"(?P<indent>[ \t]*)print[ \t]*(?P<quote>['\"])(?P<text>[^\\\r\n]*)", line)
    if not match:
        return None
    quote = match.group('quote')
    tail = match.group('text')
    # Only zero or one quote is acceptable; any quote must be the very last
    # character.  Leave escaped/complex/multiline strings for human review.
    if tail.count(quote) > 1 or (quote in tail and not tail.endswith(quote)):
        return None
    content = tail[:-1] if tail.endswith(quote) else tail
    if not content or len(content) > 200 or content.startswith(("'", '"')):
        return None
    if any(c in content for c in (';', '#')):
        return None
    replacement = match.group('indent') + 'print(' + quote + content + quote + ')'
    start = sum(len(chunk) for chunk in lines[:line_no - 1])
    end = start + len(line)
    proposed = source[:start] + replacement + source[end:]
    try:
        ast.parse(proposed)
    except (SyntaxError, ValueError):
        return None
    return _finding(
        'PY-SYNTAX-004', 'Malformed simple print statement',
        'This looks like a print statement with a string literal but without Python 3 call syntax; the quote may also be unfinished.',
        'critical', 'Syntax', line_no, 95,
        'Wrap the literal in print(...) and close the string where needed. Syntax parses; verify the intended behavior.',
        Edit(start, end, replacement),
    )


def _assignment_in_condition_repair(source: str, error: SyntaxError) -> Finding | None:
    """Repair single '=' assignment inside if/elif/while header to comparison '=='.

    The entire proposed source must parse with ast.parse before offering the fix.
    """
    line_no = error.lineno or 1
    lines = source.splitlines(keepends=True)
    if line_no < 1 or line_no > len(lines):
        return None
    raw = lines[line_no - 1]
    line = raw.rstrip("\r\n")
    stripped = line.strip()
    if not re.match(r"^(?:if|elif|while)\b", stripped):
        return None
    # Look for single '=' not preceded or followed by '=', '!', '<', '>', ':'
    match = re.search(r"(?<![=!<>:])=(?![=])", line)
    if not match:
        return None
    eq_idx = match.start()
    start = sum(len(chunk) for chunk in lines[:line_no - 1]) + eq_idx
    end = start + 1
    proposed = source[:start] + "==" + source[end:]
    try:
        ast.parse(proposed)
    except (SyntaxError, ValueError):
        return None
    return _finding(
        "PY-SYNTAX-005", "Assignment in conditional statement",
        "A single '=' is an assignment operator; comparison in conditional header requires '=='.",
        "critical", "Syntax", line_no, 96,
        "Replace '=' with '==' in the conditional expression. Proposed code passes Python syntax parsing; verify behavior.",
        Edit(start, end, "=="),
    )


def collect_findings(source: str) -> tuple[list[Finding], bool]:
    """Report likely issues. Automated fixes are intentionally narrow and conservative."""
    findings: list[Finding] = []

    # Tokenize so comments and string literals containing PRINT(...) are not edited.
    tokens = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            tokens.append(token)
    except (tokenize.TokenError, IndentationError):
        pass  # Partial tokens remain useful when a syntax error exists.
    for index, token in enumerate(tokens):
        if token.type != tokenize.NAME or token.string not in ("PRINT", "pritn", "pirnt", "prnt", "prnit"):
            continue
        previous = tokens[index - 1] if index else None
        if previous and previous.type == tokenize.OP and previous.string == ".":
            continue  # Attribute calls such as obj.PRINT() are not builtins.
        next_token = tokens[index + 1] if index + 1 < len(tokens) else None
        if not next_token or next_token.type != tokenize.OP or next_token.string != "(":
            continue
        start = _offset(source, token.start[0], len(source.splitlines()[token.start[0] - 1][:token.start[1]].encode("utf-8")))
        findings.append(_finding(
            "PY-NAME-001", "Unrecognized print function",
            f"'{token.string}' is not the Python built-in print function.",
            "high", "Name error", token.start[0], 99, "Replace with lowercase print(...).",
            Edit(start, start + len(token.string), "print"),
        ))

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        delimiter_fix = _missing_closing_delimiters(source, exc)
        print_fix = _simple_print_literal_repair(source, exc) if delimiter_fix is None else None
        cond_fix = _assignment_in_condition_repair(source, exc) if (delimiter_fix is None and print_fix is None) else None
        if delimiter_fix is not None:
            findings.append(delimiter_fix)
        if print_fix is not None:
            findings.append(print_fix)
        if cond_fix is not None:
            findings.append(cond_fix)
        line_no = exc.lineno or 1
        err_line = (source.splitlines() + [""])[min(max(line_no - 1, 0), len(source.splitlines()))] if source.splitlines() else ""
        # A single-line, missing trailing colon can be fixed with high confidence.
        stripped = err_line.rstrip()
        head = stripped.lstrip()
        header = bool(re.match(r"^(?:async\s+def|def|class|if|elif|else|for|async\s+for|while|try|except|finally|with|async\s+with)\b", head))
        missing_colon = header and not stripped.endswith(":") and not stripped.endswith("\\") and not stripped.endswith(",") and not stripped.endswith("(") and "#" not in stripped
        looks_like_header = bool(re.match(r"^(?:async\s+def|def|class|if|elif|else|for|async\s+for|while|try|except|finally|with|async\s+with)\b", head))
        # When the interpreter reports a missing colon on a valid-looking header, propose a colon.
        if missing_colon and ("expected ':'" in (exc.msg or "") or "invalid syntax" in (exc.msg or "")):
            start = _offset(source, line_no, len(stripped))
            findings.append(_finding(
                "PY-SYNTAX-002", "Missing colon after block header",
                "This block header may need a ':' before its indented body.",
                "critical", "Syntax", line_no, 92, "Add ':' at the end of the block header.",
                Edit(start, start, ":"),
            ))
        if delimiter_fix is None and print_fix is None and cond_fix is None:
            findings.append(_finding(
                "PY-SYNTAX-001", "Python syntax error", exc.msg,
                "critical", "Syntax", line_no, 100,
                "Inspect the indicated line and nearby punctuation or indentation.", None,
            ))
        return _dedupe(findings), False

    # A user may intentionally define a callable named PRINT or pritn.
    # Never rewrite those names as though they were misspelled built-ins.
    defined_callables = set()
    for definition in ast.walk(tree):
        if isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined_callables.add(definition.name)
        elif isinstance(definition, ast.Name) and isinstance(definition.ctx, ast.Store):
            defined_callables.add(definition.id)
        elif isinstance(definition, (ast.Import, ast.ImportFrom)):
            defined_callables.update(alias.asname or alias.name.split('.')[0]
                                     for alias in definition.names if alias.name != '*')
    findings = [f for f in findings if not (
        f.rule == 'PY-NAME-001' and f.detail.split("'")[1] in defined_callables
    )]

    for probable in runtime_diagnostics.static_name_typos(source, tree):
        findings.append(_runtime_finding(probable))

    for node in ast.walk(tree):
        # Intentionally only correct matching sum(xs) / (len(xs) + 1): the classic mean off-by-one bug.
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            variable = _len_plus_one(node.right)
            if variable and _is_call(node.left, "sum", variable):
                start = _offset(source, node.right.lineno, node.right.col_offset)
                end = _offset(source, node.right.end_lineno, node.right.end_col_offset)
                findings.append(_finding(
                    "PY-LOGIC-101", "Incorrect average denominator",
                    "sum(values) divided by len(values) + 1 gives a smaller, incorrect average.",
                    "high", "Logic", node.lineno, 98,
                    f"Use len({variable}) instead of len({variable}) + 1.",
                    Edit(start, end, f"len({variable})"),
                ))

        # For loop iterating len(items)+1 when the body indexes the same list at loop index.
        if isinstance(node, (ast.For, ast.AsyncFor)) and isinstance(node.target, ast.Name) and isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range" and len(node.iter.args) == 1:
            variable = _len_plus_one(node.iter.args[0])
            if variable:
                uses_index = any(isinstance(child, ast.Subscript) and isinstance(child.value, ast.Name) and child.value.id == variable and isinstance(child.slice, ast.Name) and child.slice.id == node.target.id for stmt in node.body for child in ast.walk(stmt))
                if uses_index:
                    argument = node.iter.args[0]
                    start = _offset(source, argument.lineno, argument.col_offset)
                    end = _offset(source, argument.end_lineno, argument.end_col_offset)
                    findings.append(_finding(
                        "PY-LOGIC-102", "Potential list index overflow",
                        "range(len(items) + 1) includes an index beyond the end of the list.",
                        "high", "Boundary", node.lineno, 96,
                        f"Use range(len({variable})) in this loop.",
                        Edit(start, end, f"len({variable})"),
                    ))

        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and isinstance(node.right, ast.Constant) and node.right.value == 0:
            findings.append(_finding(
                "PY-RUNTIME-201", "Division by zero",
                "A literal zero divisor will raise ZeroDivisionError at runtime if evaluated.",
                "critical", "Runtime", node.lineno, 100,
                "Choose an appropriate nonzero divisor or add logic to handle this case. Not automatically changed.", None,
            ))

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in (*node.args.defaults, *[d for d in node.args.kw_defaults if d is not None]):
                if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    findings.append(_finding(
                        "PY-QUALITY-301", "Mutable default argument",
                        "A mutable default object is shared by function calls and can cause unexpected state.",
                        "medium", "Reliability", node.lineno, 94,
                        "Use None as the default and create a new list/dict/set inside the function. Review manually.", None,
                    ))
                    break

        if isinstance(node, ast.ExceptHandler) and node.type is None:
            findings.append(_finding(
                "PY-QUALITY-302", "Bare except catches everything",
                "This handler also catches KeyboardInterrupt and SystemExit.",
                "low", "Reliability", node.lineno, 95,
                "Catch the specific expected exception or Exception. Review manually.", None,
            ))

    return _dedupe(findings), True


def _runtime_finding(issue: runtime_diagnostics.RuntimeIssue) -> Finding:
    edit = Edit(issue.edit.start, issue.edit.end, issue.edit.replacement) if issue.edit else None
    return _finding(issue.rule, issue.title, issue.detail, issue.severity,
                    issue.category, issue.line, issue.confidence, issue.suggestion, edit)


def runtime_issues(source: str, stderr: str, exit_code: int | None) -> list[dict]:
    """Structured Docker findings; never treats a failed run as 'clean'."""
    return [_runtime_finding(issue).public()
            for issue in runtime_diagnostics.runtime_findings(source, stderr, exit_code)]


def _dedupe(findings: list[Finding]) -> list[Finding]:
    seen = set()
    result = []
    for issue in sorted(findings, key=lambda f: (f.line, f.rule)):
        key = (issue.rule, issue.line, issue.edit.start if issue.edit is not None else -1)
        if key not in seen:
            result.append(issue)
            seen.add(key)
    return result


def analyze(source: str) -> dict:
    start = perf_counter()
    findings, valid = collect_findings(source)
    counts = {severity: sum(f.severity == severity for f in findings) for severity in ("critical", "high", "medium", "low")}
    return {
        "issues": [f.public() for f in findings],
        "total_issues": len(findings),
        "fixable_issues": sum(f.edit is not None for f in findings),
        "severity_counts": counts,
        "syntax_valid": valid,
        "lines_scanned": len(source.splitlines()) or 1,
        "analysis_mode": "deterministic_ast_and_rules",
        "duration_ms": round((perf_counter() - start) * 1000, 2),
    }


def repair(source: str, runtime_stderr: str = "", runtime_exit_code: int | None = None) -> dict:
    start = perf_counter()
    findings, _ = collect_findings(source)
    observed = runtime_diagnostics.runtime_findings(source, runtime_stderr, runtime_exit_code)
    findings.extend(_runtime_finding(issue) for issue in observed)
    candidates = [f for f in findings if f.edit is not None]
    # Only apply non-overlapping edits; no blanket regex rewriting or host-side execution.
    accepted: list[Finding] = []
    occupied: list[tuple[int, int]] = []
    for f in sorted(candidates, key=lambda item: (-(item.confidence), item.edit.start)):
        e = f.edit
        if any(not (e.end <= start or e.start >= end) for start, end in occupied):
            continue
        accepted.append(f)
        occupied.append((e.start, e.end))
    modified = source
    for f in sorted(accepted, key=lambda item: item.edit.start, reverse=True):
        e = f.edit
        modified = modified[:e.start] + e.replacement + modified[e.end:]

    try:
        ast.parse(modified)
        valid = True
        validity_message = "Python syntax validation passed. Logical correctness still requires tests."
    except SyntaxError as exc:
        valid = False
        validity_message = f"Syntax still needs attention near line {exc.lineno}: {exc.msg}."

    if not valid and modified != source:
        # A single syntactic change may expose a second syntax error. A proposed
        # patch must be parseable as a whole, otherwise do not present it as a fix.
        modified = source
        accepted = []
        validity_message = "No complete syntax-valid automatic patch was found. Review all syntax errors manually."

    diff = "\n".join(unified_diff(source.splitlines(), modified.splitlines(),
                                  fromfile="before.py", tofile="after.py", lineterm=""))
    return {
        "original_code": source,
        "repaired_code": modified,
        "changed": modified != source,
        "applied_fixes": [f.public() for f in sorted(accepted, key=lambda item: item.line)],
        "remaining_issues": analyze(modified)["issues"],
        "syntax_valid": valid,
        "validation_message": validity_message,
        "unified_diff": diff,
        "duration_ms": round((perf_counter() - start) * 1000, 2),
        "repair_mode": "deterministic_rules_with_runtime_traceback" if observed else "deterministic_rules",
        "runtime_issues": [_runtime_finding(issue).public() for issue in observed],
    }
