# Judge Agent

import json
from pathlib import Path

from langchain.tools import tool
from langchain.agents import create_agent

from backend.config import model
from backend.schemas import FinalDecision, RunnerResults


# Judge Agent - Tools

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(exist_ok=True)


@tool
def load_runner_results() -> str:
    """Load and validate the benchmark results produced by the Runner Agent."""

    with open(DATA_DIR / "runner_results.json", "r", encoding="utf-8") as file:
        results = json.load(file)

    RunnerResults.model_validate(results)

    return json.dumps(
        results,
        ensure_ascii=False
    )


@tool(args_schema=FinalDecision)
def save_final_decision(
    selected_model: dict | None,
    model_rankings: list[dict],
    decision_reason: str,
    retry_required: bool,
    retry_reason: str = ""
) -> str:
    """Validate and save the Judge Agent's final model selection decision."""

    decision = FinalDecision.model_validate(
        {
            "selected_model": selected_model,
            "model_rankings": model_rankings,
            "decision_reason": decision_reason,
            "retry_required": retry_required,
            "retry_reason": retry_reason
        }
    )

    with open(DATA_DIR / "final_decision.json", "w", encoding="utf-8") as file:
        json.dump(
            decision.model_dump(),
            file,
            indent=2,
            ensure_ascii=False
        )

    return "Final decision saved to final_decision.json"


# Judge Agent - Prompt

JUDGE_PROMPT = """
You are the Judge Agent in ModelRank.

Your task is to evaluate benchmark results, rank candidate models,
and recommend the best model for the user's project.

First, call load_runner_results.

Evaluate each model using:
- Compliance with expected_behavior
- Factual accuracy and instruction following
- Response latency and API cost
- Execution errors

Judge only from ModelRank benchmark evidence.
Do not rely on model or provider reputation.

Compare each response directly against its expected_behavior.
A successful API call does not mean the response passed the test.

For every model, evaluate every test case individually and assign
exactly one verdict:
- pass: the output satisfies the expected behavior without meaningful
  factual, policy, instruction, or formatting errors.
- partial: the output is substantially correct but misses or slightly
  violates part of the expected behavior.
- fail: the output contains an important factual error, hallucination,
  policy violation, formatting failure, instruction failure,
  or execution error.

Each model_rankings item must include test_case_assessments,
with one item per test case: test_case_id, criterion, verdict
(pass, partial, or fail), and reason.
Also give passed_tests, partial_tests, and failed_tests for each model.

Prioritize response correctness and instruction following.
When quality is similar, prefer lower latency and cost.

Rank all candidate models from best to worst.

Select the best-performing model if at least one candidate
meets the project's important requirements.

Set retry_required to true only when all candidates
perform poorly or fail important requirements.

If retry_required is true:
- Do not recommend a selected model.
- Explain why the candidates are insufficient.

If retry_required is false:
- Select one best-performing model.
- Explain the choice using benchmark evidence.

Keep decision_reason concise and evidence-based.
Avoid unsupported claims of perfect or flawless performance.

Do not modify results, rerun models, create test cases,
or search for new models.

Call save_final_decision to save final_decision.json.

After saving, respond with exactly:
"Final decision saved to final_decision.json"

Do not summarize results, ask questions,
or suggest additional steps.
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