# Runner Agent

import json
import os
import time
import requests

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain.tools import tool
from langchain.agents import create_agent

from backend.config import model
from backend.schemas import BenchmarkDocument, EvaluationPlan, RunnerResults


# Runner Agent - Tools

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(exist_ok=True)

# Raw results handed from run_models_parallel to save_runner_results.
# They stay on disk instead of passing through the model: an LLM copying
# the full results into a tool argument truncates or alters them, the
# validation error goes back to the model, and nothing is saved.
RAW_RESULTS_FILE = "runner_raw_results.json"


def _read_runner_inputs() -> dict:
    with open(DATA_DIR / "evaluation_plan.json", "r", encoding="utf-8") as file:
        plan = json.load(file)

    with open(DATA_DIR / "benchmark.json", "r", encoding="utf-8") as file:
        benchmark = json.load(file)

    plan = EvaluationPlan.model_validate(plan).model_dump()
    benchmark = BenchmarkDocument.model_validate(benchmark).model_dump()

    return {
        "evaluation_plan": plan,
        "benchmark": benchmark
    }


@tool
def load_runner_inputs() -> str:
    """Load and validate the evaluation plan and benchmark."""

    return json.dumps(_read_runner_inputs(), ensure_ascii=False)


@tool
def run_models_parallel() -> str:
    """Run all candidate models on the saved benchmark in parallel."""

    inputs = _read_runner_inputs()

    plan = inputs["evaluation_plan"]
    benchmark = inputs["benchmark"]

    candidate_models = plan["candidate_models"]
    test_cases = benchmark["test_cases"]

    api_key = os.environ.get("OPENROUTER_API_KEY")
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    def run_model(model_info):
        model_results = []

        for test_case in test_cases:

            payload = {
                "model": model_info["model_id"],
                "messages": [
                    {
                        "role": "user",
                        "content": test_case["prompt"]
                    }
                ],
                "temperature": 0,
                "usage": {
                    "include": True
                }
            }

            start_time = time.perf_counter()

            try:
                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=120
                )

                response.raise_for_status()

                elapsed_time = time.perf_counter() - start_time
                data = response.json()

                output = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})

                model_results.append(
                    {
                        "test_case_id": test_case["id"],
                        "criterion": test_case["criterion"],
                        "expected_behavior": test_case["expected_behavior"],
                        "output": output,
                        "latency_seconds": round(elapsed_time, 3),
                        "input_tokens": usage.get("prompt_tokens"),
                        "output_tokens": usage.get("completion_tokens"),
                        "total_tokens": usage.get("total_tokens"),
                        "cost_usd": usage.get("cost"),
                        "error": None
                    }
                )

            except Exception as error:
                elapsed_time = time.perf_counter() - start_time

                model_results.append(
                    {
                        "test_case_id": test_case["id"],
                        "criterion": test_case["criterion"],
                        "expected_behavior": test_case["expected_behavior"],
                        "output": None,
                        "latency_seconds": round(elapsed_time, 3),
                        "input_tokens": None,
                        "output_tokens": None,
                        "total_tokens": None,
                        "cost_usd": None,
                        "error": str(error)
                    }
                )

        return {
            "name": model_info["name"],
            "provider": model_info["provider"],
            "model_id": model_info["model_id"],
            "results": model_results
        }

    all_results = []

    with ThreadPoolExecutor(
        max_workers=len(candidate_models)
    ) as executor:

        futures = [
            executor.submit(
                run_model,
                model_info
            )
            for model_info in candidate_models
        ]

        for future in as_completed(futures):
            all_results.append(
                future.result()
            )

    results = {
        "project_name": plan["project_name"],
        "models": all_results
    }

    validated_results = RunnerResults.model_validate(results)

    with open(DATA_DIR / RAW_RESULTS_FILE, "w", encoding="utf-8") as file:
        file.write(validated_results.model_dump_json())

    return (
        f"Ran {len(candidate_models)} models on {len(test_cases)} test cases. "
        "Results are ready for save_runner_results."
    )


@tool
def save_runner_results() -> str:
    """Calculate model summaries and save validated runner results."""

    raw_results_path = DATA_DIR / RAW_RESULTS_FILE

    with open(raw_results_path, "r", encoding="utf-8") as file:
        runner_results = RunnerResults.model_validate_json(
            file.read()
        ).model_dump()

    for model in runner_results["models"]:

        successful_results = [
            result
            for result in model["results"]
            if result["error"] is None
        ]

        failed_results = [
            result
            for result in model["results"]
            if result["error"] is not None
        ]

        latencies = [
            result["latency_seconds"]
            for result in successful_results
        ]

        costs = [
            result["cost_usd"]
            for result in successful_results
            if result["cost_usd"] is not None
        ]

        input_tokens = [
            result["input_tokens"]
            for result in successful_results
            if result["input_tokens"] is not None
        ]

        output_tokens = [
            result["output_tokens"]
            for result in successful_results
            if result["output_tokens"] is not None
        ]

        model["summary"] = {
            "average_latency_seconds": (
                round(sum(latencies) / len(latencies), 3)
                if latencies
                else None
            ),
            "total_cost_usd": (
                round(sum(costs), 8)
                if costs
                else None
            ),
            "total_input_tokens": sum(input_tokens),
            "total_output_tokens": sum(output_tokens),
            "successful_tests": len(successful_results),
            "failed_tests": len(failed_results)
        }

    with open(DATA_DIR / "runner_results.json", "w", encoding="utf-8") as file:
        json.dump(
            runner_results,
            file,
            indent=2,
            ensure_ascii=False
        )

    raw_results_path.unlink()

    return "Runner results saved to runner_results.json"


# Runner Agent - Prompt

RUNNER_PROMPT = """
You are the Runner Agent in ModelRank.

Your task is to execute the benchmark on all candidate models
and save the runtime results.

Always follow this tool order:

1. load_runner_inputs
2. run_models_parallel
3. save_runner_results

Each tool reads what the previous tool saved,
so call them in order without passing results between them.

Use the same benchmark for every candidate model.
Models must be executed in parallel.

Do not modify candidate models, test cases,
expected behaviors, or evaluation criteria.

Collect model responses, latency, token usage,
API costs when available, and execution errors.

The save_runner_results tool calculates model summaries
and saves them to runner_results.json.

Do not evaluate response quality, assign PASS or FAIL,
rank models, or make recommendations.
Your responsibility is execution and data collection only.

After saving successfully, respond with exactly:
"Benchmark completed and saved to runner_results.json"

Do not print or summarize results.
Do not ask questions or suggest additional steps.
"""


# Runner Agent - Create Agent

runner_agent = create_agent(
    model=model,
    tools=[
        load_runner_inputs,
        run_models_parallel,
        save_runner_results
    ],
    system_prompt=RUNNER_PROMPT,
)