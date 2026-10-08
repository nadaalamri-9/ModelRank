"""Tests for the FastAPI endpoints. No model or network calls.

Run from the repository root:

    python -m unittest discover -s tests -t .
"""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

_jobs_temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ["MODELRANK_JOBS_DIR"] = _jobs_temp.name

from fastapi.testclient import TestClient  # noqa: E402

from backend import main  # noqa: E402
from backend.jobs import JobManager  # noqa: E402
from tests import workers  # noqa: E402


RESULT_FIELDS = {
    "user_request",
    "retry_count",
    "retry_required",
    "selected_model",
    "model_rankings",
    "decision_reason",
    "retry_reason",
}


def tearDownModule():
    time.sleep(0.5)
    _jobs_temp.cleanup()


class ApiTests(unittest.TestCase):

    def setUp(self):
        self.manager = JobManager(
            jobs_dir=Path(_jobs_temp.name),
            worker=workers.isolated_agents_worker,
        )
        patcher = mock.patch.object(main, "jobs", self.manager)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.manager.shutdown, wait=True)

        self.client = TestClient(main.app)

    def poll(self, job_id, timeout=60):
        deadline = time.time() + timeout

        while time.time() < deadline:
            response = self.client.get(f"/evaluate/jobs/{job_id}")
            self.assertEqual(response.status_code, 200)

            job = response.json()

            if job["status"] in ("done", "failed"):
                return job

            time.sleep(0.2)

        self.fail("Job did not finish")

    def test_health_check(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "ModelRank API is running"})

    def test_job_lifecycle(self):
        response = self.client.post(
            "/evaluate/jobs",
            json={"user_request": "Project A"},
        )

        self.assertEqual(response.status_code, 202)
        started = response.json()
        self.assertIn(started["status"], ("queued", "running"))

        job = self.poll(started["job_id"])

        self.assertEqual(job["status"], "done")
        self.assertEqual(set(job["result"]), RESULT_FIELDS)
        self.assertEqual(job["result"]["user_request"], "Project A")

    def test_unknown_job_is_404(self):
        for job_id in ("0" * 32, "not-a-job"):
            with self.subTest(job_id=job_id):
                response = self.client.get(f"/evaluate/jobs/{job_id}")
                self.assertEqual(response.status_code, 404)

    def test_each_pdf_uses_its_own_evaluation(self):
        job_ids = {}

        for name in ("Project A", "Project B"):
            response = self.client.post("/evaluate/jobs", json={"user_request": name})
            job_ids[name] = response.json()["job_id"]

        for name, job_id in job_ids.items():
            self.assertEqual(self.poll(job_id)["status"], "done")

        for name, job_id in job_ids.items():
            with self.subTest(name=name), mock.patch.object(
                main,
                "generate_pdf_report",
                wraps=main.generate_pdf_report,
            ) as generate:
                response = self.client.post(
                    "/report/pdf",
                    json={"job_id": job_id, "user_request": "ignored"},
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["content-type"], "application/pdf")
                self.assertTrue(response.content.startswith(b"%PDF"))

                kwargs = generate.call_args.kwargs
                self.assertEqual(kwargs["user_request"], name)
                self.assertEqual(
                    kwargs["final_decision"]["decision_reason"],
                    f"Best fit for {name}",
                )

    def test_report_errors(self):
        self.assertEqual(
            self.client.post("/report/pdf", json={"user_request": "x"}).status_code,
            422,
        )
        self.assertEqual(
            self.client.post("/report/pdf", json={"job_id": "0" * 32}).status_code,
            404,
        )

        slow = JobManager(jobs_dir=Path(_jobs_temp.name), worker=workers.slow_worker)
        self.addCleanup(slow.shutdown, wait=True)

        with mock.patch.object(main, "jobs", slow):
            job_id = slow.submit("Unfinished")
            response = self.client.post("/report/pdf", json={"job_id": job_id})
            self.assertEqual(response.status_code, 409)
            slow.wait(job_id, 0.2)

    def test_waiting_evaluate_endpoint_still_works(self):
        response = self.client.post("/evaluate", json={"user_request": "Project C"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body) - {"job_id"}, RESULT_FIELDS)
        self.assertEqual(body["user_request"], "Project C")

    def test_waiting_evaluate_endpoint_reports_failure(self):
        failing = JobManager(
            jobs_dir=Path(_jobs_temp.name),
            worker=workers.crashing_worker,
        )
        self.addCleanup(failing.shutdown, wait=True)

        with mock.patch.object(main, "jobs", failing):
            response = self.client.post("/evaluate", json={"user_request": "x"})

        self.assertEqual(response.status_code, 500)


if __name__ == "__main__":
    unittest.main()
