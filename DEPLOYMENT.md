# Deploying ModelRank on AWS

```
Browser ──HTTPS──▶ AWS Amplify Hosting          (frontend: React + Vite)
   │
   └─────HTTPS──▶ Amazon CloudFront ──HTTP──▶ Elastic Beanstalk, single instance
                  (HTTPS for the API)          (backend: FastAPI + LangGraph in Docker)
```

| Part | AWS service | Source |
| --- | --- | --- |
| Frontend | AWS Amplify Hosting | `frontend/`, built with `amplify.yml` |
| HTTPS for the API | Amazon CloudFront (default `*.cloudfront.net` certificate) | Console settings below |
| Backend | Elastic Beanstalk, Docker on Amazon Linux 2023, single instance | Bundle from `deploy/elastic-beanstalk/package.py` |

Region: `eu-west-1`. No custom domain or load balancer is needed. The
OpenRouter and Tavily keys live only on the backend.

---

## How evaluations run

An evaluation takes several minutes, longer than CloudFront will hold a
request open, so it runs as a background job:

1. `POST /evaluate/jobs` with `{"user_request": "..."}` returns `202` and a
   `job_id`.
2. The frontend polls `GET /evaluate/jobs/{job_id}` every 3 seconds.
   `status` goes `queued` → `running` → `done` (with `result`, the same body
   the old `POST /evaluate` returned) or `failed` (with `error`).
3. `POST /report/pdf` with `{"job_id": "..."}` builds that evaluation's PDF.

Each job runs in its own process with its own directory
(`backend/data/jobs/<job_id>/`), so evaluations running at the same time never
share files, and every PDF comes from its own evaluation. At most
`MODELRANK_MAX_CONCURRENT_JOBS` evaluations run at once (default 2); the rest
wait in order. Finished jobs are deleted after 24 hours.

`POST /evaluate` still exists and waits for the result in one request, for
direct API use. The frontend no longer calls it, and through CloudFront it
would time out.

---

## Environment variables

### Backend: Elastic Beanstalk → Configuration → Updates, monitoring, and logging → Environment properties

| Name | Required | Value |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | yes | OpenRouter API key |
| `TAVILY_API_KEY` | yes | Tavily API key (model search in the Planner) |
| `CORS_ORIGINS` | yes | The Amplify URL, e.g. `https://main.d1234abcd.amplifyapp.com` (comma-separate several) |
| `MODELRANK_MAX_CONCURRENT_JOBS` | no | Evaluations that may run at once. Default `2` |
| `MODELRANK_JOB_TIMEOUT_SECONDS` | no | An evaluation is stopped after this long. Default `1800` (30 min) |
| `MODELRANK_JOB_RETENTION_HOURS` | no | Finished evaluations are deleted after this long. Default `24` |

### Frontend: Amplify → Hosting → Environment variables

| Name | Required | Value |
| --- | --- | --- |
| `VITE_API_URL` | yes | The CloudFront URL, e.g. `https://d1abcdefgh.cloudfront.net` |

`VITE_API_URL` is built into the JavaScript, so redeploy the frontend after
changing it. The Amplify build fails on purpose if it is missing.

Locally, leave all of these unset: the frontend calls `http://127.0.0.1:8000`
and the backend allows `http://localhost:5173`, as before.

---

## Deployment steps

Do these in order: each step needs a URL from the one before.

### Step 1: Build the backend bundle

From the repository root:

```bash
python deploy/elastic-beanstalk/package.py
```

This writes `deploy/elastic-beanstalk/build/modelrank-backend.zip` with the
`Dockerfile`, `requirements.txt`, `backend/` and the nginx settings. It leaves
out `.env`, `docker-compose.yml`, the frontend and local evaluation data.

### Step 2: Create the Elastic Beanstalk environment

In the AWS console, region **Europe (Ireland) eu-west-1**:

1. **Elastic Beanstalk → Create application.**
2. **Environment tier:** Web server environment.
3. **Application name:** `modelrank`. Environment name: `modelrank-prod`.
4. **Platform:** Docker, platform branch **Docker running on 64bit Amazon Linux 2023**, recommended version.
5. **Application code:** Upload your code → choose `modelrank-backend.zip`, version label `v1`.
6. **Presets:** **Single instance**. This needs no load balancer.
7. **Service access:** create or choose the default service role and EC2 instance profile (`aws-elasticbeanstalk-service-role`, `aws-elasticbeanstalk-ec2-role`).
8. **Instance type:** `t3.micro` (or `t3.small`, see below). Root volume: leave the defaults.
9. **Environment properties:** add `OPENROUTER_API_KEY`, `TAVILY_API_KEY`, and for now
   `CORS_ORIGINS` = `http://localhost:5173` (replaced in step 5).
