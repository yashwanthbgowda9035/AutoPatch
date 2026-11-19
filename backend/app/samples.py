"""Reproducible showcase samples: each snippet is editable in the frontend."""
SAMPLES = [
    {
        "id": "average",
        "title": "Average calculation",
        "label": "Logic bug",
        "description": "Denominator off-by-one produces 52.5 instead of 70.",
        "code": "def calculate_average(marks):\n    return sum(marks) / (len(marks) + 1)\n\nprint(calculate_average([60, 70, 80]))\n",
        "tests": "import unittest\nfrom main import calculate_average\n\nclass TestAverage(unittest.TestCase):\n    def test_average(self):\n        self.assertEqual(calculate_average([60, 70, 80]), 70.0)\n\n    def test_single_mark(self):\n        self.assertEqual(calculate_average([90]), 90.0)\n",
    },
    {
        "id": "index",
        "title": "List index overflow",
        "label": "Boundary bug",
        "description": "A loop visits index len(items), which is out of bounds.",
        "code": "def total_numbers(numbers):\n    total = 0\n    for i in range(len(numbers) + 1):\n        total += numbers[i]\n    return total\n\nprint(total_numbers([10, 20, 30]))\n",
        "tests": "import unittest\nfrom main import total_numbers\n\nclass TestTotals(unittest.TestCase):\n    def test_normal(self):\n        self.assertEqual(total_numbers([10, 20, 30]), 60)\n\n    def test_empty(self):\n        self.assertEqual(total_numbers([]), 0)\n",
    },
    {
        "id": "name",
        "title": "Misnamed print",
        "label": "Name error",
        "description": "Python identifiers are case-sensitive.",
        "code": "def greet(person):\n    return f\"Hello, {person}!\"\n\nPRINT(greet(\"Judge\"))\n",
        "tests": "import unittest\nfrom main import greet\n\nclass TestGreeting(unittest.TestCase):\n    def test_hello(self):\n        self.assertEqual(greet(\"Judge\"), \"Hello, Judge!\")\n",
    },
    {
        "id": "syntax",
        "title": "Missing colon",
        "label": "Syntax bug",
        "description": "A missing colon prevents the function from compiling.",
        "code": "def square(number)\n    return number * number\n\nprint(square(5))\n",
        "tests": "import unittest\nfrom main import square\n\nclass TestSquare(unittest.TestCase):\n    def test_value(self):\n        self.assertEqual(square(5), 25)\n",
    },
    {
        "id": "safety",
        "title": "Zero divisor",
        "label": "Runtime bug",
        "description": "This needs a human decision, so AutoPatch diagnoses but does not guess a replacement.",
        "code": "def compute_ratio(total):\n    return total / 0\n\nprint(compute_ratio(20))\n",
        "tests": "import unittest\nfrom main import compute_ratio\n\nclass TestRatio(unittest.TestCase):\n    def test_ratio_is_positive(self):\n        self.assertGreater(compute_ratio(20), 0)\n",
    },
]

SAMPLES += [
    {"id":"c-unsafe", "language":"c", "filename":"demo.c", "title":"C unsafe input", "label":"Static safety check", "description":"Flag unsafe gets() without executing it.",
     "code":"#include <stdio.h>\nint main(void) {\n    char name[20];\n    gets(name);\n    printf(\"Hello\\n\");\n    return 0;\n}\n", "tests":""},
    {"id":"cpp-buffer", "language":"cpp", "filename":"demo.cpp", "title":"C++ unchecked copy", "label":"Static safety check", "description":"Highlight possible strcpy buffer risks.",
     "code":"#include <cstring>\nint main() {\n    char dest[5];\n    strcpy(dest, \"This text is too long\");\n    return 0;\n}\n", "tests":""},
    {"id":"java-case", "language":"java", "filename":"Main.java", "title":"Java println typo", "label":"Heuristic repair", "description":"Suggest correct Java method casing.",
     "code":"public class Main {\n    public static void main(String[] args) {\n        System.out.Println(\"AutoPatch\");\n    }\n}\n", "tests":""},
    {"id":"excel-ref", "language":"excel", "filename":"Sheet1.formula", "title":"Excel broken formulas", "label":"Spreadsheet diagnostics", "description":"Spot broken references and literal divide-by-zero.",
     "code":"=SUM(A1:A5)\n=A1/0\n=SUM(#REF!:B5)\n=INDIRECT(\"B2\")\n", "tests":""},
]

SAMPLES += [
    {"id":"c-case", "language":"c", "filename":"demo.c", "title":"C printf capitalization", "label":"Heuristic repair", "description":"Suggest printf() capitalization.",
     "code":"#include <stdio.h>\nint main(void) {\n    PRINTF(\"AutoPatch\\n\");\n    return 0;\n}\n", "tests":""},
    {"id":"cpp-case", "language":"cpp", "filename":"main.cpp", "title":"C++ cout capitalization", "label":"Heuristic repair", "description":"Suggest std::cout capitalization.",
     "code":"#include <iostream>\nint main() {\n    std::Cout << \"AutoPatch\";\n    return 0;\n}\n", "tests":""},
]

# AutoPatch Pulse: simple, real missing-delimiter demo used by the new syntax lab.
SAMPLES.insert(4, {
    "id": "paren", "title": "Missing closing parenthesis", "label": "Syntax repair",
    "description": "print(2*5 is not valid Python; the engine proposes the missing closing parenthesis.",
    "code": "print(2*5\n",
    "tests": "import unittest\nimport io\nimport runpy\nfrom contextlib import redirect_stdout\n\nclass TestPrintedProduct(unittest.TestCase):\n    def test_actual_stdout_is_ten(self):\n        captured = io.StringIO()\n        with redirect_stdout(captured):\n            runpy.run_module('main', run_name='__main__')\n        self.assertEqual(captured.getvalue().strip(), '10')\n",
})
