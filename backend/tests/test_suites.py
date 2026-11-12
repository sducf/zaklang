"""Tests for persisted suite runs (zakbench --persist) and the GET /suites endpoints."""

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.controllers.auth import get_current_user_controller
from api.controllers.benchmark import create_queued_pair
from api.controllers.suites import SuiteStore
from api.routes import benchmark as benchmark_routes
from database.models import Attempt, Base, BenchmarkRun, Evaluation, SuiteRun, User
from main import app
from zakbench.__main__ import main as zakbench_main
from zakbench.runners import run, suite as suite_runner

TASKS = ['array_sum', 'palindrome', 'binary_search']


def attempt(number, outcome, prompt_tokens, completion_tokens):
    return {
        'number': number, 'prompt': [{'role': 'user', 'content': 'task prompt'}], 'completion': 'code',
        'code': 'code', 'prompt_tokens': prompt_tokens, 'completion_tokens': completion_tokens,
        'latency_ms': 10, 'finish_reason': 'stop', 'compile_ok': True, 'compile_errors': [],
        'transpiled_python': None, 'exec_outcome': outcome, 'tests_passed': 6 if outcome == 'pass' else 0,
        'tests_total': 6, 'failure_summary': None if outcome == 'pass' else 'Test 1 of 6 failed.',
    }


# (task, language) -> attempts. None means the run crashes the harness.
OUTCOMES = {
    ('array_sum', 'zak'): [attempt(1, 'pass', 100, 20)],
    ('array_sum', 'python'): [attempt(1, 'pass', 150, 30)],
    ('palindrome', 'zak'): [attempt(1, 'fail', 100, 20), attempt(2, 'pass', 160, 25)],
    ('palindrome', 'python'): [attempt(n, 'fail', 100 * n, 30) for n in (1, 2, 3)],
    ('binary_search', 'zak'): None,
    ('binary_search', 'python'): [attempt(1, 'pass', 120, 40)],
}


def fake_run_single(task_id, language, model_id, spec_version, prompt_version, seed, max_attempts=3):
    # Tasks outside OUTCOMES pass on the first attempt, for CLI runs over the whole dev suite.
    attempts = OUTCOMES.get((task_id, language), [attempt(1, 'pass', 10, 5)])
    if attempts is None:
        raise RuntimeError('Docker is not available')
    prompt = sum(a['prompt_tokens'] for a in attempts)
    completion = sum(a['completion_tokens'] for a in attempts)
    first = attempts[0]['prompt_tokens'] + attempts[0]['completion_tokens']
    last = attempts[-1]
    return run.RunResult(
        task_id=task_id, language=language, model_id=model_id, spec_version=spec_version,
        prompt_version=prompt_version, seed=seed, temperature=run.TEMPERATURE, max_tokens=run.MAX_TOKENS,
        max_attempts=max_attempts, source_provided=False, exec_outcome=last['exec_outcome'],
        compile_ok=True, tests_passed=last['tests_passed'], tests_total=6,
        passed=last['exec_outcome'] == 'pass', attempts_used=len(attempts), prompt_tokens_total=prompt,
        completion_tokens_total=completion, total_tokens=prompt + completion, first_attempt_tokens=first,
        repair_tokens=prompt + completion - first, latency_ms_total=10 * len(attempts), attempts=attempts)


class SuiteDatabaseTestCase(unittest.TestCase):
    """An in-memory database with one user, served to the API routes."""

    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False},
                                    poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.db = self.session_factory()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.user = User(email='suite-user@example.com', password_hash='hash')
        self.db.add(self.user)
        self.db.commit()
        self.results = tempfile.TemporaryDirectory()
        self.addCleanup(self.results.cleanup)

        def override_db():
            db = self.session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[benchmark_routes.get_db] = override_db
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

    def run_suite(self, run_single=fake_run_single):
        store = SuiteStore(self.db, 'Suite-User@example.com ')
        with patch.object(run, 'run_single', side_effect=run_single):
            return suite_runner.run_suite('dev', 'test-model', 0, '1', '0.1', task_ids=TASKS,
                                          results_dir=self.results.name, store=store)

    def log_in(self):
        app.dependency_overrides[get_current_user_controller] = lambda: self.user


