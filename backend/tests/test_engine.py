"""Deterministic engine regression tests. Never run untrusted user source."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engine import analyze, repair
from app.samples import SAMPLES


def sample(item_id: str) -> dict:
    return next(s for s in SAMPLES if s["id"] == item_id)


def test_average_is_fixed_and_code_compiles():
    result = repair(sample("average")["code"])
    assert result["changed"]
    assert result["syntax_valid"]
    assert len(result["applied_fixes"]) == 1
    ast.parse(result["repaired_code"])
    assert "len(marks) + 1" not in result["repaired_code"]


def test_index_boundary_is_fixed():
    result = repair(sample("index")["code"])
    assert result["changed"]
    assert "range(len(numbers))" in result["repaired_code"]
    assert result["syntax_valid"]


def test_print_misspelling_is_fixed():
    result = repair(sample("name")["code"])
    assert "print(greet(" in result["repaired_code"]
    assert "PRINT(greet(" not in result["repaired_code"]


def test_missing_colon_is_fixed():
    result = repair(sample("syntax")["code"])
    assert "def square(number):" in result["repaired_code"]
    assert result["syntax_valid"]


def test_no_guess_for_zero_divisor():
    result = repair(sample("safety")["code"])
    assert not result["changed"]
    assert any(x["rule"] == "PY-RUNTIME-201" for x in result["remaining_issues"])


def test_do_not_rewrite_comments_or_strings():
    snippet = 'message = "PRINT(x)"\n# pritn(23)\n'
    result = repair(snippet)
    assert not result["changed"]
    assert analyze(snippet)["total_issues"] == 0


def test_do_not_rewrite_method_print():
    snippet = 'thing.PRINT("hello")\n'
    assert not repair(snippet)["changed"]


def test_do_not_trigger_untrusted_execution():
    snippet = 'raise RuntimeError("If executed, this test would fail")\n'
    assert analyze(snippet)["syntax_valid"]
    assert not repair(snippet)["changed"]


def test_unicode_columns_are_handled():
    source = 'x="🙂"; answer = sum(nums) / (len(nums) + 1)\n'
    result = repair(source)
    assert 'answer = sum(nums) / (len(nums))' in result["repaired_code"]
    assert result["syntax_valid"]


def test_style_and_syntax_issues_reported():
    source = 'def add(value, values=[]):\n    values.append(value)\n    return values\n'
    issues = analyze(source)["issues"]
    assert any(f["rule"] == "PY-QUALITY-301" and not f["fix_available"] for f in issues)


def test_empty_and_valid_file():
    result = analyze('pass\n')
    assert result["total_issues"] == 0
    assert result["syntax_valid"]


def test_diff_generated_and_reviewable():
    result = repair(sample("average")["code"])
    assert "--- before.py" in result["unified_diff"]
    assert "+++ after.py" in result["unified_diff"]


def test_analysis_does_not_mutate_source():
    original = sample("average")["code"]
    assert repair(original)["original_code"] == original


def test_two_print_typos_on_one_line():
    source = 'PRINT(1); PRINT(2)\n'
    fixed = repair(source)
    assert fixed["changed"]
    assert fixed["repaired_code"] == 'print(1); print(2)\n'
    assert len(fixed["applied_fixes"]) == 2


def test_missing_close_parenthesis_is_repaired():
    result = repair('print(2*5')
    assert result['changed'] and result['syntax_valid']
    assert result['repaired_code'] == 'print(2*5)'
    assert any(issue['rule'] == 'PY-SYNTAX-003' for issue in result['applied_fixes'])

def test_missing_close_parenthesis_before_trailing_comment():
    result = repair('print(2*5  # multiplication\n')
    assert result['repaired_code'] == 'print(2*5)  # multiplication\n'
    assert result['syntax_valid']

def test_nested_unclosed_delimiters():
    result = repair('print(sum([1, 2, 3')
    assert result['changed'] and result['syntax_valid']
    assert result['repaired_code'] == 'print(sum([1, 2, 3]))'

def test_no_unsafe_guess_for_unterminated_string():
    source = 'print("hello)'
    assert not repair(source)['changed']

def test_no_unsafe_guess_for_incomplete_expression():
    source = 'print(2 *'
    assert not repair(source)['changed']

def test_no_unsafe_guess_for_mismatched_delimiters():
    source = 'print([1, 2)'
    assert not repair(source)['changed']

def test_missing_delimiter_in_sample():
    sample_code = sample('paren')['code']
    result = repair(sample_code)
    assert result['syntax_valid']
    assert result['repaired_code'].startswith('print(2*5)')
