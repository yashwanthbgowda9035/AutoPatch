"""Conservative, explainable source language detection with filename hints.

Source syntax is the primary signal for pasted code; uploads add a filename hint.
An ambiguous snippet defaults to Python and is explicitly flagged tentative.
"""
from __future__ import annotations
import re

LANGUAGES = ("python", "c", "cpp", "java", "excel")
EXTENSIONS = {".py": "python", ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".java": "java", ".formula": "excel", ".xlsx": "excel"}


def detect(source: str, filename: str = "untitled") -> dict:
    text = source.strip()
    scores = {name: 0 for name in LANGUAGES}
    reasons = {name: [] for name in LANGUAGES}
    def boost(language: str, points: int, why: str):
        scores[language] += points
        reasons[language].append(why)
    if re.search(r"(?m)^\s*=\s*(?:[A-Z]{1,3}\d+|[A-Z][A-Z0-9_.]*\s*\(|#REF!|[+\-]?\d)", text, re.I):
        boost("excel", 14, "Excel formula beginning with =")
    if text and all(not line.strip() or line.lstrip().startswith('=') for line in text.splitlines()):
        boost("excel", 10, "Each nonblank line is a formula")
    if re.search(r"#REF!|#DIV/0!|#VALUE!", text, re.I):
        boost("excel", 9, "Excel error marker")
    if re.search(r"(?m)^\s*#\s*include\s*[<\"]", text):
        boost("c", 8, "C-family include directive")
        boost("cpp", 8, "C-family include directive")
    if re.search(r"\b(?:std::|cout|cin|namespace\s+std|template\s*<|#include\s*<iostream>)", text):
        boost("cpp", 15, "C++ stream or namespace syntax")
    if re.search(r"\b(?:printf|PRINTF|scanf|gets|fgets)\s*\(", text):
        boost("c", 5, "C-style standard library call")
    if re.search(r"\b(?:int|void)\s+main\s*\(", text):
        boost("c", 5, "C-family main function")
        boost("cpp", 4, "C-family main function")
    if re.search(r"\b(?:System\.out\.|public\s+(?:static\s+)?class\s+|package\s+[\w.]+\s*;|public\s+static\s+void\s+main)", text):
        boost("java", 16, "Java class or System.out syntax")
    if re.search(r"(?m)^\s*(?:def\s+\w+\s*\(|async\s+def\s+|from\s+\w+\s+import\s+|import\s+\w+|class\s+\w+\s*(?:\(|:))", text):
        boost("python", 14, "Python declaration or import")
    if re.search(r"(?m)^\s*(?:for|if|elif|while|try|except|else)\b[^;{}\n]*:\s*(?:#.*)?$", text):
        boost("python", 8, "Python indented control flow")
    if re.search(r"\b(?:print|PRINT|len|range|self|None|True|False)\s*\(", text):
        boost("python", 6, "Python built-in call")
    if re.search(r"(?m)^\s*print\s*\(", text):
        boost("python", 5, "Python print statement")
    # A real extension strengthens an already detected language, but does not override
    # strong contradictory syntax; 'main.py' is not treated as an implied filename.
    suffix = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    hint = EXTENSIONS.get(suffix)
    if hint and filename.lower() not in ('main.py','untitled.py','code.py'):
        boost(hint, 6, f"Uploaded filename extension {suffix}")
    ordered = sorted(LANGUAGES, key=lambda item: scores[item], reverse=True)
    leader, second = ordered[:2]
    if scores[leader] == 0:
        leader = hint or "python"
        confidence = 0.25
        reason = "No decisive language markers; tentative fallback" if not hint else f"Filename extension {suffix} only"
    else:
        margin = scores[leader] - scores[second]
        confidence = min(0.99, max(0.43, 0.50 + margin * 0.035 + min(scores[leader], 20) * 0.012))
        reason = "; ".join(dict.fromkeys(reasons[leader]))
    return {"language": leader, "confidence": round(confidence, 2), "reason": reason,
            "tentative": confidence < 0.66, "method": "source_and_filename_heuristics"}