class PersistedSuiteTests(SuiteDatabaseTestCase):
    def test_persisted_three_task_suite_creates_one_suite_six_runs_and_their_attempts(self):
        result = self.run_suite()

        [suite] = self.db.query(SuiteRun).all()
        self.assertEqual((suite.cli_suite_run_id, suite.suite, suite.model_name, suite.seed, suite.max_attempts),
                         (result.suite_run_id, 'dev', 'test-model', 0, 3))
        self.assertEqual((suite.status, suite.user_id), ('completed', self.user.id))
        self.assertIsNotNone(suite.finished_at)

        runs = self.db.query(BenchmarkRun).order_by(BenchmarkRun.id).all()
        self.assertEqual(len(runs), 6)
        self.assertEqual({r.suite_run_id for r in runs}, {suite.id})
        pairs = {}
        for r in runs:
            pairs.setdefault(r.pair_id, []).append((r.task_id, r.language))
        self.assertEqual(sorted(sorted(pair) for pair in pairs.values()),
                         sorted([(t, 'python'), (t, 'zak')] for t in TASKS))
        self.assertEqual({(r.task_id, r.language): r.status for r in runs}, {
            ('array_sum', 'zak'): 'passed', ('array_sum', 'python'): 'passed',
            ('palindrome', 'zak'): 'passed', ('palindrome', 'python'): 'failed',
            ('binary_search', 'zak'): 'error', ('binary_search', 'python'): 'passed'})
        # 1 + 1 + 2 + 3 + 0 (crashed) + 1 attempts, each with one evaluation.
        self.assertEqual(self.db.query(func.count(Attempt.id)).scalar(), 8)
        self.assertEqual(self.db.query(func.count(Evaluation.id)).scalar(), 8)

    def test_suite_summary_endpoint_matches_summary_json(self):
        result = self.run_suite()
        suite_id = self.db.query(SuiteRun).one().id
        self.log_in()

        response = self.client.get(f'/suites/{suite_id}')

        self.assertEqual(response.status_code, 200)
        api_summary = response.json()['summary']
        file_summary = json.loads((result.path / 'summary.json').read_text(encoding='utf-8'))
        # The database has no column for the crash message, so only that text differs.
        self.assertEqual(file_summary['errors'][0]['error'], 'RuntimeError: Docker is not available')
        for error in file_summary['errors']:
            error['error'] = None
        self.assertEqual(api_summary, file_summary)
        # Spot-check the numbers the Explorer reads.
        overall = api_summary['overall']
        self.assertEqual((overall['languages']['zak']['pass_at_1'], overall['languages']['zak']['pass_at_k']),
                         (0.3333, 0.6667))
        self.assertEqual(overall['paired']['tasks'], ['array_sum'])
        self.assertEqual(overall['paired']['token_ratio'], 0.6667)  # 120 / 180
        self.assertIn('by_category', api_summary)

    def test_responses_contain_no_hidden_test_data(self):
        self.run_suite()
        self.log_in()
        body = self.client.get('/suites/1').text + self.client.get('/suites').text
        for task_id in TASKS:
            cases = json.loads((suite_runner.TASKS / task_id / 'hidden_tests.json').read_text(encoding='utf-8'))
            for case in cases:
                # The API writes compact JSON, so check that form as well as the default one.
                for separators in ((', ', ': '), (',', ':')):
                    self.assertNotIn(json.dumps(case['inputs'], separators=separators), body, task_id)

    def test_list_suites_needs_login_and_lists_newest_first(self):
        self.run_suite()
        self.run_suite()

        for path in ('/suites', '/suites/1'):
            self.assertEqual(self.client.get(path).status_code, 401, path)

        self.log_in()
        response = self.client.get('/suites')
        self.assertEqual(response.status_code, 200)
        listed = response.json()
        self.assertEqual([suite['id'] for suite in listed], [2, 1])
        self.assertEqual(listed[0]['status'], 'completed')
        self.assertNotIn('summary', listed[0])
        self.assertEqual(self.client.get('/suites/99').status_code, 404)

    def test_stopped_suite_is_marked_failed_and_has_no_summary(self):
        def stop_on_palindrome(task_id, language, *args, **kwargs):
            if task_id == 'palindrome':
                raise KeyboardInterrupt
            return fake_run_single(task_id, language, *args, **kwargs)

        with self.assertRaises(KeyboardInterrupt):
            self.run_suite(stop_on_palindrome)

        suite = self.db.query(SuiteRun).one()
        self.assertEqual(suite.status, 'failed')
        self.assertEqual(self.db.query(func.count(BenchmarkRun.id)).scalar(), 2)
        self.log_in()
        self.assertIsNone(self.client.get(f'/suites/{suite.id}').json()['summary'])

    def test_runs_store_the_category_the_cli_recorded(self):
        self.run_suite()

        stored = {run.task_id: run.category for run in self.db.query(BenchmarkRun)}
        self.assertEqual(stored, {task_id: suite_runner.load_task(task_id)['category'] for task_id in TASKS})

    def test_summary_does_not_reread_task_files(self):
        self.run_suite()
        suite_id = self.db.query(SuiteRun).one().id
        self.log_in()

        with patch('api.controllers.benchmark.get_task_controller', side_effect=AssertionError('read task.json')):
            response = self.client.get(f'/suites/{suite_id}')

        self.assertEqual(response.status_code, 200)
        self.assertIn('by_category', response.json()['summary'])

    def test_suite_detail_lists_one_pair_id_per_task(self):
        self.run_suite()
        suite_id = self.db.query(SuiteRun).one().id
        self.log_in()

        pairs = self.client.get(f'/suites/{suite_id}').json()['pairs']

        stored = {(run.task_id, str(run.pair_id)) for run in self.db.query(BenchmarkRun)}
        self.assertEqual(set(pairs), set(TASKS))
        self.assertEqual(set(pairs.items()), stored)

    def test_other_members_can_read_suite_runs_but_not_personal_ones(self):
        self.run_suite()
        personal_pair_id, personal_runs = create_queued_pair(self.db, self.user, 'array_sum')
        self.db.commit()
        suite_run = self.db.query(BenchmarkRun).filter(BenchmarkRun.suite_run_id.isnot(None)).first()
        member = User(email='member@example.com', password_hash='hash')
        self.db.add(member)
        self.db.commit()
        app.dependency_overrides[get_current_user_controller] = lambda: member

        pair = self.client.get(f'/pairs/{suite_run.pair_id}')
        self.assertEqual(pair.status_code, 200)
        self.assertEqual({run['language'] for run in pair.json()}, {'zak', 'python'})
        self.assertEqual(self.client.get(f'/runs/{suite_run.id}').status_code, 200)

        self.assertEqual(self.client.get(f'/pairs/{personal_pair_id}').status_code, 404)
        self.assertEqual(self.client.get(f'/runs/{personal_runs[0].id}').status_code, 404)
        # The run list stays personal: suite runs do not show up in another member's history.
        self.assertEqual(self.client.get('/runs').json(), [])

    def test_failed_summary_write_marks_the_suite_failed(self):
        with patch.object(suite_runner, 'write_summary', side_effect=OSError('disk full')), \
                self.assertRaises(OSError):
            self.run_suite()

        self.assertEqual(self.db.query(SuiteRun).one().status, 'failed')

    def test_unknown_email_is_rejected_before_anything_is_written(self):
        with self.assertRaisesRegex(ValueError, '^no user has the email nobody@example.com$'):
            SuiteStore(self.db, 'nobody@example.com')
        self.assertEqual(self.db.query(func.count(SuiteRun.id)).scalar(), 0)


