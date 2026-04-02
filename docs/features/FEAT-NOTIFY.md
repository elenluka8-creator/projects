# Feature: FEAT-NOTIFY — Job Completion Email Notification

---

## Metadata

```
feature_id:    FEAT-NOTIFY
capability:    JOBS (cross-cutting with QUEUE, AUTH)
status:        draft
priority:      high
created_by:    Product
created_at:    2026-03-28
related_prd:   §Job Lifecycle
pipeline_stage: cross-cutting
```

---

## Summary

When a user's translation job reaches the `completed` terminal state, the system sends
a transactional email to the user's registered address. The email is written in the
user's UI language (the locale active in the browser when the job was submitted) and
contains a direct link to the jobs page where the output EPUB can be downloaded.

Email dispatch is a non-fatal side effect of job completion. A failed email send must
never fail or delay the job. The email provider is Resend, called via raw `httpx`
(no additional Python package required if `httpx` is already a project dependency).

---

## Problem

Processing a book takes minutes to hours. Users must either keep the browser tab open
or repeatedly return to check the jobs page. There is no current mechanism to notify
them when processing finishes. This increases abandonment and reduces perceived
reliability — users who close the tab often forget to return.

---

## Goals

1. Notify the user by email as soon as their translation job is complete.
2. Include a direct link to the jobs page so the user can download immediately.
3. Write the email in the user's UI language (the locale they used when submitting).
4. Never fail or delay the job due to email errors.

---

## Non-Goals

- Email notification for `failed` jobs (out of scope for MVP; see Optional Follow-ups).
- Email notification for `cancelled` jobs.
- HTML email templates (plain-text only for MVP).
- Unsubscribe / email preference management.
- Email open or click tracking.
- Queued or retry logic for failed email sends (fire-and-forget).
- Using the job's *target language* (the language being translated into) as the email
  language proxy. This is explicitly rejected — see Locale Decision below.

---

## Locale Decision

### Problem

To send the email in the user's UI language, the system must know which locale the user
had active at the time of submission. There are two candidate approaches:

**Approach A — Store `preferred_locale` on `users` table.**
Add a `preferred_locale` column to `users`; update it whenever the user navigates to a
different locale. This requires the frontend to emit a locale-change API call on every
URL change and adds ongoing maintenance surface.

**Approach B — Capture `ui_locale` on the `jobs` table at submission time.**
When the user submits a job, the Next.js frontend already knows the active locale from
the URL path (e.g. `/ru/upload` → `"ru"`). Pass it as a field in the job creation
request and store it in a new nullable `jobs.ui_locale` column. This is a one-time
capture requiring no ongoing tracking.

### Decision: Approach B — `jobs.ui_locale` captured at submission

**Justification:**

- The target language of translation is not the same as the UI language. A native
  Russian speaker learning English would have target language `"en"` but UI locale
  `"ru"`. Using the target language as a proxy would produce emails in the wrong
  language in many real cases.
- Approach A requires ongoing frontend → backend locale-sync calls on every navigation,
  adding complexity and a new API contract with no other benefit.
- Approach B captures the locale once, at the moment it is most naturally known
  (job submission), with a single nullable column on `jobs` and a single frontend
  field addition to the job creation payload.
- Fallback to `"en"` for existing jobs (where `ui_locale` is null) and for any
  unsupported locale value that may slip through validation.

---

## User Flow

1. User submits a job from locale `"ru"`. The job creation request includes
   `ui_locale: "ru"`. The backend stores it on the `jobs` row.
2. The worker processes the job. On reaching `completed` terminal state, after credit
   settlement, the worker calls the notification service.
3. The notification service loads the `ru` Jinja2 template, renders it with
   `display_name`, `book_title`, and the jobs page URL
   (`{APP_BASE_URL}/ru/jobs`), and calls the Resend API via httpx.
4. The user receives an email in Russian with a link to their jobs page.
5. Any exception in steps 3–4 is caught, logged at WARNING level, and the job
   proceeds normally.

---

## Functional Requirements

- The system must send a plain-text email when a job transitions to the `completed`
  terminal state.
- Email must be addressed to the `email` field of the authenticated `user` who owns
  the job.
