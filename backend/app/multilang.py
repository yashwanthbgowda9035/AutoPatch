"""Conservative static heuristics for C, C++, Java and Excel formulas.

No C/C++/Java compilation or source execution; do not call heuristic parsing a compiler.
"""
from __future__ import annotations

import re
from difflib import unified_diff
from time import perf_counter

LANGUAGES = {'c': '.c', 'cpp': '.cpp', 'java': '.java', 'excel': '.formula'}

EXCEL_FUNCS = (
    'SUM', 'AVERAGE', 'COUNT', 'COUNTA', 'MAX', 'MIN', 'IF', 'IFS',
    'VLOOKUP', 'HLOOKUP', 'XLOOKUP', 'INDEX', 'MATCH', 'CONCAT',
    'CONCATENATE', 'TRIM', 'ROUND', 'ROUNDUP', 'ROUNDDOWN', 'MOD',
    'AND', 'OR', 'NOT', 'LEFT', 'RIGHT', 'MID', 'LEN', 'TEXT'
)


def _issue(rule, title, detail, severity, line, suggestion, fix=False):
    return {'id': f'{rule}-L{line}', 'rule': rule, 'title': title, 'detail': detail,
            'severity': severity, 'category': 'Static heuristic', 'line': line,
            'confidence': 75 if fix else 65, 'suggestion': suggestion,
            'fix_available': fix}


def _mask_literals(source):
    """Keep code lengths and line numbers, blank comments and quoted literals."""
    state, i, out = 'code', 0, []
    while i < len(source):
        ch, nxt = source[i], source[i + 1] if i + 1 < len(source) else ''
        if state == 'code':
            if ch == '/' and nxt == '/':
                out.extend('  '); i += 2; state = 'line'; continue
            if ch == '/' and nxt == '*':
                out.extend('  '); i += 2; state = 'block'; continue
            if ch in ('"', "'"):
                out.append(' '); state = ch; i += 1; continue
            out.append(ch)
        elif state == 'line':
            if ch == '\n': out.append('\n'); state = 'code'
            else: out.append(' ')
        elif state == 'block':
            if ch == '*' and nxt == '/': out.extend('  '); i += 2; state = 'code'; continue
            out.append('\n' if ch == '\n' else ' ')
        else:
            if ch == '\\' and nxt:
                out.extend('  '); i += 2; continue
            if ch == state: state = 'code'
            out.append('\n' if ch == '\n' else ' ')
        i += 1
    return ''.join(out)


