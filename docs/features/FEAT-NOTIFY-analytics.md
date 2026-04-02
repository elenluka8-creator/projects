## Analytics Specification

**Feature:** FEAT-NOTIFY — Job Completion Email Notification
**Prepared for:** Architect and Builder
**Related tasks:** TASK-78, TASK-79, TASK-80, TASK-81

---

### Analytics Goal

Measure whether notification emails are successfully dispatched when jobs reach the `completed` terminal state, track the dispatch failure rate and failure classification by cause, and monitor the locale distribution of outbound notifications — to verify that the notification pipeline is operating correctly, detect configuration issues (missing API key, broken templates), and understand which UI locales are active among completing users.

---

### Events

#### Event: `notification_dispatched`

**Pipeline stage:** export (emitted in worker completion handler, after pipeline stages conclude and credit settlement completes)

**Trigger:** The worker's completed-state handler invokes the notification service for a job that has just transitioned to `completed`. Fires exactly once per job completion, regardless of whether the send succeeds or fails. Does not fire for `failed` or `cancelled` terminal states.

**Properties:**
- `event`: string — always `"notification_dispatched"`
- `timestamp`: ISO8601 — when the notification attempt concludes
- `job_id`: string — UUID of the completed job
- `user_id`: string — UUID of the job owner (not their email address)
- `ui_locale`: string — the resolved locale used for the email template, after fallback (always a value from `SUPPORTED_LOCALES`; never null)
- `locale_source`: enum["stored", "fallback"] — `"stored"` if `jobs.ui_locale` was a valid supported locale; `"fallback"` if `jobs.ui_locale` was null or an unsupported value and the system fell back to `"en"`
- `success`: bool — `true` if the Resend API accepted the request; `false` for any error
- `failure_reason`: enum["api_key_missing", "template_error", "http_error", "unknown"] | null — null when `success` is `true`; set to the applicable class on failure
- `duration_ms`: int — total time for the notification service call in milliseconds, from entry to return, including template rendering and HTTP round-trip; 0 when the call aborts before reaching the HTTP layer

**Example payload (success):**
```json
{
  "event": "notification_dispatched",
  "timestamp": "2026-03-28T14:23:01Z",
  "job_id": "a1b2c3d4-0000-0000-0000-000000000001",
  "user_id": "u1u2u3u4-0000-0000-0000-000000000001",
  "ui_locale": "ru",
  "locale_source": "stored",
  "success": true,
  "failure_reason": null,
  "duration_ms": 312
}
```

**Example payload (failure — API key missing):**
```json
{
  "event": "notification_dispatched",
  "timestamp": "2026-03-28T14:23:02Z",
  "job_id": "a1b2c3d4-0000-0000-0000-000000000002",
  "user_id": "u1u2u3u4-0000-0000-0000-000000000002",
  "ui_locale": "en",
  "locale_source": "fallback",
  "success": false,
  "failure_reason": "api_key_missing",
  "duration_ms": 0
}
```

---

### Event Schema

#### `notification_dispatched`

```json
{
  "event": "string",
  "timestamp": "ISO8601",
  "job_id": "string",
  "user_id": "string",
  "ui_locale": "string",
  "locale_source": "enum[stored, fallback]",
  "success": "bool",
  "failure_reason": "enum[api_key_missing, template_error, http_error, unknown] | null",
  "duration_ms": "int"
}
```

All fields are required. `failure_reason` is `null` when `success` is `true`; it must be a non-null enum value when `success` is `false`.

---

### Metrics

**Product metrics:**
- `notification_delivery_rate`
  definition: count(notification_dispatched where success=true) / count(notification_dispatched)
  source: `notification_dispatched`

- `locale_distribution`
  definition: count(notification_dispatched) grouped by ui_locale — shows which UI locales are active among completing users
  source: `notification_dispatched`

- `locale_fallback_rate`
  definition: count(notification_dispatched where locale_source="fallback") / count(notification_dispatched)
  source: `notification_dispatched`

**Quality metrics:**
- `notification_failure_breakdown`
  definition: count(notification_dispatched where success=false) grouped by failure_reason — identifies the dominant failure class for triage
  source: `notification_dispatched`

**System metrics:**
- `avg_notification_latency_ms`
  definition: avg(duration_ms) from notification_dispatched where success=true
  source: `notification_dispatched`