10. **Create** and wait for health to turn **OK**.
11. Open the environment URL (`http://modelrank-prod.<id>.eu-west-1.elasticbeanstalk.com/`). It should show
    `{"message":"ModelRank API is running"}`. Copy the host name, without `http://`.

### Step 3: Put CloudFront in front of the backend

1. **CloudFront → Create distribution.**
2. **Origin domain:** paste the Elastic Beanstalk host name from step 2.
3. **Protocol:** **HTTP only**, port `80`.
4. **Default cache behavior:**
   - Viewer protocol policy: **Redirect HTTP to HTTPS**
   - Allowed HTTP methods: **GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE**
   - Cache policy: **CachingDisabled**
   - Origin request policy: **AllViewerExceptHostHeader** (passes the `Origin` header the backend needs for CORS)
   - Response headers policy: none (the backend sends the CORS headers)
5. **Web Application Firewall:** **Do not enable security protections** (avoids WAF charges).
6. **Price class:** **Use only North America and Europe**.
7. **Create**, wait until the distribution is deployed (several minutes), then open
   `https://<distribution>.cloudfront.net/`. It should show the same health message.

The default origin response timeout (30 s) is fine: every request the frontend
makes now returns in seconds.

### Step 4: Create the Amplify app

1. **AWS Amplify → Create new app → GitHub**, authorize, pick the repository and branch.
2. Tick **My app is a monorepo** and enter `frontend`. Amplify detects `amplify.yml`.
3. **Advanced settings → Environment variables:** `VITE_API_URL` = `https://<distribution>.cloudfront.net` (no trailing slash).
4. **Save and deploy.** Copy the app URL (`https://<branch>.<app-id>.amplifyapp.com`).
5. **Hosting → Rewrites and redirects → Manage redirects**, add:

   | Source address | Target address | Type |
   | --- | --- | --- |
   | `/links` | `/links/` | 301 (Redirect - Permanent) |

   `/` and `/links/` are real HTML files, so they load when opened directly or
   refreshed. The rule only covers `/links` typed without the slash.

### Step 5: Allow the Amplify site to call the API

1. Elastic Beanstalk → `modelrank-prod` → **Configuration → Updates, monitoring, and logging → Edit**.
2. Set `CORS_ORIGINS` to the Amplify URL from step 4, e.g. `https://main.d1234abcd.amplifyapp.com`.
3. **Apply** and wait for health **OK**.

### Step 6: Check the live site

1. Open the Amplify URL, run one evaluation and wait for the ranking. **This uses your OpenRouter and Tavily credits.**
2. Download the PDF.
3. Open `/links/` and `/links`, and refresh both.
4. If something fails: Elastic Beanstalk → **Logs → Request logs → Last 100 lines** shows each job's start, finish and any error.

### Updating later

- **Backend:** run `package.py` again → Elastic Beanstalk → **Upload and deploy** the new zip. An evaluation running during a deploy is lost and shows the error state in the UI.
- **Frontend:** push to the connected branch; Amplify rebuilds automatically.

---

## Known limitations

- **One instance.** Jobs live on the instance's disk and in its process, so keep the environment at one instance. Scaling out would need shared storage.
- **Restarts lose running evaluations.** A deploy, crash or instance replacement fails any queued or running evaluation; the user sees the error state and can start again. Finished results also disappear when the instance is replaced.
- **Polling is not real-time progress.** The progress bar keeps its existing timed animation. Each job reports `last_completed_step` (`planner`, `benchmark`, `runner`, `judge`), which the UI could use later.
- **The API is open.** Anyone who finds the CloudFront URL can start evaluations, which spend OpenRouter credits. CORS only restricts browsers. Consider a spending limit on the OpenRouter key.
- **Direct origin access.** The Elastic Beanstalk URL also answers over plain HTTP. The site never uses it.

---

## Suggested starting resources (eu-west-1)

Measured in the production image: the API server uses about 50 MB and each
running evaluation about 150 MB plus its working data.

| Resource | Size | Approx. monthly cost |
| --- | --- | --- |
| EB instance | 1 × `t3.micro` (1 GB), fine for 2 concurrent evaluations | ≈ $8.50 on-demand; free-tier eligible on new accounts |
| or | 1 × `t3.small` (2 GB) for more headroom | ≈ $17 |
| EBS root volume | 8 GB gp3 (default) | < $1 |
| Public IPv4 address | 1 | ≈ $3.60 |
| CloudFront | API traffic only | Normally $0 (within the always-free 1 TB / 10 M requests) |
| Amplify Hosting | Build minutes + small static site | Usually a few dollars or less at low traffic |

Estimates only; check the AWS Pricing Calculator. OpenRouter and Tavily usage
is billed separately.

---

## Running the tests

```bash
# Backend: no model or network calls
python -m unittest discover -s tests -t .

# Frontend
cd frontend && npm run build && npm run lint
```
