# Planner Agent

import json
import requests

from pathlib import Path

from langchain.tools import tool
from langchain.agents import create_agent
from langchain_tavily import TavilySearch

from backend.config import model
from backend.schemas import EvaluationPlan


# Planner Agent - Tools

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DATA_DIR.mkdir(exist_ok=True)


tavily_search = TavilySearch(max_results=5)


@tool
def search_models(query: str) -> str:
    """Search the web for current information about suitable LLMs."""

    results = tavily_search.invoke(
        {
            "query": query
        }
    )

    return json.dumps(
        results,
        ensure_ascii=False
    )


@tool
def verify_model_ids(candidate_models: list[dict]) -> str:
    """Verify that candidate model IDs currently exist on OpenRouter."""

    response = requests.get(
        "https://openrouter.ai/api/v1/models",
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    available_model_ids = {
        model_info["id"]
        for model_info in data.get("data", [])
        if model_info.get("id")
    }

    verified_models = []
    invalid_models = []

    for candidate in candidate_models:
        model_id = candidate.get("model_id")

        if model_id in available_model_ids:
            verified_models.append(candidate)
        else:
            invalid_models.append(candidate)

    result = {
        "verified_models": verified_models,
        "invalid_models": invalid_models
    }

    return json.dumps(
        result,
        ensure_ascii=False
    )


@tool(args_schema=EvaluationPlan)
def save_evaluation_plan(
    project_name: str,
    project_type: str,
    project_goal: str,
    evaluation_criteria: list[str],
    candidate_models: list[dict],
    notes: str = ""
) -> str:
    """Validate and save the evaluation plan as a JSON file."""

    plan = EvaluationPlan.model_validate(
        {
            "project_name": project_name,
            "project_type": project_type,
            "project_goal": project_goal,
            "evaluation_criteria": evaluation_criteria,
            "candidate_models": candidate_models,
            "notes": notes
        }
    )

    with open(DATA_DIR / "evaluation_plan.json", "w", encoding="utf-8") as file:
        json.dump(
            plan.model_dump(),
            file,
            indent=2,
            ensure_ascii=False
        )

    return "Evaluation plan saved to evaluation_plan.json"


# Planner Agent - Prompt

PLANNER_PROMPT = """
You are the Planner Agent in ModelRank.

Your task is to analyze the user's AI project and create
a relevant evaluation plan.

Identify the project's goal, type, evaluation criteria,
and suitable candidate LLMs.

Use only requirements explicitly provided by the user.
Do not invent requirements, constraints, examples, or assumptions.
Evaluation criteria must come from the user's request,
not from external search results.

Use search_models to find suitable LLMs and their exact
OpenRouter model IDs.

Search only once unless the results are insufficient
or model verification fails.

Select distinct, relevant models supported by the search results.
Prefer different providers when appropriate.

Never invent model names or IDs.
Each model's name, provider, and model_id must match.
Use exact OpenRouter IDs without the "openrouter:" prefix.

Always call verify_model_ids before saving the plan.

Include only models returned in verified_models.
If any model is invalid, search for a replacement
and verify again.

Never save unverified models.

Do not claim that candidate models have been tested,
benchmarked, ranked, or validated by ModelRank.

Keep selection notes brief and based on search evidence.

Focus only on planning.
Do not generate test cases or execute evaluations.

Once verification succeeds, call save_evaluation_plan
to save evaluation_plan.json.

After saving, respond with exactly:
"Evaluation plan saved to evaluation_plan.json"

Do not summarize, explain, ask questions,
or suggest additional steps.
"""


# Planner Agent - Create Agent

planner_agent = create_agent(
    model=model,
    tools=[
        search_models,
        verify_model_ids,
        save_evaluation_plan
    ],
    system_prompt=PLANNER_PROMPT,
)