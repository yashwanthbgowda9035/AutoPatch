"""Conservative, non-executing Python name-typo analysis and traceback hints.

Never executes, imports or evaluates submitted source. A typo is only offered
when an unambiguous, previously-bound name exists in the *same lexical scope*.
Tracebacks are advisory evidence, not a proof of logical correctness.
"""
from __future__ import annotations

import ast
import builtins
from dataclasses import dataclass
from difflib import SequenceMatcher
import re


@dataclass(frozen=True)
class NameEdit:
    line: int
    start: int
    end: int
    original: str
    replacement: str


@dataclass(frozen=True)
class RuntimeIssue:
    rule: str
    title: str
    detail: str
    severity: str
    category: str
    line: int
    confidence: int
    suggestion: str
    edit: NameEdit | None = None


# Only the fixed filename used by the Docker runner is accepted as a frame.
_FRAME = re.compile(r'^\s*File ["\']/workspace/main\.py["\'], line (\d+)\b', re.M)
_NAME_ERROR = re.compile(
    r'^NameError: name [\'\"](?P<name>[A-Za-z_]\w*)[\'\"] is not defined'
    r'(?:\. Did you mean: [\'\"](?P<hint>[A-Za-z_]\w*)[\'\"]\?)?', re.M,
)
_ERROR = re.compile(r'^([A-Za-z_][\w.]*(?:Error|Exception)):\s*(.*)$', re.M)
_BUILTINS = frozenset(dir(builtins))
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_NESTED_SCOPES = _SCOPES + (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _offset(source: str, line: int, byte_col: int) -> int:
    lines = source.splitlines(keepends=True)
    if line < 1 or line > len(lines):
        raise ValueError('Invalid source location')
    prefix = lines[line - 1].encode('utf-8')[:byte_col].decode('utf-8', errors='ignore')
    return sum(map(len, lines[:line - 1])) + len(prefix)


def _scope(tree: ast.AST, line: int) -> ast.AST:
    """Choose the narrowest definition body containing this line."""
    found: ast.AST = tree
    size = 10**9
    for node in ast.walk(tree):
        if isinstance(node, _NESTED_SCOPES) and node.lineno <= line <= (node.end_lineno or node.lineno):
            span = (node.end_lineno or node.lineno) - node.lineno
            if span < size:
                found, size = node, span
    return found


def _targets(target: ast.AST) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        return set().union(*(_targets(part) for part in target.elts)) if target.elts else set()
    return set()


def _bindings(scope: ast.AST, line: int) -> set[str]:
    names: set[str] = set()
    if isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        args = scope.args
        names.update(a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs))
        if args.vararg:
            names.add(args.vararg.arg)
        if args.kwarg:
            names.add(args.kwarg.arg)
    # Only preceding direct statements. Do not assume that conditional branches,
    # loops, try blocks or dynamically executed statements have run.
    for stmt in getattr(scope, 'body', ()):
        if stmt.lineno >= line:
            continue
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                names.update(_targets(target))
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            names.update(_targets(stmt.target))
        elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
            for alias in stmt.names:
                if alias.name == '*':
                    continue
                names.add(alias.asname or alias.name.split('.')[0])
        elif isinstance(stmt, _SCOPES):
            names.add(stmt.name)
    return names


def _unsafe_dynamic_namespace(tree: ast.AST) -> bool:
    # Dynamic bindings are intentionally not guessed about by static rules.
    return any(
        isinstance(node, ast.ImportFrom) and any(a.name == '*' for a in node.names)
        or isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id in {'exec', 'eval', 'globals', 'locals', 'vars'}
        for node in ast.walk(tree)
    )


def _candidate(bad: str, bound: set[str], hint: str | None) -> str | None:
    if len(bad) < 4 or bad in bound or bad in _BUILTINS:
        return None
    options = []
    for name in bound:
        if name.startswith('_') or abs(len(name) - len(bad)) > 2:
            continue
        similarity = SequenceMatcher(None, bad, name).ratio()
        if similarity >= .82:
            options.append((similarity, name))
    options.sort(reverse=True)
    if not options:
        return None
    # The runner's Did-you-mean hint must also be a previously bound name.
    if hint is not None and options[0][1] != hint:
        return None
    if len(options) > 1 and options[0][0] - options[1][0] < .09:
        return None
    return options[0][1]


def name_edit(source: str, line: int, bad: str, hint: str | None = None,
              *, static: bool = False, tree: ast.AST | None = None) -> NameEdit | None:
    try:
        tree = tree or ast.parse(source)
        if _unsafe_dynamic_namespace(tree):
            return None
        scope = _scope(tree, line)
        # Without an observed runtime failure, limit heuristic fixes to module
        # scope to avoid incorrectly replacing legitimate globals in functions.
        if static and not isinstance(scope, ast.Module):
            return None
        replacement = _candidate(bad, _bindings(scope, line), hint)
        if not replacement:
            return None
        matching = [node for node in ast.walk(scope) if isinstance(node, ast.Name)
                    and isinstance(node.ctx, ast.Load) and node.id == bad and node.lineno == line
                    and _scope(tree, node.lineno) is scope]
        if len(matching) != 1:
            return None
        node = matching[0]
        start = _offset(source, node.lineno, node.col_offset)
        end = _offset(source, node.end_lineno, node.end_col_offset)
        if source[start:end] != bad:
            return None
        proposed = source[:start] + replacement + source[end:]
        ast.parse(proposed)
        return NameEdit(line, start, end, bad, replacement)
    except (SyntaxError, ValueError, IndexError, UnicodeError):
        return None


