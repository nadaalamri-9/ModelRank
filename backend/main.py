# ModelRank - FastAPI Backend

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.workflow import model_rank_graph
from backend.report import generate_pdf_report


app = FastAPI(
    title="ModelRank API",
    version="1.0.0",
)


# CORS

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Paths

DATA_DIR = Path(__file__).resolve().parent / "data"


# Request Schema

class EvaluationRequest(BaseModel):
    user_request: str


# Health Check

@app.get("/")
def root():
    return {
        "message": "ModelRank API is running"
    }


# Evaluate Models

@app.post("/evaluate")
def evaluate(request: EvaluationRequest):

    initial_state = {
        "user_request": request.user_request,
        "retry_count": 0,
        "retry_required": False,
        "selected_model": None,
    }

    final_state = model_rank_graph.invoke(
        initial_state
    )

    final_decision_path = DATA_DIR / "final_decision.json"

    with open(
        final_decision_path,
        "r",
        encoding="utf-8",
    ) as file:
        final_decision = json.load(file)

    return {
        "user_request": final_state["user_request"],
        "retry_count": final_state["retry_count"],
        "retry_required": final_state["retry_required"],
        "selected_model": final_state["selected_model"],
        "model_rankings": final_decision.get(
            "model_rankings",
            [],
        ),
        "decision_reason": final_decision.get(
            "decision_reason",
            "",
        ),
        "retry_reason": final_decision.get(
            "retry_reason",
            "",
        ),
    }


# Download PDF Report

@app.post("/report/pdf")
def download_pdf_report(
    request: EvaluationRequest,
):

    final_decision_path = DATA_DIR / "final_decision.json"

    with open(
        final_decision_path,
        "r",
        encoding="utf-8",
    ) as file:
        final_decision = json.load(file)

    pdf_buffer = generate_pdf_report(
        user_request=request.user_request,
        final_decision=final_decision,
    )

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                'attachment; filename="ModelRank_Report.pdf"'
            )
        },
    )