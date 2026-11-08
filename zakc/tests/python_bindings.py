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


    def test_compile_error_exposes_structured_diagnostics(self) -> None:
        for function in (zakc.zak_check, zakc.zak_transpile):
            with self.subTest(function=function.__name__):
                with self.assertRaises(zakc.ZakCompileError) as caught:
                    function("out(first);\nout(second)")
                self.assertIsInstance(caught.exception, ValueError)
                errors = caught.exception.errors
                self.assertEqual(
                    [(e.code, e.line, e.col, e.end_line, e.end_col) for e in errors],
                    [("UNDEFINED_NAME", 1, 5, 1, 10), ("UNDEFINED_NAME", 2, 5, 2, 11)],
                )
                self.assertTrue(all(isinstance(e, zakc.CompilerError) for e in errors))
                self.assertIn("first", errors[0].message)
                # Rust call-site traces stay in str(exception), not in model-facing messages.
                self.assertNotIn(".rs:", errors[0].message)

    def test_syntax_error_has_one_based_location(self) -> None:
        with self.assertRaises(zakc.ZakCompileError) as caught:
            zakc.zak_transpile("x:=1;\nout(")
        error, = caught.exception.errors
        self.assertEqual((error.code, error.line, error.col), ("SYNTAX_ERROR", 2, 5))

    def test_concurrent_threads_compile_identically(self) -> None:
        import threading

        source = "".join(f"@f{i}(a:[I])I{{t:=0;~x:a{{t+=x}}^t}}" for i in range(400))
        results: list[str] = []
        threads = [threading.Thread(target=lambda: results.append(zakc.zak_transpile(source).source))
                   for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(set(results)), 1)
        self.assertEqual(len(results), 4)


if __name__ == "__main__":
    unittest.main()
