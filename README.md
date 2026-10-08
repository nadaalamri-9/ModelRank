# ModelRank

**Find the model worth building on.**

ModelRank is a multi-agent LLM evaluation system that benchmarks language models against project-specific requirements and identifies the best fit based on quality, latency, and cost.

**Developed by Nada Alamri**  
As part of the **Advanced Agentic AI Systems Engineering Program**  
by [**SDAIA Academy**](https://github.com/SDAIAAcademy)

### Explore ModelRank

**[Live Application](https://main.d315adazaocnwp.amplifyapp.com)** · **[Links Page](https://main.d315adazaocnwp.amplifyapp.com/links/)**

### Agent Notebook

**[View ModelRank Agents Notebook](./ModelRank_Agents.ipynb)**

Want to explore the agents without navigating the full application?

The notebook provides a standalone, simplified implementation of the agents, tools, prompts, structured output validation, and LangGraph orchestration in one place.

---

## Overview

ModelRank takes a project description and automatically:

1. Analyzes requirements and identifies evaluation criteria.
2. Discovers suitable language models.
3. Generates project-specific benchmark test cases.
4. Executes the same benchmark across candidate models.
5. Evaluates responses and compares quality, latency, and cost.
6. Ranks the models and recommends the strongest fit.

## Multi-Agent Architecture

ModelRank uses four specialized agents orchestrated with **LangGraph**.

| Agent | Responsibility |
|---|---|
| **Planner** | Analyzes requirements, researches models, and defines evaluation criteria |
| **Benchmark** | Generates targeted test cases |
| **Runner** | Executes models and captures responses, latency, token usage, and cost |
| **Judge** | Assesses responses and ranks models based on benchmark performance |

![ModelRank LangGraph Workflow](./app/frontend/public/modelrank-workflow.svg)

LangGraph orchestrates the agents through conditional routing, with a single retry when necessary. The Runner executes candidate models in parallel, while Pydantic validates intermediate data and agent tool inputs.

### Background Evaluations

Evaluations run as isolated background jobs, allowing the frontend to track progress without blocking requests. Each evaluation maintains its own results and PDF report.

## Tech Stack

| Layer | Technologies |
|---|---|
| AI & Orchestration | LangChain, LangGraph, OpenRouter, Tavily |
| Backend | Python, FastAPI, Pydantic, ReportLab |
| Frontend | React, Vite, JavaScript |
| Deployment | Docker, AWS Elastic Beanstalk, CloudFront, AWS Amplify |

## Project Structure

```text
ModelRank/
├── app/
│   ├── backend/                  # API, agents, workflow, jobs, reports
│   ├── frontend/                 # React application and Links page
│   ├── tests/                    # Automated backend tests
│   ├── deploy/elastic-beanstalk/ # AWS deployment tooling
│   ├── docker-compose.yml
│   └── requirements.txt
├── ModelRank_Agents.ipynb        # Standalone agent notebook
├── amplify.yml                   # AWS Amplify build settings
└── README.md
```

## Local Setup

Clone the repository:

```bash
git clone https://github.com/nadaalamri-9/ModelRank.git
cd ModelRank/app
```

Create a `.env` file in the `app/` directory:

```env
OPENROUTER_API_KEY=your_openrouter_api_key
TAVILY_API_KEY=your_tavily_api_key
```

Run the application:

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API documentation: http://localhost:8000/docs

Run backend tests from the `app/` directory:

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -t .
```

## Evaluation Results

ModelRank provides ranked model recommendations, benchmark assessments (`PASS`, `PARTIAL`, `FAIL`), latency and cost comparisons, and a downloadable PDF evaluation report.

---

## Author

**Nada Alamri**