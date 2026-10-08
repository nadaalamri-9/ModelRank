"""Tests for backend/jobs.py. No model or network calls.

Run from the app/ directory:

    python -m unittest discover -s tests -t .
"""

import json
import tempfile
import time
import unittest
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

from backend import jobs
from backend.workflow import route_after_judge, route_after_planner
from backend.jobs import (
    DONE,
    FAILED,
    QUEUED,
    RUNNING,
    JobManager,
    JobNotFinished,
    JobNotFound,
)
from tests import workers


BACKEND_DATA_DIR = Path(jobs.__file__).resolve().parent / "data"


def wait_until(predicate, timeout=60, interval=0.1):
    deadline = time.time() + timeout

    while time.time() < deadline:
        if predicate():
            return True

        time.sleep(interval)

    return False


class ToyState(TypedDict):
    user_request: str
    retry_count: int
    retry_required: bool
    selected_model: dict | None


def build_toy_graph(retries_wanted: int):
    """The real workflow's nodes and routing, without agents."""

    def passthrough(state):
        return state

    def judge(state):
        retry = state["retry_count"] < retries_wanted

        return {
            **state,
            "retry_required": retry,
            "retry_count": state["retry_count"] + (1 if retry else 0),
            "selected_model": None if retry else {"name": "Winner"},
        }

    graph = StateGraph(ToyState)
    graph.add_node("planner", passthrough)
    graph.add_node("benchmark", passthrough)
    graph.add_node("runner", passthrough)
    graph.add_node("judge", judge)
    graph.set_entry_point("planner")
    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        {"benchmark": "benchmark", "runner": "runner"},
    )
    graph.add_edge("benchmark", "runner")
    graph.add_edge("runner", "judge")
    graph.add_conditional_edges(
        "judge",
        route_after_judge,
        {"planner": "planner", "end": END},
    )

    return graph.compile()


class RunWorkflowTests(unittest.TestCase):

    def test_matches_invoke_and_reports_each_step(self):
        initial_state = {
            "user_request": "Test",
            "retry_count": 0,
            "retry_required": False,
            "selected_model": None,
        }

        # The Judge counts a retry before route_after_judge checks it
        # against MAX_RETRIES, so the workflow loops back at most once
        for retries_wanted, loops in ((0, 0), (1, 1), (2, 1)):
            with self.subTest(retries_wanted=retries_wanted):
                graph = build_toy_graph(retries_wanted)
                steps = []

                final_state = jobs.run_workflow(graph, initial_state, steps.append)

                self.assertEqual(final_state, graph.invoke(initial_state))
                self.assertEqual(
                    steps,
                    ["planner", "benchmark", "runner", "judge"]
                    + ["planner", "runner", "judge"] * loops,
                )


class BuildEvaluationResponseTests(unittest.TestCase):

    def test_has_the_original_response_fields(self):
        response = jobs.build_evaluation_response(
            {
                "user_request": "Request",
                "retry_count": 1,
                "retry_required": False,
                "selected_model": {"name": "Model"},
                "ignored": True,
            },
            {
                "model_rankings": [{"rank": 1}],
                "decision_reason": "Reason",
            },
        )

        self.assertEqual(
            response,
            {
                "user_request": "Request",
                "retry_count": 1,
                "retry_required": False,
                "selected_model": {"name": "Model"},
                "model_rankings": [{"rank": 1}],
                "decision_reason": "Reason",
                "retry_reason": "",
            },
        )


