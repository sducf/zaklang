"""Tests for check_references.py. Run from the repository root: python3 -m unittest discover -s zakbench/tasks"""

import json
from pathlib import Path
import tempfile
import unittest

from check_references import check_task

TASK = {
    'id': 'double', 'title': 'Double', 'category': 'algorithms', 'prompt': 'Return twice n.',
    'functionName': 'solve', 'inputs': [{'name': 'n', 'type': 'integer'}], 'outputType': 'integer',
}
# The expected values are distinctive so a test can prove they never reach the report.
CASES = [{'inputs': [n], 'expected': n * 2} for n in (1001, 7007, 4321, 98765, 13579)]
PYTHON = 'def solve(n):\n    return n * 2\n'
ZAK = '@solve(n:I)I{^n*2}\n'


class CheckTaskTest(unittest.TestCase):
    def check(self, zak=ZAK, python=PYTHON):
        with tempfile.TemporaryDirectory() as workdir:
            folder = Path(workdir) / 'double'
            folder.mkdir()
            (folder / 'task.json').write_text(json.dumps(TASK), encoding='utf-8')
            (folder / 'hidden_tests.json').write_text(json.dumps(CASES), encoding='utf-8')
            (folder / 'reference.py').write_text(python, encoding='utf-8')
            if zak is not None:
                (folder / 'reference.zak').write_text(zak, encoding='utf-8')
            return check_task(folder)

    def assertNoHiddenValues(self, line):
        for case in CASES:
            self.assertNotIn(str(case['expected']), line)

    def test_pass(self):
        self.assertEqual(self.check(), (True, 'double: PASS py 5/5, zak 5/5'))

    def test_zak_compile_error(self):
        ok, line = self.check(zak='@solve(n:I)I{^n*}\n')
        self.assertFalse(ok)
        self.assertIn('zak 0/5', line)
        self.assertRegex(line, r'reference\.zak does not compile: \d+:\d+: \S+: ')

    def test_zak_type_error(self):
        ok, line = self.check(zak='@solve(n:I)I{^"x"}\n')
        self.assertFalse(ok)
        self.assertIn('reference.zak does not compile', line)

    def test_zak_wrong_answer(self):
        ok, line = self.check(zak='@solve(n:I)I{?n==7007{^0}^n*2}\n')
        self.assertFalse(ok)
        self.assertIn('py 5/5, zak 4/5 reference.zak failed case 2', line)
        self.assertNoHiddenValues(line)

    def test_zak_wrong_function_name(self):
        ok, line = self.check(zak='@other(n:I)I{^n*2}\n')
        self.assertFalse(ok)
        self.assertIn('reference.zak crashed or does not define the function', line)

    def test_missing_zak_reference(self):
        ok, line = self.check(zak=None)
        self.assertEqual((ok, line), (False, 'double: FAIL reference.zak is missing'))

    def test_python_failure_still_reported(self):
        ok, line = self.check(python='def solve(n):\n    return n\n')
        self.assertFalse(ok)
        self.assertIn('py 0/5, zak 5/5 reference.py failed case 1, 2, 3, 4, 5', line)
        self.assertNoHiddenValues(line)


if __name__ == '__main__':
    unittest.main()