def _scan(source, language):
    findings = []
    if language == 'excel':
        for n, line in enumerate(source.splitlines(), 1):
            formula = line.strip()
            if not formula:
                continue
            if not formula.startswith('='):
                first_word = re.split(r'[\s(]', formula)[0].upper()
                fixable = first_word in EXCEL_FUNCS
                findings.append(_issue(
                    'XL-FORM-001', 'Formula should begin with =',
                    'This line is not prefixed with = for an Excel formula.',
                    'low', n, 'Prefix formulas with = when entering into Excel.',
                    fix=fixable
                ))
            if '#REF!' in formula.upper():
                findings.append(_issue('XL-REF-001', 'Broken cell reference', 'The formula contains #REF!, which indicates a deleted or invalid reference.', 'high', n, 'Restore the correct cell reference manually.'))
            if re.search(r'/\s*0(?:\.0+)?\s*(?:[),+\-*/]|$)', formula):
                findings.append(_issue('XL-DIV-001', 'Literal zero divisor', 'Formula divides by literal zero.', 'high', n, 'Confirm the intended denominator, then fix it.'))
            if re.search(r'\b(?:INDIRECT|OFFSET)\s*\(', formula, re.I):
                findings.append(_issue('XL-VOL-001', 'Potentially volatile function', 'INDIRECT/OFFSET may recalculate frequently or make references harder to audit.', 'low', n, 'Consider direct references when possible.'))
            if '[' in formula and ']' in formula:
                findings.append(_issue('XL-LINK-001', 'External workbook link', 'Formula appears to reference another workbook.', 'medium', n, 'Verify that the linked workbook exists and is trusted.'))
            # Check for unclosed parentheses in Excel formula
            open_count = formula.count('(')
            close_count = formula.count(')')
            if open_count > close_count:
                findings.append(_issue(
                    'XL-BRACE-001', 'Unclosed formula parenthesis',
                    f'Formula has {open_count} opening parentheses but only {close_count} closing parentheses.',
                    'high', n, f'Add {open_count - close_count} closing parentheses at the end of the formula.',
                    fix=True
                ))
        return findings

    masked = _mask_literals(source)
    line_for = lambda pos: masked.count('\n', 0, pos) + 1
    opening = {'(': ')', '{': '}', '[': ']'}
    closing = {v: k for k, v in opening.items()}
    stack = []
    for p, c in enumerate(masked):
        if c in opening: stack.append((c, p))
        elif c in closing:
            if stack and stack[-1][0] == closing[c]: stack.pop()
            else: findings.append(_issue('ML-BRACE-001', 'Unmatched closing delimiter', f'Unexpected {c!r}.', 'high', line_for(p), 'Inspect surrounding brackets/braces.'))
    for c, p in stack[:10]:
        findings.append(_issue('ML-BRACE-002', 'Unclosed delimiter', f'Unclosed {c!r}.', 'high', line_for(p), 'Check for a matching closing delimiter.'))
    patterns = {
        'c': [
            (r'\bPRINTF\s*\(', 'ML-C-PRINTF', 'Unrecognized PRINTF capitalization', 'The C standard function is printf, not PRINTF.', 'high', 'Use lowercase printf(...).'),
            (r'\bgets\s*\(', 'ML-C-GETS', 'Unsafe gets() call', 'gets() cannot limit input size.', 'high', 'Use fgets() with an explicit buffer size.'),
            (r'\bstrcpy\s*\(', 'ML-C-STRCPY', 'Unchecked string copy', 'strcpy() can overflow a destination buffer.', 'medium', 'Validate input sizes or use bounded operations.'),
            (r'\bvoid\s+main\s*\(\s*\)', 'ML-C-MAIN', 'Non-standard main signature', 'C standard requires int main(void) returning an integer status code.', 'medium', 'Change void main() to int main(void).'),
        ],
        'cpp': [
            (r'\bstd::Cout(?=\s*<<)', 'ML-CPP-COUT', 'Incorrect std::cout capitalization', 'C++ stream names are case-sensitive.', 'high', 'Use std::cout << ... .'),
            (r'\bstd::Cin(?=\s*>>)', 'ML-CPP-CIN', 'Incorrect std::cin capitalization', 'C++ stream names are case-sensitive.', 'high', 'Use std::cin >> ... .'),
            (r'\bstd::Endl\b', 'ML-CPP-ENDL', 'Incorrect std::endl capitalization', 'C++ stream manipulator is std::endl.', 'medium', 'Use std::endl.'),
            (r'\bgets\s*\(', 'ML-CPP-GETS', 'Unsafe gets() call', 'gets() cannot limit input size.', 'high', 'Use std::getline for strings.'),
            (r'\bstrcpy\s*\(', 'ML-CPP-STRCPY', 'Unchecked string copy', 'strcpy() may overflow its destination buffer.', 'medium', 'Prefer std::string or bounded copies.'),
        ],
        'java': [
            (r'\b(?:System\.out\.Println|System\.out\.printLn|system\.out\.println)\s*\(', 'ML-JAVA-PRINT', 'Incorrect println capitalization', 'Java is case-sensitive; standard call is System.out.println.', 'high', 'Use System.out.println(...).'),
            (r'\bpublic\s+static\s+void\s+Main\s*\(', 'ML-JAVA-MAIN', 'Incorrect Main method casing', 'Java entry point must be lowercase: public static void main(String[] args).', 'high', 'Change Main to main.'),
        ],
    }
    fixable_rules = {'ML-JAVA-PRINT', 'ML-JAVA-MAIN', 'ML-C-PRINTF', 'ML-C-MAIN', 'ML-CPP-COUT', 'ML-CPP-CIN', 'ML-CPP-ENDL'}
    for pattern, rule, title, detail, severity, suggestion in patterns.get(language, []):
        for match in re.finditer(pattern, masked):
            findings.append(_issue(rule, title, detail, severity, line_for(match.start()), suggestion, fix=rule in fixable_rules))
    return findings


