# ModelRank - LangGraph Workflow

import json
from pathlib import Path
from typing import TypedDict

from langchain.messages import HumanMessage
from langgraph.graph import StateGraph, END

from backend.agents.planner import planner_agent
from backend.agents.benchmark import benchmark_agent
from backend.agents.runner import runner_agent
from backend.agents.judge import judge_agent


# Data Directory

DATA_DIR = Path(__file__).resolve().parent / "data"


# LangGraph - State

class ModelRankState(TypedDict):
    user_request: str
    retry_count: int
    retry_required: bool
    selected_model: dict | None


# LangGraph - Nodes

def planner_node(state: ModelRankState):
    if state["retry_count"] > 0:
        planner_message = f"""
The previous candidate models were not good enough.

Select a new set of candidate models for the same user request.

Do not select the same candidate models used in the previous attempt.

Original user request:
{state["user_request"]}
"""
    else:
        planner_message = state["user_request"]

    planner_agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content=planner_message
                )
            ]
        }
    )

    return state


def benchmark_node(state: ModelRankState):
    benchmark_agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content="Create the benchmark using the saved evaluation plan."
                )
            ]
        }
    )

    return state


def runner_node(state: ModelRankState):
    runner_agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content="Run the benchmark using the saved evaluation plan and benchmark."
                )
            ]
        }
    )

    return state


def judge_node(state: ModelRankState):
    judge_agent.invoke(
        {
            "messages": [
                HumanMessage(
                    content="Evaluate the saved runner results and select the best model."
                )
            ]
        }
    )

    final_decision_path = DATA_DIR / "final_decision.json"

    with open(final_decision_path, "r", encoding="utf-8") as file:
        decision = json.load(file)

    retry_count = state["retry_count"]

    if decision["retry_required"]:
        retry_count += 1

    return {
        **state,
        "retry_required": decision["retry_required"],
        "retry_count": retry_count,
        "selected_model": decision["selected_model"]
    }


# LangGraph - Routing

MAX_RETRIES = 2


def route_after_planner(state: ModelRankState):
    if state["retry_count"] > 0:
        return "runner"

    return "benchmark"


def route_after_judge(state: ModelRankState):
    if (
        state["retry_required"]
        and state["retry_count"] < MAX_RETRIES
    ):
        return "planner"

    return "end"


# LangGraph - Workflow

workflow = StateGraph(ModelRankState)

workflow.add_node("planner", planner_node)
workflow.add_node("benchmark", benchmark_node)
workflow.add_node("runner", runner_node)
workflow.add_node("judge", judge_node)

workflow.set_entry_point("planner")

workflow.add_conditional_edges(
    "planner",
    route_after_planner,
    {
        "benchmark": "benchmark",
        "runner": "runner"
    }
)

workflow.add_edge(
    "benchmark",
    "runner"
)

workflow.add_edge(
    "runner",
    "judge"
)

workflow.add_conditional_edges(
    "judge",
    route_after_judge,
    {
        "planner": "planner",
        "end": END
    }
)

model_rank_graph = workflow.compile()