- The email language is determined by `jobs.ui_locale`. If `ui_locale` is null or
  contains a value not in `SUPPORTED_LOCALES`, the system falls back to `"en"`.
- The jobs page link in the email must be: `{APP_BASE_URL}/{locale}/jobs` where
  `locale` is the resolved locale (after fallback).
- Email subject and body must both be in the resolved locale.
- `RESEND_API_KEY` must be read from environment; never hardcoded.
- `RESEND_FROM_EMAIL` must be read from environment; never hardcoded.
- `APP_BASE_URL` must be read from environment; never hardcoded.
- Email sending must be non-fatal: exceptions are caught at the notification boundary,
  logged at WARNING level with `job_id`, and do not propagate.
- The email must contain no raw book content (text extracted from the EPUB). It may
  contain `jobs.title` (the book's title metadata) as it is not book text.
- Supported locales for email templates: `en`, `ru`, `sr`, `de`, `fr`, `es`, `it`,
  `pt`, `zh`, `ja`, `ko`, `tr`, `nl`, `pl` (14 locales matching `SUPPORTED_LANGUAGES`
  in `app/config/policy.py`).

---

## MVP Slice

Send a plain-text email in the user's submission locale when a job completes. The email
contains a direct link to the jobs page. Email failure is never fatal to the job.
All 14 supported locales have a template. `ui_locale` is captured on job submission.
No HTML templates, no failure-state emails, no retry logic for failed sends.

---

## Constraints

- Must follow the architecture defined in `docs/ARCHITECTURE.md`.
- Email dispatch must not block the worker's terminal-state path.
- Raw book text must not appear in any email payload or log line (per DEC-004,
  `POLICY-PRIVACY`).
- No new Python packages if `httpx` is already in project dependencies. If `httpx` is
  not present, it is an approved addition (HTTP client only, no transitive bloat).
- `RESEND_API_KEY` must be treated as a secret and documented in `.env.example`.
- Changes to the `jobs` table must use an Alembic migration.
- The `jobs.ui_locale` column must be nullable and backward-compatible with existing
  job rows.

---

## Open Questions

1. Is `httpx` already in the Python `requirements.txt`? If not, confirm it may be
   added. (Assumption: yes, based on Discovery findings.)
2. Is there a confirmed `APP_BASE_URL` env var already defined, or must it be added?
   Builder should check `.env.example` before creating a new one.
3. Should the email include the job ID (for support reference)? Not included in MVP;
   can be added to templates without a schema change if decided later.

---

## Risks

- **Resend deliverability**: Resend requires a verified sender domain. `RESEND_FROM_EMAIL`
  must use a domain verified in the Resend dashboard before production use. This is an
  operational prerequisite, not a code risk.
- **Template quality**: Machine-translated templates for 14 languages need review by
  a native speaker for production. For MVP launch, English-reviewed templates are
  acceptable; others should be marked as needing review.
- **Email to wrong locale**: If the frontend does not pass `ui_locale` in the job
  creation payload, the fallback to `"en"` applies. This is safe but degrades UX for
  non-English speakers. Acceptance criteria must verify the frontend passes the field.
- **`jobs` table migration**: The migration is additive (nullable column) and backward-
  compatible, but it must be tested against a real schema to confirm no ORM conflicts.

---

## Success Criteria

- A user who submits a job from the `/ru/jobs` locale receives a completion email in
  Russian with a link to `/ru/jobs`.
- A user who submits a job from the `/en/jobs` locale receives a completion email in
  English.
- An email failure (simulated by mocking httpx to raise) does not change the job's
  terminal state or the credit settlement outcome.
- The `jobs.ui_locale` column is present after the migration and accepts null.
- Job creation with `ui_locale: "de"` stores `"de"` on the row.
- Job creation with no `ui_locale` field stores null.
- All 14 locale templates render without Jinja2 errors.
- `RESEND_API_KEY` is absent → notification service logs a warning and returns without
  sending (does not raise).

---

## Tasks

- TASK-78 — Add `ui_locale` to `jobs` table and job creation API `[MVP]`
- TASK-79 — Implement Resend email client module `[MVP]`
- TASK-80 — Create plain-text Jinja2 email templates for 14 locales `[MVP]`
- TASK-81 — Integrate notification dispatch into worker job completion handler `[MVP]`
