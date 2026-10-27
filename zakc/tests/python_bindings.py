"""Run against the built extension with its directory on PYTHONPATH."""

import contextlib
import io
import unittest

import zakc


class PythonBindingsTests(unittest.TestCase):
    def test_check_returns_a_checked_program(self) -> None:
        checked = zakc.zak_check("x:=7/2;out(x)")
        self.assertIsInstance(checked, zakc.CheckedProgram)

    def test_transpile_returns_executable_python_with_zak_division(self) -> None:
        generated = zakc.zak_transpile("out(7/2);out(7.0/2.0)")
        self.assertIsInstance(generated, zakc.TranspiledProgram)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(generated.source, {})
        self.assertEqual(output.getvalue(), "3\n3.5\n")

    def test_both_functions_preserve_all_semantic_diagnostics(self) -> None:
        for function in (zakc.zak_check, zakc.zak_transpile):
            with self.subTest(function=function.__name__):
                with self.assertRaises(ValueError) as caught:
                    function("out(first);out(second)")
                message = str(caught.exception)
                self.assertEqual(message.count("UNDEFINED_NAME"), 2)
                self.assertIn("first", message)
                self.assertIn("second", message)
                self.assertIn("1:5", message)
                self.assertIn("1:16", message)

    def test_both_functions_report_syntax_errors(self) -> None:
        for function in (zakc.zak_check, zakc.zak_transpile):
            with self.subTest(function=function.__name__):
                with self.assertRaises(ValueError) as caught:
                    function("x:=1;\nout(")
                message = str(caught.exception)
                self.assertIn("SYNTAX_ERROR", message)
                self.assertIn("2:5", message)


if __name__ == "__main__":
    unittest.main()
