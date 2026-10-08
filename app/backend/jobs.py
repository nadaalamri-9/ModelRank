# ModelRank - Background Evaluation Jobs
#
# An evaluation runs the full LangGraph workflow and can take several
# minutes, longer than a proxy will hold one HTTP request open. Instead, the
# API starts a job and the frontend polls for its status.
#
# Each job runs in its own process with its own data directory, so
# concurrent evaluations never share evaluation_plan.json, benchmark.json,
# runner_results.json or final_decision.json. The agents are unchanged: the
# worker process points their module-level DATA_DIR at the job's directory
# before running the workflow.

import json
import logging
import multiprocessing
import os
import re
import shutil
import sys
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


logger = logging.getLogger("modelrank.jobs")


# Configuration

JOBS_DIR = Path(
    os.getenv(
        "MODELRANK_JOBS_DIR",
        Path(__file__).resolve().parent / "data" / "jobs",
    )
)

MAX_CONCURRENT_JOBS = int(os.getenv("MODELRANK_MAX_CONCURRENT_JOBS", "2"))
JOB_TIMEOUT_SECONDS = int(os.getenv("MODELRANK_JOB_TIMEOUT_SECONDS", "1800"))
JOB_RETENTION_SECONDS = int(os.getenv("MODELRANK_JOB_RETENTION_HOURS", "24")) * 3600

JOB_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")

QUEUED = "queued"
RUNNING = "running"
DONE = "done"
FAILED = "failed"


# Files

FILE_RETRY_ATTEMPTS = 20
FILE_RETRY_SECONDS = 0.05


def _retry_while_locked(action):
    # On Windows, reading a file while another process replaces it (or
    # replacing it while it is being read) briefly fails with
    # PermissionError. Linux renames are atomic, so this never retries there.
    for attempt in range(FILE_RETRY_ATTEMPTS):
        try:
            return action()
        except PermissionError:
            if attempt == FILE_RETRY_ATTEMPTS - 1:
                raise

            time.sleep(FILE_RETRY_SECONDS)


def _write_json(path: Path, data: dict) -> None:
    # Write then rename, so a reader never sees a half-written file
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")

    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    _retry_while_locked(lambda: os.replace(temp_path, path))


def _read_json(path: Path) -> dict:
    def read():
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)

    return _retry_while_locked(read)


def _update_status(job_dir: Path, **changes) -> None:
    status = _read_json(job_dir / "status.json")
    status.update(changes)
    _write_json(job_dir / "status.json", status)


# Evaluation

def build_evaluation_response(final_state: dict, final_decision: dict) -> dict:
    """The /evaluate response body, unchanged from the synchronous API."""

    return {
        "user_request": final_state["user_request"],
        "retry_count": final_state["retry_count"],
        "retry_required": final_state["retry_required"],
        "selected_model": final_state["selected_model"],
        "model_rankings": final_decision.get(
            "model_rankings",
            [],
        ),
        "decision_reason": final_decision.get(
            "decision_reason",
            "",
        ),
        "retry_reason": final_decision.get(
            "retry_reason",
            "",
        ),
    }


def point_agents_at(data_dir: Path) -> None:
    """Make every agent and the workflow read and write in data_dir.

    Only safe inside a job's own worker process.
    """

    from backend import workflow
    from backend.agents import benchmark, judge, planner, runner

    for module in (workflow, planner, benchmark, runner, judge):
        module.DATA_DIR = data_dir


def run_workflow(graph, initial_state: dict, on_step=None) -> dict:
    """Run the graph to completion, reporting each finished node.

    Equivalent to graph.invoke(initial_state): every node returns the
    full state, so the last update is the final state.
    """

    final_state = dict(initial_state)

    for update in graph.stream(initial_state, stream_mode="updates"):
        for node, node_state in update.items():
            if node_state:
                final_state.update(node_state)

            if on_step:
                on_step(node)

    return final_state


def evaluation_worker(job_dir_path: str, user_request: str) -> None:
    """Entry point of a job's worker process."""

    job_dir = Path(job_dir_path)

    try:
        point_agents_at(job_dir)

        from backend.workflow import model_rank_graph

        initial_state = {
            "user_request": user_request,
            "retry_count": 0,
            "retry_required": False,
            "selected_model": None,
        }

        final_state = run_workflow(
            model_rank_graph,
            initial_state,
            on_step=lambda step: _update_status(
                job_dir,
                last_completed_step=step,
            ),
        )

        final_decision = _read_json(job_dir / "final_decision.json")

        _write_json(
            job_dir / "result.json",
            build_evaluation_response(final_state, final_decision),
        )

        _update_status(job_dir, status=DONE, finished_at=time.time())

    except Exception:
        traceback.print_exc(file=sys.stderr)

        _update_status(
            job_dir,
            status=FAILED,
            error="The evaluation failed.",
            finished_at=time.time(),
        )

        sys.exit(1)


# Job Manager

class JobNotFound(Exception):
    pass


class JobNotFinished(Exception):
    pass


