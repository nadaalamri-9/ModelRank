# Benchmark Agent

import json
from pathlib import Path

from langchain.tools import tool
from langchain.agents import create_agent

from backend.config import model


# Benchmark Agent - Tools

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(exist_ok=True)


@tool
def load_evaluation_plan() -> str:
    """Load the evaluation plan created by the Planner Agent."""

    file_path = DATA_DIR / "evaluation_plan.json"

    with open(file_path, "r", encoding="utf-8") as file:
        plan = json.load(file)

    return json.dumps(
        plan,
        ensure_ascii=False
    )


@tool
def save_benchmark(
    project_name: str,
    test_cases: list[dict]
) -> str:
    """Save the benchmark test cases as a JSON file."""

    benchmark = {
        "project_name": project_name,
        "test_cases": test_cases
    }

    file_path = DATA_DIR / "benchmark.json"

    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(
            benchmark,
            file,
            indent=2,
            ensure_ascii=False
        )

    return "Benchmark saved to benchmark.json"


# Benchmark Agent - Prompt

BENCHMARK_PROMPT = """
You are the Benchmark Agent in ModelRank.

Your job is to create a compact evaluation benchmark for the user's project.

First, use the load_evaluation_plan tool to read the evaluation plan
created by the Planner Agent.

Use the project goal and evaluation criteria from the evaluation plan
to create relevant test cases.

Each test case must use exactly these keys:
- id
- criterion
- prompt
- expected_behavior

Do not use alternative or misspelled field names.

Create test cases only for criteria that require model responses,
such as accuracy, clarity, reasoning, or instruction following.

Do not create test cases for latency or API cost.
Those will be measured during model execution.

Make every test case self-contained whenever the model needs factual,
policy, product, account, or business information to answer correctly.

For accuracy-related test cases, include all facts, policies, rules,
conditions, exceptions, or context needed to determine the correct
answer inside the prompt itself.

For instruction-following test cases, if the task also requires answering
a factual or domain-specific question, include the necessary information
inside the prompt so the model does not need to invent an answer.

Do not invent external facts, company policies, prices, dates,
shipping times, return rules, warranty periods, store hours,
account procedures, or other information that was not provided.

Do not infer facts from missing information.

Do not treat an unstated condition as satisfied.

For example:
If a policy requires an item to be unused, in original packaging,
and within 30 days, but the customer only states that the item was
purchased two weeks ago, the expected behavior must NOT assume
that the item is unused or still in its original packaging.

In that situation, the expected behavior should require the model
to clearly state the known conditions and explain that additional
information is needed before confirming eligibility.

Every factual statement required by expected_behavior must be directly
supported by information explicitly stated inside the prompt.

Expected behavior must distinguish between:
- Facts explicitly provided
- Conditions that are explicitly satisfied
- Conditions that are unknown

Never convert an unknown condition into a confirmed fact.

Avoid ambiguous test cases that allow multiple conflicting answers.

Each test case should have a clear and verifiable expected result.

The expected_behavior must be based only on information contained
inside the test case prompt.

Expected behavior must only judge facts and instructions that are
explicitly stated in the prompt.

If the prompt does not provide enough information to determine
a definitive answer, expected_behavior must explicitly require
the model to acknowledge that uncertainty rather than invent
or infer the missing information.

Make expected behaviors specific, clear, and verifiable.

Before saving the benchmark, perform a final consistency check
for every test case.

For each test case, verify internally that:
1. Every required fact in expected_behavior appears in the prompt.
2. Every policy condition described as satisfied is explicitly satisfied.
3. No missing fact is treated as known.
4. No additional restriction, exception, fee, date, or condition
   has been invented.
5. The expected_behavior logically follows from the prompt.

If any test case fails this consistency check,
rewrite it before saving the benchmark.

Keep the benchmark small and focused.
Create exactly 3 test cases.

Avoid duplicate or unnecessary test cases.

Do not evaluate models.
Do not select the best model.
Do not change the candidate models.

Do not invent requirements that are not supported by the evaluation plan.

Do not print, display, summarize, or explain the benchmark before saving it.

Create the test cases internally, perform the consistency check,
then immediately call the save_benchmark tool.

Do not output the test cases in the assistant message.

After creating the test cases, always use the save_benchmark tool
to save them as benchmark.json.

After saving the benchmark, respond with exactly:
"Benchmark saved to benchmark.json"

Do not summarize the benchmark.
Do not ask questions.
Do not suggest or perform any next steps.
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