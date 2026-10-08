# ModelRank - FastAPI Backend

import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.jobs import (
    FAILED,
    JobManager,
    JobNotFinished,
    JobNotFound,
)
from backend.report import generate_pdf_report


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


app = FastAPI(
    title="ModelRank API",
    version="1.0.0",
)


# CORS
# Production sets CORS_ORIGINS (comma-separated, e.g. the Amplify domain);
# without it, only the local frontend is allowed.

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

CORS_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
] or DEFAULT_CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Evaluation Jobs
# Each evaluation runs in its own process and data directory (backend/jobs.py)

jobs = JobManager()


# Request Schemas

class EvaluationRequest(BaseModel):
    user_request: str


class ReportRequest(BaseModel):
    job_id: str
    user_request: str | None = None


def _get_job(job_id: str) -> dict:
    try:
        return jobs.get(job_id)
    except JobNotFound:
        raise HTTPException(status_code=404, detail="Evaluation not found.")


# Health Check

@app.get("/")
def root():
    return {
        "message": "ModelRank API is running"
    }


# Evaluate Models (background job)
# Start with POST /evaluate/jobs, then poll GET /evaluate/jobs/{job_id}
# until status is "done" (with "result") or "failed".

@app.post("/evaluate/jobs", status_code=202)
def start_evaluation(request: EvaluationRequest):
    job_id = jobs.submit(request.user_request)

    return _get_job(job_id)


@app.get("/evaluate/jobs/{job_id}")
def get_evaluation(job_id: str):
    return _get_job(job_id)


# Evaluate Models (waits for the result)
# Kept for direct API use; behind a proxy, prefer the job endpoints.

@app.post("/evaluate")
def evaluate(request: EvaluationRequest):
    job = jobs.wait(jobs.submit(request.user_request))

    if job["status"] == FAILED:
        raise HTTPException(status_code=500, detail=job["error"])

    return {
        **job["result"],
        "job_id": job["job_id"],
    }


# Download PDF Report

@app.post("/report/pdf")
def download_pdf_report(
    request: ReportRequest,
):

    try:
        user_request, final_decision = jobs.final_decision(request.job_id)
    except JobNotFound:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    except JobNotFinished:
        raise HTTPException(
            status_code=409,
            detail="This evaluation has no finished result.",
        )

    pdf_buffer = generate_pdf_report(
        user_request=user_request,
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