class JobManager:
    """Queues evaluations and runs each in its own process.

    At most max_concurrent jobs run at once; the rest wait in order.
    State lives in each job's directory, so it can be read from any thread.
    """

    def __init__(
        self,
        jobs_dir: Path = JOBS_DIR,
        max_concurrent: int = MAX_CONCURRENT_JOBS,
        timeout_seconds: int = JOB_TIMEOUT_SECONDS,
        retention_seconds: int = JOB_RETENTION_SECONDS,
        worker=evaluation_worker,
    ):
        self.jobs_dir = Path(jobs_dir)
        self.timeout_seconds = timeout_seconds
        self.retention_seconds = retention_seconds
        self.worker = worker

        self.jobs_dir.mkdir(parents=True, exist_ok=True)

        # spawn: a fresh interpreter per job, nothing inherited from the
        # server's threads
        self._context = multiprocessing.get_context("spawn")
        self._executor = ThreadPoolExecutor(
            max_workers=max_concurrent,
            thread_name_prefix="modelrank-job",
        )
        self._cleanup_lock = threading.Lock()

        self._fail_interrupted_jobs()

    # Public API

    def submit(self, user_request: str) -> str:
        self.cleanup_expired()

        job_id = uuid.uuid4().hex
        job_dir = self.jobs_dir / job_id
        job_dir.mkdir(parents=True)

        _write_json(job_dir / "request.json", {"user_request": user_request})
        _write_json(
            job_dir / "status.json",
            {
                "status": QUEUED,
                "last_completed_step": None,
                "error": None,
                "created_at": time.time(),
            },
        )

        self._executor.submit(self._run, job_id)

        logger.info("Queued evaluation job %s", job_id)

        return job_id

    def get(self, job_id: str) -> dict:
        """Status of a job, with its result once it is done."""

        job_dir = self._job_dir(job_id)
        status = _read_json(job_dir / "status.json")

        job = {
            "job_id": job_id,
            "status": status["status"],
            "last_completed_step": status.get("last_completed_step"),
            "error": status.get("error"),
        }

        if status["status"] == DONE:
            job["result"] = _read_json(job_dir / "result.json")

        return job

    def wait(self, job_id: str, poll_seconds: float = 1.0) -> dict:
        while True:
            job = self.get(job_id)

            if job["status"] in (DONE, FAILED):
                return job

            time.sleep(poll_seconds)

    def final_decision(self, job_id: str) -> tuple[str, dict]:
        """The user request and Judge decision of a finished job."""

        job_dir = self._job_dir(job_id)

        if _read_json(job_dir / "status.json")["status"] != DONE:
            raise JobNotFinished(job_id)

        user_request = _read_json(job_dir / "request.json")["user_request"]
        final_decision = _read_json(job_dir / "final_decision.json")

        return user_request, final_decision

    def cleanup_expired(self) -> None:
        cutoff = time.time() - self.retention_seconds

        with self._cleanup_lock:
            for job_dir in self.jobs_dir.iterdir():
                try:
                    status = _read_json(job_dir / "status.json")
                except (OSError, ValueError):
                    continue

                if status["status"] in (QUEUED, RUNNING):
                    continue

                if status.get("finished_at", 0) < cutoff:
                    shutil.rmtree(job_dir, ignore_errors=True)

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=True)

    # Internals

    def _job_dir(self, job_id: str) -> Path:
        # The id becomes a path, so accept only ids this manager creates
        if not JOB_ID_PATTERN.match(job_id or ""):
            raise JobNotFound(job_id)

        job_dir = self.jobs_dir / job_id

        if not (job_dir / "status.json").is_file():
            raise JobNotFound(job_id)

        return job_dir

    def _run(self, job_id: str) -> None:
        job_dir = self.jobs_dir / job_id

        try:
            user_request = _read_json(job_dir / "request.json")["user_request"]

            _update_status(job_dir, status=RUNNING, started_at=time.time())
            logger.info("Started evaluation job %s", job_id)

            process = self._context.Process(
                target=self.worker,
                args=(str(job_dir), user_request),
                daemon=True,
            )
            process.start()
            process.join(self.timeout_seconds)

            if process.is_alive():
                process.terminate()
                process.join(10)

                _update_status(
                    job_dir,
                    status=FAILED,
                    error="The evaluation timed out.",
                    finished_at=time.time(),
                )
                logger.error("Evaluation job %s timed out", job_id)
                return

            status = _read_json(job_dir / "status.json")["status"]

            if status != DONE and status != FAILED:
                _update_status(
                    job_dir,
                    status=FAILED,
                    error="The evaluation stopped unexpectedly.",
                    finished_at=time.time(),
                )

            logger.info(
                "Evaluation job %s finished: %s",
                job_id,
                _read_json(job_dir / "status.json")["status"],
            )

        except Exception:
            logger.exception("Evaluation job %s could not run", job_id)

            try:
                _update_status(
                    job_dir,
                    status=FAILED,
                    error="The evaluation failed.",
                    finished_at=time.time(),
                )
            except OSError:
                pass

    def _fail_interrupted_jobs(self) -> None:
        # Jobs left queued or running by a previous server process can
        # never finish
        for job_dir in self.jobs_dir.iterdir():
            try:
                status = _read_json(job_dir / "status.json")
            except (OSError, ValueError):
                continue

            if status["status"] in (QUEUED, RUNNING):
                _update_status(
                    job_dir,
                    status=FAILED,
                    error="The evaluation was interrupted by a server restart.",
                    finished_at=time.time(),
                )
