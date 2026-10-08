# Benchmark Agent

import json
from pathlib import Path

from langchain.tools import tool
from langchain.agents import create_agent

from backend.config import model
from backend.schemas import BenchmarkDocument, EvaluationPlan


# Benchmark Agent - Tools

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(exist_ok=True)


@tool
def load_evaluation_plan() -> str:
    """Load and validate the evaluation plan created by the Planner Agent."""

    with open(DATA_DIR / "evaluation_plan.json", "r", encoding="utf-8") as file:
        plan = json.load(file)

    validated_plan = EvaluationPlan.model_validate(plan)

    return json.dumps(
        validated_plan.model_dump(),
        ensure_ascii=False
    )


@tool(args_schema=BenchmarkDocument)
def save_benchmark(
    project_name: str,
    test_cases: list[dict]
) -> str:
    """Validate and save benchmark test cases as a JSON file."""

    benchmark = BenchmarkDocument.model_validate(
        {
            "project_name": project_name,
            "test_cases": test_cases
        }
    )

    with open(DATA_DIR / "benchmark.json", "w", encoding="utf-8") as file:
        json.dump(
            benchmark.model_dump(),
            file,
            indent=2,
            ensure_ascii=False
        )

    return "Benchmark saved to benchmark.json"


# Benchmark Agent - Prompt

BENCHMARK_PROMPT = """
You are the Benchmark Agent in ModelRank.

Your task is to create a compact, project-specific benchmark.

First, call load_evaluation_plan to read the evaluation plan.

Generate test cases based only on the project's goal
and evaluation criteria.

Create tests only for criteria that require model responses,
such as accuracy, reasoning, clarity, or instruction following.

Do not create tests for latency or API cost.
These are measured during execution.

Make every test case self-contained and unambiguous.

Include all necessary facts, rules, policies, and context
inside the test prompt whenever factual accuracy is evaluated.

Do not invent external facts, policies, prices, dates,
or requirements missing from the evaluation plan.

Each expected_behavior must:
- Be specific and objectively verifiable.
- Follow only the facts and instructions in its test prompt.
- Avoid assumptions about missing information.
- Clearly identify when the model must not invent details.

Ensure every expected_behavior is logically consistent
with its corresponding prompt.

Create exactly 3 distinct, relevant test cases.
Avoid duplicates and unnecessary complexity.

Do not modify candidate models, run evaluations,
or select the best model.

Call save_benchmark to validate and save the test cases
as benchmark.json.

Do not output or summarize the test cases.

After saving, respond with exactly:
"Benchmark saved to benchmark.json"

Do not ask questions or suggest additional steps.
"""


# Benchmark Agent - Create Agent

benchmark_agent = create_agent(
    model=model,
    tools=[
        load_evaluation_plan,
        save_benchmark
    ],
    system_prompt=BENCHMARK_PROMPT,
)