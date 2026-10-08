"""Stand-in job workers for the tests. None of them call a model or the network.

Workers run in a spawned process, so they must be importable top-level
functions.
"""

import json
import time
from pathlib import Path

from backend import jobs


def _finish(job_dir: Path, final_state: dict) -> None:
    final_decision = jobs._read_json(job_dir / "final_decision.json")

    jobs._write_json(
        job_dir / "result.json",
        jobs.build_evaluation_response(final_state, final_decision),
    )
    jobs._update_status(job_dir, status=jobs.DONE, finished_at=time.time())


def _final_state(user_request: str) -> dict:
    return {
        "user_request": user_request,
        "retry_count": 0,
        "retry_required": False,
        "selected_model": {
            "name": f"{user_request} model",
            "provider": "Test",
            "model_id": "test/model",
        },
    }


def isolated_agents_worker(job_dir_path: str, user_request: str) -> None:
    """Drive the real agents' file tools inside the job's directory.

    Mirrors evaluation_worker, with synthetic data in place of model calls.
    Every read checks that it sees this job's own data.
    """

    job_dir = Path(job_dir_path)
    jobs.point_agents_at(job_dir)

    from backend import workflow
    from backend.agents import benchmark, judge, planner, runner

    planner.save_evaluation_plan.invoke({
        "project_name": user_request,
        "project_type": "test",
        "project_goal": "test",
        "evaluation_criteria": ["Accuracy"],
        "candidate_models": [
            {"name": f"{user_request} model", "model_id": "test/model"},
        ],
    })
    jobs._update_status(job_dir, last_completed_step="planner")

    plan = json.loads(benchmark.load_evaluation_plan.invoke({}))
    assert plan["project_name"] == user_request, plan

    benchmark.save_benchmark.invoke({
        "project_name": user_request,
        "test_cases": [{"id": "tc-1", "prompt": "Test prompt"}],
    })
    jobs._update_status(job_dir, last_completed_step="benchmark")

    inputs = json.loads(runner.load_runner_inputs.invoke({}))
    assert inputs["benchmark"]["project_name"] == user_request, inputs

    # Give a concurrent job time to write its own files in between
    time.sleep(1.5)

    runner.save_runner_results.invoke({
        "results_json": json.dumps({
            "project_name": user_request,
            "models": [{
                "model_id": "test/model",
                "results": [{
                    "error": None,
                    "latency_seconds": 1.0,
                    "cost_usd": 0.001,
                    "input_tokens": 10,
                    "output_tokens": 20,
                }],
            }],
        }),
    })
    jobs._update_status(job_dir, last_completed_step="runner")

    results = json.loads(judge.load_runner_results.invoke({}))
    assert results["project_name"] == user_request, results

    judge.save_final_decision.invoke({
        "selected_model": _final_state(user_request)["selected_model"],
        "model_rankings": [{
            "rank": 1,
            "name": f"{user_request} model",
            "provider": "Test",
            "model_id": "test/model",
            "passed_tests": 1,
            "partial_tests": 0,
            "failed_tests": 0,
        }],
        "decision_reason": f"Best fit for {user_request}",
        "retry_required": False,
    })
    jobs._update_status(job_dir, last_completed_step="judge")

    # The workflow's Judge node reads final_decision.json through this
    assert workflow.DATA_DIR == job_dir

    _finish(job_dir, _final_state(user_request))


def slow_worker(job_dir_path: str, user_request: str) -> None:
    job_dir = Path(job_dir_path)
    time.sleep(3)

    jobs._write_json(
        job_dir / "final_decision.json",
        {
            "selected_model": _final_state(user_request)["selected_model"],
            "model_rankings": [],
            "decision_reason": f"Best fit for {user_request}",
            "retry_required": False,
            "retry_reason": "",
        },
    )
    _finish(job_dir, _final_state(user_request))


def crashing_worker(job_dir_path: str, user_request: str) -> None:
    raise RuntimeError("Simulated crash")


def hanging_worker(job_dir_path: str, user_request: str) -> None:
    time.sleep(120)
