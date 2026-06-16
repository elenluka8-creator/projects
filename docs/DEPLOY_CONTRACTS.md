# Deployment Contracts

This document defines deployment requirements, environment variables, infrastructure dependencies, and operational constraints for Unfolda.

Status: active
Last updated: 2026-04-16

---

## Purpose

This document captures what is needed to deploy and operate the system correctly. It complements `docs/ARCHITECTURE.md` with operationally-focused constraints that implementation must respect.

Agents read this document before planning or implementing any change that touches deployment, configuration, infrastructure, or operational behavior.

---

## Environment variables

### Required — API backend

| Variable | Purpose | Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg2://...` |
| `REDIS_URL` | Redis connection string | `redis://...` |
| `NEXTAUTH_SECRET` | Shared JWT signing secret (Next.js + FastAPI) | — |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key | — |
| `S3_BUCKET_NAME` | Object storage bucket | — |
| `S3_ENDPOINT_URL` | S3-compatible endpoint | — |
| `AWS_ACCESS_KEY_ID` | Storage credentials | — |
| `AWS_SECRET_ACCESS_KEY` | Storage credentials | — |
| `AWS_REGION` | Storage region | — |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | — |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | — |
| `ADMIN_EMAILS` | Comma-separated admin email allowlist | — |
| `INITIAL_CREDIT_GRANT` | Credits granted on registration | `100` |
| `RETENTION_WINDOW_DAYS` | File retention window in days | `30` |

### Required — worker

All API backend variables plus:

| Variable | Purpose | Default |
|---|---|---|
| `TRANSLATION_MODEL` | Default translation model (legacy fallback) | `claude-haiku-4-5-20251001` |
| `TRANSLATION_MODEL_EXPRESS` | Express tier model | — |
| `TRANSLATION_MODEL_STANDARD` | Standard tier model | — |
| `TRANSLATION_MODEL_PREMIUM` | Premium tier model | — |
| `TRANSLATION_MAX_RETRIES` | Max provider retries per batch | `3` |
| `TRANSLATION_MAX_TOKENS_RESPONSE` | Max tokens in provider response | `16384` |
| `TRANSLATION_REQUEST_TIMEOUT` | Provider request timeout (seconds) | `600` |

### Required — web frontend

| Variable | Purpose |
|---|---|
| `NEXTAUTH_SECRET` | Shared JWT signing secret |
| `NEXTAUTH_URL` | NextAuth.js base URL |
| `BACKEND_URL` | FastAPI backend URL |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |

### Optional — notifications

| Variable | Purpose | Default |
|---|---|---|
| `RESEND_API_KEY` | Resend email provider API key | — (disabled if absent) |
| `RESEND_FROM_ADDRESS` | From address for transactional email | `Unfolda <noreply@unfolda.app>` |
| `APP_BASE_URL` | Application base URL for email links | — |

---

## Infrastructure dependencies

| Component | Technology | Role |
|---|---|---|
| Web frontend | Next.js (Node.js) | User-facing SaaS application |
| API backend | FastAPI (Python) | Authenticated API, job management, signed URLs |
| Worker | Python (same codebase as API) | Pipeline execution |
| Database | PostgreSQL | Canonical state store |
| Queue broker | Redis | Execution signaling (non-canonical) |
| Object storage | S3-compatible | EPUB files and structured artifacts |
| LLM provider | Anthropic Claude | Translation stage only |
| Email provider | Resend (optional) | Job completion notifications |

---

## Database migrations

Migrations are managed by Alembic. Apply before deploying a new API or worker version:

```bash
alembic upgrade head
```

Migration files are in `alembic/versions/`. Each migration must be backward-compatible with the running worker version during deployment.

---

## Operational constraints

- The worker must not be deployed while a job is actively processing unless workers are drained first.
- PostgreSQL is the system of record. Redis may be cleared without data loss — jobs recover on worker restart via `startup_recovery`.
- Object storage keys follow the pattern: `users/{user_id}/jobs/{job_id}/{artifact_type}/{artifact_id}`.
- Files in object storage are deleted by the retention cleanup worker after `RETENTION_WINDOW_DAYS` past terminal state.
- The worker startup recovery process re-enqueues any stuck `leased` or `processing` runs on boot.

---

## Deployment checklist

Before deploying a new version:

- [ ] Run `alembic upgrade head` on the target database
- [ ] Verify all required environment variables are set in the deployment environment
- [ ] Confirm no active job runs are in `processing` state (or plan for startup recovery)
- [ ] Verify `TRANSLATION_MODEL_*` env vars match the intended model versions