class JobManagerTests(unittest.TestCase):

    def setUp(self):
        self._temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.jobs_dir = Path(self._temp.name)
        self.managers = []

    def tearDown(self):
        # Let every job thread finish before its directory is deleted
        for manager in self.managers:
            manager.shutdown(wait=True)

        # Give stopped workers a moment to release files on Windows
        time.sleep(0.5)
        self._temp.cleanup()

    def make_manager(self, **options):
        manager = JobManager(jobs_dir=self.jobs_dir, **options)
        self.managers.append(manager)

        return manager

    def test_concurrent_jobs_use_separate_files(self):
        shared_files = {
            path.name: path.stat().st_mtime_ns
            for path in BACKEND_DATA_DIR.glob("*.json")
        }

        manager = self.make_manager(
            max_concurrent=2,
            worker=workers.isolated_agents_worker,
        )

        job_a = manager.submit("Project A")
        job_b = manager.submit("Project B")

        # Both are running at the same time
        self.assertTrue(
            wait_until(
                lambda: manager.get(job_a)["status"] == RUNNING
                and manager.get(job_b)["status"] == RUNNING,
            )
        )

        for job_id, name in ((job_a, "Project A"), (job_b, "Project B")):
            job = manager.wait(job_id, poll_seconds=0.2)

            self.assertEqual(job["status"], DONE, job)
            self.assertEqual(job["last_completed_step"], "judge")
            self.assertEqual(job["result"]["user_request"], name)
            self.assertEqual(
                job["result"]["decision_reason"],
                f"Best fit for {name}",
            )

            job_dir = self.jobs_dir / job_id

            for file_name in (
                "evaluation_plan.json",
                "benchmark.json",
                "runner_results.json",
            ):
                data = json.loads((job_dir / file_name).read_text("utf-8"))
                self.assertEqual(data["project_name"], name, file_name)

            user_request, decision = manager.final_decision(job_id)
            self.assertEqual(user_request, name)
            self.assertEqual(decision["decision_reason"], f"Best fit for {name}")

        # The shared backend/data files were not touched
        self.assertEqual(
            shared_files,
            {
                path.name: path.stat().st_mtime_ns
                for path in BACKEND_DATA_DIR.glob("*.json")
            },
        )

        # Repointing DATA_DIR only happened inside the workers
        from backend.agents import planner

        self.assertEqual(planner.DATA_DIR, BACKEND_DATA_DIR)

    def test_extra_jobs_wait_their_turn(self):
        manager = self.make_manager(max_concurrent=1, worker=workers.slow_worker)

        first = manager.submit("First")
        second = manager.submit("Second")

        self.assertTrue(
            wait_until(lambda: manager.get(first)["status"] == RUNNING)
        )
        self.assertEqual(manager.get(second)["status"], QUEUED)

        self.assertEqual(manager.wait(first, 0.2)["status"], DONE)
        self.assertEqual(manager.wait(second, 0.2)["status"], DONE)

        first_status = jobs._read_json(self.jobs_dir / first / "status.json")
        second_status = jobs._read_json(self.jobs_dir / second / "status.json")
        self.assertGreaterEqual(
            second_status["started_at"],
            first_status["finished_at"],
        )

    def test_crashed_worker_fails_the_job(self):
        manager = self.make_manager(worker=workers.crashing_worker)

        job = manager.wait(manager.submit("Crash"), 0.2)

        self.assertEqual(job["status"], FAILED)
        self.assertEqual(job["error"], "The evaluation stopped unexpectedly.")
        self.assertNotIn("result", job)

    def test_timed_out_worker_is_stopped(self):
        manager = self.make_manager(
            worker=workers.hanging_worker,
            timeout_seconds=3,
        )

        job = manager.wait(manager.submit("Hang"), 0.2)

        self.assertEqual(job["status"], FAILED)
        self.assertEqual(job["error"], "The evaluation timed out.")

    def test_unfinished_jobs_fail_after_restart(self):
        manager = self.make_manager(max_concurrent=1, worker=workers.slow_worker)
        first = manager.submit("First")
        queued = manager.submit("Second")
        manager.shutdown()

        restarted = self.make_manager(worker=workers.slow_worker)

        job = restarted.get(queued)
        self.assertEqual(job["status"], FAILED)
        self.assertEqual(
            job["error"],
            "The evaluation was interrupted by a server restart.",
        )

        # Let the first job's still-running worker finish before cleanup
        self.assertTrue(
            wait_until(
                lambda: (self.jobs_dir / first / "result.json").exists(),
                timeout=30,
            )
        )

    def test_unknown_and_malformed_ids_are_rejected(self):
        manager = self.make_manager(worker=workers.slow_worker)

        for job_id in ("0" * 32, "../../etc/passwd", "", "ABC"):
            with self.subTest(job_id=job_id):
                with self.assertRaises(JobNotFound):
                    manager.get(job_id)

                with self.assertRaises(JobNotFound):
                    manager.final_decision(job_id)

    def test_report_needs_a_finished_job(self):
        manager = self.make_manager(worker=workers.slow_worker)
        job_id = manager.submit("Unfinished")

        with self.assertRaises(JobNotFinished):
            manager.final_decision(job_id)

        manager.wait(job_id, 0.2)
        self.assertEqual(manager.final_decision(job_id)[0], "Unfinished")

    def test_expired_jobs_are_removed(self):
        manager = self.make_manager(
            worker=workers.slow_worker,
            retention_seconds=0,
        )

        old = manager.submit("Old")
        manager.wait(old, 0.2)

        manager.submit("New")

        self.assertFalse((self.jobs_dir / old).exists())


if __name__ == "__main__":
    unittest.main()
