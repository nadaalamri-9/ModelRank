# ModelRank - Structured Output Schemas
#
# Matches the schemas in ModelRank_Agents.ipynb. ModelRanking also carries
# the per-test PASS / PARTIAL / FAIL assessments that the frontend and the
# PDF report display.

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# Shared model information

class CandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    provider: str
    model_id: str


# 1. Planner Agent

class EvaluationPlan(BaseModel):
    project_name: str
    project_type: str
    project_goal: str
    evaluation_criteria: list[str]
    candidate_models: list[CandidateModel]
    notes: str = ""


# 2. Benchmark Agent

class BenchmarkCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    criterion: str
    prompt: str
    expected_behavior: str


class BenchmarkDocument(BaseModel):
    project_name: str
    test_cases: list[BenchmarkCase] = Field(
        min_length=3,
        max_length=3
    )


# 3. Runner Agent

class TestExecutionResult(BaseModel):
    test_case_id: str
    criterion: str
    expected_behavior: str
    output: Optional[str] = None
    latency_seconds: float
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    error: Optional[str] = None


class RunnerSummary(BaseModel):
    average_latency_seconds: Optional[float] = None
    total_cost_usd: Optional[float] = None
    total_input_tokens: int
    total_output_tokens: int
    successful_tests: int
    failed_tests: int


class ModelExecutionResults(CandidateModel):
    results: list[TestExecutionResult]
    summary: Optional[RunnerSummary] = None


class RunnerResults(BaseModel):
    project_name: str
    models: list[ModelExecutionResults]


# 4. Judge Agent

class TestCaseAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_case_id: str
    criterion: str
    verdict: Literal["pass", "partial", "fail"]
    reason: str


class ModelRanking(CandidateModel):
    rank: int = Field(ge=1)
    quality_assessment: str
    test_case_assessments: list[TestCaseAssessment]
    passed_tests: int
    partial_tests: int
    failed_tests: int
    average_latency_seconds: Optional[float] = None
    total_cost_usd: Optional[float] = None
    reason: str


class FinalDecision(BaseModel):
    selected_model: Optional[CandidateModel]
    model_rankings: list[ModelRanking]
    decision_reason: str
    retry_required: bool
    retry_reason: str = ""