def analyze(source, language):
    start = perf_counter()
    findings = _scan(source, language)
    return {'language': language, 'issues': findings, 'total_issues': len(findings),
            'fixable_issues': sum(f.get('fix_available', False) for f in findings),
            'severity_counts': {s: sum(f['severity'] == s for f in findings) for s in ('critical', 'high', 'medium', 'low')},
            'syntax_valid': None, 'lines_scanned': len(source.splitlines()) or 1,
            'analysis_mode': 'limited_static_heuristics_not_a_compiler',
            'duration_ms': round((perf_counter() - start) * 1000, 2),
            'note': 'Findings are heuristic. No compilation, execution or full syntax validation was performed.'}


def repair(source, language):
    result = analyze(source, language)
    fixed = source
    applied = []

    if language == 'excel':
        lines = []
        changed = False
        for line in source.splitlines():
            trimmed = line.strip()
            if not trimmed:
                lines.append(line)
                continue
            new_line = line
            # Prefix missing = if starts with known formula
            first_word = re.split(r'[\s(]', trimmed)[0].upper()
            if not trimmed.startswith('=') and first_word in EXCEL_FUNCS:
                indent = line[:len(line) - len(line.lstrip())]
                new_line = indent + '=' + trimmed
                changed = True
                applied.extend([f for f in result['issues'] if f['rule'] == 'XL-FORM-001'])
            # Balance unclosed parentheses
            open_count = new_line.count('(')
            close_count = new_line.count(')')
            if open_count > close_count:
                new_line = new_line + (')' * (open_count - close_count))
                changed = True
                applied.extend([f for f in result['issues'] if f['rule'] == 'XL-BRACE-001'])
            lines.append(new_line)
        if changed:
            fixed = '\n'.join(lines)
            if source.endswith('\n'):
                fixed += '\n'

    else:
        replacement_rules = {
            'java': [
                (r'\b(?:System\.out\.Println|System\.out\.printLn|system\.out\.println)(?=\s*\()', 'System.out.println', 'ML-JAVA-PRINT'),
                (r'\bpublic\s+static\s+void\s+Main(?=\s*\()', 'public static void main', 'ML-JAVA-MAIN'),
            ],
            'c': [
                (r'\bPRINTF(?=\s*\()', 'printf', 'ML-C-PRINTF'),
                (r'\bvoid\s+main\s*\(\s*\)', 'int main(void)', 'ML-C-MAIN'),
            ],
            'cpp': [
                (r'\bstd::Cout(?=\s*<<)', 'std::cout', 'ML-CPP-COUT'),
                (r'\bstd::Cin(?=\s*>>)', 'std::cin', 'ML-CPP-CIN'),
                (r'\bstd::Endl\b', 'std::endl', 'ML-CPP-ENDL'),
            ],
        }
        for pattern, replacement, rule in replacement_rules.get(language, []):
            mask = _mask_literals(fixed)
            matches = list(re.finditer(pattern, mask))
            if matches:
                for match in reversed(matches):
                    fixed = fixed[:match.start()] + replacement + fixed[match.end():]
                applied.extend([f for f in result['issues'] if f['rule'] == rule])

    diff = '\n'.join(unified_diff(source.splitlines(), fixed.splitlines(), fromfile='before', tofile='after', lineterm=''))
    return {'original_code': source, 'repaired_code': fixed, 'changed': fixed != source,
            'applied_fixes': applied, 'remaining_issues': analyze(fixed, language)['issues'],
            'syntax_valid': None, 'validation_message': 'Heuristic suggestion only; compile or inspect in the correct toolchain. AutoPatch has not compiled or executed this code.',
            'unified_diff': diff, 'duration_ms': result['duration_ms'], 'repair_mode': 'conservative_heuristic_patch' if applied else 'diagnostics_only',
            'ai_used': False, 'ai_message': 'AI repair is currently enabled for Python only.'}
