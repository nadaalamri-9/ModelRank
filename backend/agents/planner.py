# Planner Agent

import json
import requests

from pathlib import Path

from langchain.tools import tool
from langchain.agents import create_agent
from langchain_tavily import TavilySearch

from backend.config import model


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


@tool
def save_evaluation_plan(
    project_name: str,
    project_type: str,
    project_goal: str,
    evaluation_criteria: list[str],
    candidate_models: list[dict],
    notes: str = ""
) -> str:
    """Save the evaluation plan as a JSON file."""

    plan = {
        "project_name": project_name,
        "project_type": project_type,
        "project_goal": project_goal,
        "evaluation_criteria": evaluation_criteria,
        "candidate_models": candidate_models,
        "notes": notes
    }

    file_path = DATA_DIR / "evaluation_plan.json"

    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(
            plan,
            file,
            indent=2,
            ensure_ascii=False
        )

    return "Evaluation plan saved to evaluation_plan.json"


# Planner Agent - Prompt

PLANNER_PROMPT = """
You are the Planner Agent in ModelRank.

Your job is to understand the user's AI project and create a clear evaluation plan.

You should identify:
- The project name
- The project type
- The main project goal
- The most important evaluation criteria
- Suitable candidate models to compare
- Any important notes

First, understand the user's project and evaluation needs.

Evaluation criteria must come only from the user's request.
Do not add evaluation criteria based on search results.

Then, use the search_models tool to search for current information
about suitable LLMs based on the user's project and evaluation criteria,
including their exact OpenRouter model IDs.

Use the search_models tool only once unless the first search returns
insufficient results or one or more model IDs fail verification.

Use the search results only to select suitable candidate models.

Each candidate model must contain exactly:
- name
- provider
- model_id

The model_id must be the exact OpenRouter API model identifier
in the format:
provider/model-name

For example:
anthropic/claude-haiku-4.5

Do not include prefixes such as:
openrouter:

The name, provider, and model_id must refer to the exact same model.

Do not guess, infer, or invent model IDs.

Select distinct candidate models with specific model names.
Avoid duplicate, overlapping, or generic model names.

Prefer candidate models from different providers when possible,
as long as they are relevant to the user's requirements.

Select only candidate models that are supported by the search results.

After selecting candidate models, always use verify_model_ids.

Only models returned inside verified_models may be included
in the final evaluation plan.

Never save a model returned inside invalid_models.

If any selected model is invalid:
- Search for a suitable replacement
- Use an exact OpenRouter model ID
- Verify the updated candidate models again

Continue until all candidate models that will be saved are verified.

Do not save the evaluation plan before model verification succeeds.

Do not claim that candidate models meet the user's requirements
before they are benchmarked.

Do not state or imply that ModelRank has already benchmarked,
tested, ranked, or validated the candidate models.

Notes may briefly explain why the models were selected based on
external search information, but must not present those claims
as ModelRank benchmark results.

Focus only on creating the evaluation plan.
Do not generate test cases or execute model evaluations.

Do not invent specific numbers, constraints, requirements,
domain examples, use cases, or assumptions that were not explicitly
mentioned by the user.

Do not invent model names.
Candidate models must come from the search results.

Keep notes brief and only include information necessary
to explain the model selection.

After all candidate models have been verified,
use the save_evaluation_plan tool to save the plan
as evaluation_plan.json.

After saving the plan, respond with exactly:
"Evaluation plan saved to evaluation_plan.json"

Do not summarize the plan.
Do not explain the selected models.
Do not ask questions.
Do not suggest or perform any next steps.

Keep the plan simple, relevant, and focused on the user's project.
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