class PersistCliTests(SuiteDatabaseTestCase):
    """Run the real CLI and its real open_store() against the test database."""

    def cli(self, *extra, session_factory=None):
        with patch('database.db.SessionLocal', session_factory or self.session_factory), \
                patch.object(run, 'run_single', side_effect=fake_run_single) as run_single, \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            code = zakbench_main(['run', '--suite', 'dev', '--lang', 'both', '--model', 'test-model', *extra],
                                 results_dir=self.results.name)
        return code, run_single.call_count, stderr.getvalue()

    def counts(self):
        return tuple(self.db.query(func.count(model.id)).scalar() for model in (SuiteRun, BenchmarkRun, Attempt))

    def test_without_persist_nothing_is_written_to_the_database(self):
        code, calls, _ = self.cli()

        self.assertEqual(code, 0)
        self.assertEqual(calls, 2 * len(suite_runner.suite_tasks('dev')))
        self.assertEqual(self.counts(), (0, 0, 0))
        self.assertEqual(len(list(Path(self.results.name).iterdir())), 1)  # The results folder is still written.

    def test_persist_writes_the_whole_suite(self):
        code, calls, _ = self.cli('--persist', '--user-email', 'suite-user@example.com')

        self.assertEqual(code, 0)
        suite_count, run_count, _ = self.counts()
        self.assertEqual((suite_count, run_count), (1, calls))
        self.assertEqual(self.db.query(SuiteRun).one().status, 'completed')

    def test_persist_with_an_unknown_email_stops_before_any_inference(self):
        code, calls, stderr = self.cli('--persist', '--user-email', 'nobody@example.com')

        self.assertEqual((code, calls), (1, 0))
        self.assertEqual(stderr, 'error: no user has the email nobody@example.com\n')
        self.assertEqual(self.counts(), (0, 0, 0))

    def test_persist_with_an_unreachable_database_stops_without_printing_the_url(self):
        missing = Path(self.results.name) / 'missing' / 'secret-password.db'
        unreachable = sessionmaker(bind=create_engine(f'sqlite:///{missing}'))

        code, calls, stderr = self.cli('--persist', '--user-email', 'suite-user@example.com',
                                       session_factory=unreachable)

        self.assertEqual((code, calls), (1, 0))
        self.assertEqual(stderr, 'error: could not reach the database (OperationalError)\n')


if __name__ == '__main__':
    unittest.main()
