"""Tests for public benchmark task loading."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from api.controllers import benchmark
from api.routes import benchmark as benchmark_routes


class BenchmarkTaskControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.tasks_root = Path(self.temp_directory.name)

        (self.tasks_root / "array_sum").mkdir()
        (self.tasks_root / "array_sum" / "task.json").write_text(
            json.dumps(
                {
                    "id": "array_sum",
                    "title": "Array Sum",
                    "category": "arrays",
                    "prompt": "Return the sum.",
                    "functionName": "solve",
                    "inputs": [{"name": "nums", "type": "integer[]"}],
                    "outputType": "integer",
                }
            ),
            encoding="utf-8",
        )
        # Invalid hidden-test JSON proves task loading does not open this file.
        (self.tasks_root / "array_sum" / "hidden_tests.json").write_text(
            "{not json",
            encoding="utf-8",
        )

        (self.tasks_root / "README.md").write_text("not a task", encoding="utf-8")

    def test_list_reads_public_task_metadata_only(self):
        with patch.object(benchmark, "TASKS_ROOT", self.tasks_root):
            tasks = benchmark.list_tasks_controller()

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].id, "array_sum")
        self.assertEqual(tasks[0].function_name, "solve")
        self.assertNotIn("hidden_tests", tasks[0].model_dump())

    def test_get_task_maps_fixture_field_names(self):
        with patch.object(benchmark, "TASKS_ROOT", self.tasks_root):
            task = benchmark.get_task_controller("array_sum")

        self.assertEqual(task.function_name, "solve")
        self.assertEqual(task.output_type, "integer")
        self.assertEqual(task.inputs[0].name, "nums")

    def test_unknown_task_is_not_found(self):
        with patch.object(benchmark, "TASKS_ROOT", self.tasks_root):
            with self.assertRaises(HTTPException) as raised:
                benchmark.get_task_controller("missing")

        self.assertEqual(raised.exception.status_code, 404)

    def test_task_routes_delegate_to_controllers(self):
        task = benchmark.get_task_controller("array_sum")
        with patch.object(
            benchmark_routes,
            "list_tasks_controller",
            return_value=[task],
        ) as list_controller, patch.object(
            benchmark_routes,
            "get_task_controller",
            return_value=task,
        ) as get_controller:
            self.assertEqual(benchmark_routes.list_tasks(), [task])
            self.assertEqual(benchmark_routes.get_task("array_sum"), task)

        list_controller.assert_called_once_with()
        get_controller.assert_called_once_with("array_sum")


if __name__ == "__main__":
    unittest.main()