- `notification_volume`
  definition: count(notification_dispatched) per hour — operational throughput; should equal completed job rate
  source: `notification_dispatched`

---

### Instrumentation Requirements

Builder must:
- Emit `notification_dispatched` exactly once per job in the worker's completed-state handler, after credit settlement and after the notification service call returns (success or failure).
- Set `job_id` from the current job's UUID.
- Set `user_id` from the job owner's UUID. Do not include the user's email address.
- Set `ui_locale` to the resolved locale value used for template selection — the value after fallback logic has been applied, never null.
- Set `locale_source` to `"stored"` when `jobs.ui_locale` was a valid value from `SUPPORTED_LOCALES`; set to `"fallback"` when `jobs.ui_locale` was null or an unsupported value and `"en"` was substituted.
- Set `success` to `true` if the Resend API returned a 2xx response; `false` for any exception or non-2xx response.
- Set `failure_reason` to `null` on success. On failure, classify as:
  - `"api_key_missing"` — `RESEND_API_KEY` is absent or empty
  - `"template_error"` — Jinja2 template rendering raised an exception
  - `"http_error"` — httpx raised an exception or Resend returned a non-2xx status
  - `"unknown"` — any other exception class
- Set `duration_ms` to the elapsed milliseconds for the entire notification service call. Use `0` when the call aborts before attempting the HTTP request (e.g. `api_key_missing`, `template_error`).
- Emit the event using `log_structured` via the existing `app/analytics/events.py` pattern (fire-and-forget; exceptions in event emission must not propagate).
- The event must not fire for `failed` or `cancelled` terminal states.
- The event must not contain raw book text, the user's email address, or any other PII beyond `user_id`.
- The notification service call must remain non-fatal: the analytics event is emitted regardless of the outcome, and neither a failed send nor a failed analytics emit may affect the job terminal state or credit settlement.

---

### Validation Rules

Analytics Validator must verify:
- `notification_dispatched` is emitted exactly once per job that reaches `completed` state.
- `notification_dispatched` is NOT emitted for `failed` or `cancelled` terminal states.
- `ui_locale` is a non-null, non-empty string and is always a value from `SUPPORTED_LOCALES` (never the raw null or unsupported value from `jobs.ui_locale`).
- `locale_source` is either `"stored"` or `"fallback"` — no other values.
- When `jobs.ui_locale` is null or unsupported, `locale_source` is `"fallback"` and `ui_locale` is `"en"`.
- When `jobs.ui_locale` is a valid supported locale, `locale_source` is `"stored"` and `ui_locale` matches `jobs.ui_locale`.
- `success` is `true` when the Resend API responds with a 2xx status; `false` for all other outcomes.
- `failure_reason` is `null` when `success` is `true`.
- `failure_reason` is a non-null enum value (`"api_key_missing"`, `"template_error"`, `"http_error"`, or `"unknown"`) when `success` is `false`.
- `duration_ms` is a non-negative integer.
- `duration_ms` is `0` when `failure_reason` is `"api_key_missing"` or `"template_error"` (no HTTP call was made).
- `job_id` and `user_id` are valid UUID strings.
- No PII fields are present in the payload — specifically, no `email` field and no raw book content.
- `timestamp` is a valid ISO8601 string.
- Emission failures are caught and do not propagate; a failed analytics emit must not alter the job's terminal state.

---

### Assumptions Made

- The existing `log_structured` infrastructure in `app/logging/structured.py` and the `emit_event` pattern in `app/analytics/events.py` are reused for `notification_dispatched`. No new analytics infrastructure is required.
- `duration_ms` is measured using a monotonic clock inside the notification service wrapper, not derived from Resend response headers.
- The `failure_reason` classification is applied inside the notification service boundary (in `notifications/email_client.py` or its caller), before the analytics event is emitted, so the worker's completed handler receives a structured result rather than a raw exception.
- Locale resolution logic (fallback to `"en"`) is part of the notification service and occurs before template selection. The resolved locale and its source are returned to the caller so the analytics event can record them accurately.
- `RESEND_API_KEY` absence is detectable before any HTTP call is made, allowing accurate classification as `"api_key_missing"` with `duration_ms` of `0`.
