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


# Runner Agent - Tools

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(exist_ok=True)


@tool
def load_runner_inputs() -> str:
    """Load the evaluation plan and benchmark."""

    evaluation_plan_path = DATA_DIR / "evaluation_plan.json"
    benchmark_path = DATA_DIR / "benchmark.json"

    with open(evaluation_plan_path, "r", encoding="utf-8") as file:
        plan = json.load(file)

    with open(benchmark_path, "r", encoding="utf-8") as file:
        benchmark = json.load(file)

    inputs = {
        "evaluation_plan": plan,
        "benchmark": benchmark
    }

    return json.dumps(inputs, ensure_ascii=False)


@tool
def run_models_parallel(runner_inputs: str) -> str:
    """Run all candidate models on the same benchmark in parallel."""

    inputs = json.loads(runner_inputs)

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

    return json.dumps(results, ensure_ascii=False)


@tool
def save_runner_results(results_json: str) -> str:
    """Calculate model summaries and save the runner results."""

    runner_results = json.loads(results_json)

    for model_data in runner_results["models"]:
        successful_results = [
            result
            for result in model_data["results"]
            if result["error"] is None
        ]

        failed_results = [
            result
            for result in model_data["results"]
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

        model_data["summary"] = {
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

    file_path = DATA_DIR / "runner_results.json"

    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(
            runner_results,
            file,
            indent=2,
            ensure_ascii=False
        )

    return "Runner results saved to runner_results.json"


# Runner Agent - Prompt

RUNNER_PROMPT = """
You are the Runner Agent in ModelRank.

Your job is to execute the benchmark on all candidate models
and save the runtime results.

First, use the load_runner_inputs tool to load:
- The evaluation plan
- The benchmark test cases

Then, pass the output of load_runner_inputs directly to
the run_models_parallel tool.

Use the run_models_parallel tool to execute all candidate models
on the same benchmark.

The candidate models must be executed in parallel.

Then, pass the output of run_models_parallel directly to
the save_runner_results tool.

The save_runner_results tool must calculate the model summaries
and save the final results to runner_results.json.

The same benchmark must be used for every candidate model.

Do not modify:
- The candidate models
- The benchmark test cases
- The expected behaviors
- The evaluation criteria

Do not evaluate the quality of model responses.
Do not decide whether a response passed or failed the expected behavior.
Do not select the best model.
Do not rank the models.
Do not make recommendations.

Your job is only to execute the benchmark and collect runtime data.

For every test case, collect:
- Test case ID
- Evaluation criterion
- Expected behavior
- Model output
- Response latency
- Input token usage
- Output token usage
- Total token usage
- API cost when available
- Any execution error

For every model, calculate:
- Average response latency
- Total API cost
- Total input tokens
- Total output tokens
- Number of successful executions
- Number of failed executions

Always follow this tool order:

1. load_runner_inputs
2. run_models_parallel
3. save_runner_results

After save_runner_results completes successfully, respond with exactly:
"Benchmark completed and saved to runner_results.json"

Do not print or summarize the benchmark results.
Do not explain model performance.
Do not ask questions.
Do not suggest or perform any next steps.
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