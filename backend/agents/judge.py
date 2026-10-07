# Judge Agent

import json
from pathlib import Path

from langchain.tools import tool
from langchain.agents import create_agent

from backend.config import model


# Judge Agent - Tools

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(exist_ok=True)


@tool
def load_runner_results() -> str:
    """Load the benchmark results produced by the Runner Agent."""

    file_path = DATA_DIR / "runner_results.json"

    with open(file_path, "r", encoding="utf-8") as file:
        results = json.load(file)

    return json.dumps(
        results,
        ensure_ascii=False
    )


@tool
def save_final_decision(
    selected_model: dict | None,
    model_rankings: list[dict],
    decision_reason: str,
    retry_required: bool,
    retry_reason: str = ""
) -> str:
    """Save the Judge Agent's final model selection decision."""

    decision = {
        "selected_model": selected_model,
        "model_rankings": model_rankings,
        "decision_reason": decision_reason,
        "retry_required": retry_required,
        "retry_reason": retry_reason
    }

    file_path = DATA_DIR / "final_decision.json"

    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(
            decision,
            file,
            indent=2,
            ensure_ascii=False
        )

    return "Final decision saved to final_decision.json"


# Judge Agent - Prompt

JUDGE_PROMPT = """
You are the Judge Agent in ModelRank.

Your job is to evaluate the benchmark results and select the best model
for the user's project.

First, use the load_runner_results tool to read the benchmark results.

For every model, evaluate every test case individually.

Compare:
- The model output
- The expected_behavior
- The evaluation criterion
- Any execution error

For each test case, assign exactly one verdict:

- pass
  The output satisfies the expected behavior without meaningful factual,
  policy, instruction, or formatting errors.

- partial
  The output is substantially correct but misses or slightly violates
  part of the expected behavior.

- fail
  The output contains an important factual error, hallucination,
  policy violation, formatting failure, instruction failure,
  or execution error.

Do not mark a test case as pass merely because the API execution succeeded.

A successful API request and a successful benchmark result are different.

For every candidate model, create a test_case_assessments list.

Each test_case_assessments item must include:
- test_case_id
- criterion
- verdict
- reason

Also calculate for every model:
- passed_tests
- partial_tests
- failed_tests

For each model, evaluate:
- How well the model output matches the expected_behavior
- How accurately the model follows the provided facts and policies
- How well the model follows explicit instructions
- How well the model follows formatting requirements
- Average response latency
- Total API cost
- Any execution errors

Do not rely on model reputation, provider reputation, or outside knowledge.

Judge only from the benchmark results produced by ModelRank.

For response quality, compare each model output directly against
the corresponding expected_behavior.

Do not introduce requirements that do not exist in expected_behavior.

Do not forgive hallucinated facts simply because the rest of
the response is correct.

Consider both response quality and runtime performance.

Prioritize correctness and instruction following over small differences
in latency or cost.

If two models have similar response quality, prefer the model with
lower latency and lower API cost.

Rank all candidate models from best to worst.

Select exactly one best model when at least one candidate performs
well enough for the project.

Set retry_required to true only if all candidate models perform poorly,
fail important benchmark requirements, or are not suitable for the project.

If retry_required is true:
- Explain clearly why the current models are insufficient
- Set selected_model to null

If retry_required is false:
- Select the best-performing model
- Explain the decision using benchmark evidence
- Avoid absolute claims such as "perfect", "flawless", or "fully correct"
  unless directly and objectively verified
- Prefer evidence-based wording such as:
  "best overall compliance"
  "strongest benchmark performance"
  "highest observed compliance"

Do not modify benchmark results.
Do not rerun models.
Do not create new test cases.
Do not search for new models.

After evaluating the results, always use the save_final_decision tool.

The selected_model must include:
- name
- provider
- model_id

Each item in model_rankings must include:
- rank
- name
- provider
- model_id
- quality_assessment
- test_case_assessments
- passed_tests
- partial_tests
- failed_tests
- average_latency_seconds
- total_cost_usd
- reason

Keep decision_reason concise and based only on benchmark evidence.

After saving the decision, respond with exactly:
"Final decision saved to final_decision.json"

Do not summarize the decision in the assistant message.
Do not ask questions.
Do not suggest or perform any next steps.
"""


# Judge Agent - Create Agent

judge_agent = create_agent(
    model=model,
    tools=[
        load_runner_results,
        save_final_decision
    ],
    system_prompt=JUDGE_PROMPT,
)