def static_name_typos(source: str, tree: ast.AST) -> list[RuntimeIssue]:
    """Fast top-level-only typo hints; never treats heuristics as proof.

    Visit the AST once and maintain a running set of previously bound names.
    Avoid repeatedly scanning the entire tree for every identifier in a large
    program; source may contain hundreds of valid names.
    """
    if _unsafe_dynamic_namespace(tree):
        return []

    class ModuleLoads(ast.NodeVisitor):
        def __init__(self):
            self.by_key: dict[tuple[int, str], list[ast.Name]] = {}

        def visit_Name(self, node: ast.Name):
            if isinstance(node.ctx, ast.Load):
                self.by_key.setdefault((node.lineno, node.id), []).append(node)

        # These constructs have their own lexical bindings. Do not guess.
        def visit_FunctionDef(self, node): pass
        def visit_AsyncFunctionDef(self, node): pass
        def visit_ClassDef(self, node): pass
        def visit_Lambda(self, node): pass
        def visit_ListComp(self, node): pass
        def visit_SetComp(self, node): pass
        def visit_DictComp(self, node): pass
        def visit_GeneratorExp(self, node): pass

    visitor = ModuleLoads()
    visitor.visit(tree)
    statements = tree.body
    position = 0
    bound: set[str] = set()
    issues: list[RuntimeIssue] = []
    for (line, bad), nodes in sorted(visitor.by_key.items()):
        while position < len(statements) and statements[position].lineno < line:
            stmt = statements[position]
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    bound.update(_targets(target))
            elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
                bound.update(_targets(stmt.target))
            elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
                bound.update(alias.asname or alias.name.split('.')[0]
                             for alias in stmt.names if alias.name != '*')
            elif isinstance(stmt, _SCOPES):
                bound.add(stmt.name)
            position += 1
        if len(nodes) != 1:
            continue
        replacement = _candidate(bad, bound, None)
        if not replacement:
            continue
        node = nodes[0]
        try:
            start = _offset(source, node.lineno, node.col_offset)
            end = _offset(source, node.end_lineno, node.end_col_offset)
            if source[start:end] != bad:
                continue
            ast.parse(source[:start] + replacement + source[end:])
        except (SyntaxError, ValueError, IndexError, UnicodeError):
            continue
        edit = NameEdit(line, start, end, bad, replacement)
        issues.append(RuntimeIssue(
            'PY-NAME-002', 'Possible undefined variable typo',
            f"'{bad}' may be a typo for the earlier variable '{replacement}'.",
            'high', 'Name error', line, 88,
            f"Consider replacing '{bad}' with '{replacement}'. Run the code and tests to confirm.", edit,
        ))
    return issues


def runtime_findings(source: str, stderr: str, exit_code: int | None) -> list[RuntimeIssue]:
    """Translate an actual failed Docker traceback into an actionable finding."""
    if exit_code is None or exit_code == 0 or not stderr:
        return []
    frames = [int(n) for n in _FRAME.findall(stderr[-12000:])]
    line = frames[-1] if frames else 0
    errors = list(_ERROR.finditer(stderr[-12000:]))
    last_error = errors[-1] if errors else None
    name_errors = list(_NAME_ERROR.finditer(stderr[-12000:]))
    if line and name_errors and last_error and last_error.group(1) == 'NameError':
        match = name_errors[-1]
        if match.start() == last_error.start():
            bad, hint = match.group('name'), match.group('hint')
            edit = name_edit(source, line, bad, hint)
            if edit:
                return [RuntimeIssue(
                    'PY-RUNTIME-401', 'Runtime NameError: undefined variable',
                    f"Docker execution failed on line {line}: '{bad}' is undefined. "
                    f"The previously defined name '{edit.replacement}' is a likely match.",
                    'critical', 'Runtime', line, 97,
                    f"Replace '{bad}' with '{edit.replacement}', then rerun Docker and tests. This is not yet a verified fix.", edit,
                )]
            return [RuntimeIssue(
                'PY-RUNTIME-400', 'Runtime NameError: undefined variable',
                f"Docker execution failed on line {line}: '{bad}' is undefined. No unambiguous safe replacement was found.",
                'critical', 'Runtime', line, 100, 'Review variable names, scope and assignment order.', None,
            )]
    error_name = last_error.group(1) if last_error else 'Nonzero exit code'
    detail = (last_error.group(2) if last_error else 'Program exited with an error.')[:180]
    return [RuntimeIssue(
        'PY-RUNTIME-499', 'Docker execution failed',
        f'{error_name}: {detail}' if detail else error_name,
        'critical', 'Runtime', line, 100,
        'Inspect the execution traceback. A syntax-valid program can still fail at runtime.', None,
    )]
