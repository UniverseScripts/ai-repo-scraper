# AgentRisk DaaS — Maintainer & Dormancy Risk Signal API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon_Serverless-4169E1?style=flat-square&logo=postgresql)](https://neon.tech/)
[![Redis](https://img.shields.io/badge/Redis-Upstash_Sliding_Window-DC382D?style=flat-square&logo=redis)](https://upstash.com/)
[![Vercel](https://img.shields.io/badge/Frontend-Vercel_Edge-000000?style=flat-square&logo=vercel)](https://agentrisk-daas-asteriostech-projects.vercel.app/)

> **Institutional-Grade Data-as-a-Service (DaaS) engine providing maintainer-concentration and dormancy-reactivation risk telemetry across the AI agent supply chain (Model Context Protocol / MCP servers, npm, and PyPI packages).**

---

## 📌 Problem & Value Proposition

- **71% Single-Maintainer Risk**: Over 70% of audited Model Context Protocol (MCP) packages rely on a single maintainer, creating severe bus-factor and account-takeover liabilities.
- **Dormancy Reactivation Threat**: Attackers routinely acquire dormant packages with high download volume and release malicious updates post-dormancy.
- **Honest Telemetry Scope**: Every field returned by AgentRisk DaaS traces directly to public registry metadata (`registry.npmjs.org`, `pypi.org`) and GitHub API telemetry. Zero fabricated metrics, zero static code stubs.

---

## 🚀 Live Endpoints

- **Frontend Landing Page**: [https://agentrisk-daas-asteriostech-projects.vercel.app/](https://agentrisk-daas-asteriostech-projects.vercel.app/)
- **Backend API Base**: `https://agentrisk-daas.onrender.com`

---

## 📊 Composite Risk Indices

AgentRisk DaaS synthesizes raw temporal signals into three institutional composite indices:

| Index | Name | Formula / Derivation | Fallback Behavior |
| :--- | :--- | :--- | :--- |
| **MCI** | **Maintainer Concentration Index** | Evaluates maintainer count and author churn (`1.0 - unique_authors/total_commits`). Yields `10.0` for single-maintainer packages. | Returns `"insufficient data"` if maintainer count is `null` — PyPI packages, where maintainer metadata is unverified, and any npm package whose registry record carries no maintainer array. Absent metadata is never substituted with a count of 1. |
| **DRI** | **Dormancy Reactivation Index** | Evaluates days since last publish vs historical publish cadence variance to detect unexpected reactivation after long quiet periods. | Returns `"insufficient data"` if `days_since_last_publish` or `publish_cadence_variance` is undefined ($n \le 1$ publish). |
| **ASI** | **Anomalous Spike Index** | Evaluates daily fork velocity relative to 30-day historical averages (`fork_spike_ratio`) combined with open issue deltas. | Returns `"insufficient data"` if `fork_spike_ratio` is `null`. |

---

## 🛠️ API Reference & Usage

### 1. Health Check
```bash
curl -X GET "https://agentrisk-daas.onrender.com/"
```
**Response:**
```json
{"status": "online"}
```

### 2. Advanced Risk Analytics
```bash
curl -X GET "https://agentrisk-daas.onrender.com/api/v1/analytics/package-risk/npm/example-mcp-server" \
  -H "X-API-Key: YOUR_API_KEY"
```

**Response Payload** — *illustrative. These values show field shapes and types; they are not a recorded response for any specific package.*
```json
{
  "package_name": "npm/example-mcp-server",
  "timestamp": "2026-07-27T00:00:00Z",
  "maintainer_concentration_index": 10.0,
  "dormancy_reactivation_index": "insufficient data",
  "anomalous_spike_index": 8.0,
  "maintainer_count": 1,
  "single_maintainer_flag": true,
  "days_since_last_publish": 2,
  "publish_cadence_variance": null,
  "fork_spike_ratio": 3.5
}
```

### 3. Cryptographic Merchant Webhook
```
POST /webhooks/lemon-squeezy
```
- **HMAC-SHA256**: Validates request signatures via `X-Signature`.
- **`subscription_created`**: Derives the raw key deterministically from `subscription_id`, persists its SHA-256 digest, and dispatches the raw key via Resend transactional email. Deterministic derivation makes webhook retries idempotent — a retry regenerates the identical key rather than minting a duplicate.
- **Delivery is enforced, not best-effort**: if the dispatch fails the endpoint returns HTTP 500 so Lemon Squeezy retries. A 2xx from this endpoint means the subscriber actually received their key.
- **`subscription_payment_success` / `subscription_updated`**: Reactivates the existing key without re-issuing it.
- **`subscription_cancelled` / `subscription_expired`**: Deactivates the API key (`is_active = False`) to prevent revenue leakage.

---

## 🏗️ System Topology & Infrastructure

```
[ Static Edge Gateway ] ──► [ Cloud Run / Render Compute ] ──► [ Serverless Storage ]
(Vercel Edge / Static)      (FastAPI / Uvicorn Docker)        (Neon PostgreSQL)
│                            │                                 │
▼                            ▼                                 ▼
[ Lemon Squeezy MoR ]    [ Upstash Redis Limiter ]        [ Scheduled Ingestion ]
(Air-Gapped Sub Billing) (60 req/min Sliding Window)      (GitHub Actions Cron)
```

---

## 🛡️ Security & Privacy Guardrails

- **Zero Hardcoded Secrets**: Secrets (`DATABASE_URL`, `REDIS_URL`, `RESEND_API_KEY`, `LEMON_SQUEEZY_WEBHOOK_SECRET`) are strictly loaded from host environment variables.
- **SHA-256 Hashed Keys**: Raw API keys (`daas_live_...`) are never stored in plain text; PostgreSQL stores SHA-256 digests.
- **Rate Limiting**: Atomic Redis Lua sliding-window token bucket (60 requests/60s).

---

## 🧪 Verification & Testing

Run full unit, integration, and E2E test suite locally:
```bash
pip install -r requirements-dev.txt
PYTHONPATH=. pytest
```
The suite also runs on every push and pull request via `.github/workflows/test.yaml`. It needs no secrets — `tests/conftest.py` supplies every required environment variable and no live service is contacted.

*Current Coverage*: **30/30 tests passing.**