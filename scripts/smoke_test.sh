#!/usr/bin/env bash
# scripts/smoke_test.sh
#
# End-to-end smoke test against a running Unfolda stack.
#
# Two-token flow:
#   Step 1: JWT with {google_sub, email, name} → POST /auth/provision → user_id
#   Steps 2–6: JWT with {user_id} → all protected endpoints
#
# Prerequisites:
#   - Stack running (docker compose up or local uvicorn)
#   - NEXTAUTH_SECRET in environment or .env
#   - S3 accessible for upload confirm + precheck
#
# Usage:
#   ./scripts/smoke_test.sh [API_URL]
#   SMOKE_VERBOSE=1 ./scripts/smoke_test.sh
#
# Environment:
#   API_URL         Base URL (default: http://localhost:8000)
#   NEXTAUTH_SECRET JWT signing secret (read from .env if not set)
#   SMOKE_VERBOSE   Set to 1 for full response bodies

set -euo pipefail

API="${1:-${API_URL:-http://localhost:8000}}"
VERBOSE="${SMOKE_VERBOSE:-0}"
PASS_COUNT=0
FAIL_COUNT=0
FAILED_STEPS=()

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; NC='\033[0m'

pass_step() { echo -e "${GREEN}PASS${NC}  $1"; ((PASS_COUNT++)) || true; }
fail_step()  { echo -e "${RED}FAIL${NC}  $1: $2"; FAILED_STEPS+=("$1"); ((FAIL_COUNT++)) || true; }
skip_step()  { echo -e "${YELLOW}SKIP${NC}  $1: $2"; }
info()       { echo -e "${YELLOW}INFO${NC}  $*"; }
body()       { [[ "$VERBOSE" == "1" ]] && echo "       $*" || true; }

# ── Resolve NEXTAUTH_SECRET ───────────────────────────────────────────────────
if [[ -z "${NEXTAUTH_SECRET:-}" ]]; then
  if [[ -f .env ]]; then
    NEXTAUTH_SECRET=$(grep -E '^NEXTAUTH_SECRET=' .env | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")
  fi
fi
if [[ -z "${NEXTAUTH_SECRET:-}" ]]; then
  echo -e "${RED}ERROR${NC}  NEXTAUTH_SECRET not set and not found in .env"; exit 1
fi
export NEXTAUTH_SECRET

# ── Generate JWT helper (Python) ──────────────────────────────────────────────
make_jwt() {
  # $1 = JSON payload dict as Python literal
  python3 -c "
import jwt, time, os, sys
secret = os.environ['NEXTAUTH_SECRET']
payload = $1
payload.setdefault('exp', int(time.time()) + 3600)
print(jwt.encode(payload, secret, algorithm='HS256'))
"
}

# ── Create minimal test EPUB ──────────────────────────────────────────────────
EPUB_FILE=$(mktemp /tmp/smoke_test_XXXXXX.epub)
trap 'rm -f "$EPUB_FILE"' EXIT

python3 - <<PYEOF
import io, zipfile
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
    zf.writestr("mimetype", "application/epub+zip")
    zf.writestr("META-INF/container.xml",
        '<?xml version="1.0"?>'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        "<rootfiles>"
        '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
        "</rootfiles></container>")
    zf.writestr("OEBPS/content.opf",
        '<?xml version="1.0"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:title>Smoke Test Book</dc:title>"
        "<dc:creator>Smoke Test</dc:creator>"
        "<dc:language>en</dc:language>"
        "</metadata>"
        "<manifest>"
        '<item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>'
        "</manifest>"
        "<spine><itemref idref='ch1'/></spine>"
        "</package>")
    zf.writestr("OEBPS/ch1.xhtml",
        "<html><body><h1>Chapter One</h1>"
        "<p>The quick brown fox jumps over the lazy dog. "
        "This smoke test book contains enough English text for language "
        "detection to work correctly during the precheck step.</p>"
        "</body></html>")
with open("${EPUB_FILE}", "wb") as f:
    f.write(buf.getvalue())
PYEOF

info "Stack: $API"
info "EPUB:  $EPUB_FILE ($(wc -c < "$EPUB_FILE" | tr -d ' ') bytes)"
echo ""

# ── Helper: extract JSON field ────────────────────────────────────────────────
jfield() { python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('$1',''))" <<< "$2"; }
jcheck() {
  # jcheck <resp> <field> <expected>
  local val
  val=$(python3 -c "import json,sys; print(json.loads('''$1''').get('$2','__missing__'))" 2>/dev/null)
  [[ "$val" == "$3" ]]
}
jexists() {
  python3 -c "import json,sys; d=json.loads('''$1'''); sys.exit(0 if d.get('$2') else 1)" 2>/dev/null
}
jislist() {
  python3 -c "import json,sys; d=json.loads('''$1'''); sys.exit(0 if isinstance(d,list) else 1)" 2>/dev/null
}

# ── Step 1: POST /auth/provision ──────────────────────────────────────────────
echo "──────────────────────────────────────────────"
echo "Step 1  POST /auth/provision"
TIMESTAMP=$(date +%s)
PROVISION_JWT=$(make_jwt "{'google_sub':'smoke-sub-$TIMESTAMP','email':'smoke-$TIMESTAMP@smoke.test','name':'Smoke Test'}")
RESP1=$(curl -sf -X POST "$API/auth/provision" \
  -H "Authorization: Bearer $PROVISION_JWT" \
  -H "Content-Type: application/json" 2>&1) || RESP1=""

if jexists "$RESP1" "user_id"; then
  USER_ID=$(jfield "user_id" "$RESP1")
  pass_step "POST /auth/provision → user_id=${USER_ID:0:8}…"
  body "$RESP1"
else
  fail_step "POST /auth/provision" "Response: $RESP1"
  USER_ID=""
fi

# ── Build API JWT with user_id (for all protected endpoints) ──────────────────
if [[ -n "$USER_ID" ]]; then
  API_JWT=$(make_jwt "{'user_id':'$USER_ID'}")
  API_AUTH="Authorization: Bearer $API_JWT"
else
  API_AUTH="Authorization: Bearer invalid"
fi

# ── Step 2: POST /storage/artifacts ──────────────────────────────────────────
echo "──────────────────────────────────────────────"
echo "Step 2  POST /storage/artifacts"
TEMP_JOB_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
RESP2=$(curl -sf -X POST "$API/storage/artifacts" \
  -H "$API_AUTH" -H "Content-Type: application/json" \
  -d "{\"artifact_type\":\"source_epub\",\"job_id\":\"$TEMP_JOB_ID\",\"expires_in_seconds\":300}" 2>&1) || RESP2=""

ARTIFACT_ID=""; UPLOAD_URL=""
if jexists "$RESP2" "artifact_id" && jexists "$RESP2" "upload_url"; then
  ARTIFACT_ID=$(jfield "artifact_id" "$RESP2")
  UPLOAD_URL=$(jfield "upload_url" "$RESP2")
  pass_step "POST /storage/artifacts → artifact_id=${ARTIFACT_ID:0:8}…"
  body "$RESP2"
else
  fail_step "POST /storage/artifacts" "Response: $RESP2"
fi

# ── Step 3: PUT to presigned URL + POST /upload/confirm ──────────────────────
echo "──────────────────────────────────────────────"
echo "Step 3  PUT EPUB to S3, then POST /upload/confirm/$ARTIFACT_ID"
CONFIRMED=false
if [[ -n "$UPLOAD_URL" && -n "$ARTIFACT_ID" ]]; then
  PUT_CODE=$(curl -sf -o /dev/null -w "%{http_code}" \
    -X PUT "$UPLOAD_URL" \
    -H "Content-Type: application/epub+zip" \
    --data-binary "@$EPUB_FILE" 2>&1) || PUT_CODE="error"

  if [[ "$PUT_CODE" == "200" || "$PUT_CODE" == "204" ]]; then
    info "  PUT to S3 → HTTP $PUT_CODE"
    RESP3=$(curl -sf -X POST "$API/upload/confirm/$ARTIFACT_ID" \
      -H "$API_AUTH" -H "Content-Type: application/json" 2>&1) || RESP3=""

    if jexists "$RESP3" "content_sha256"; then
      SHA=$(jfield "content_sha256" "$RESP3")
      pass_step "POST /upload/confirm → sha256=${SHA:0:16}…"
      body "$RESP3"
      CONFIRMED=true
    else
      fail_step "POST /upload/confirm/$ARTIFACT_ID" "Response: $RESP3"
    fi
  else
    skip_step "PUT + /upload/confirm" "S3 PUT returned HTTP $PUT_CODE (check S3 config)"
  fi
else
  skip_step "PUT + /upload/confirm" "No upload URL from step 2"
fi

# ── Step 4: POST /precheck/{artifact_id} ─────────────────────────────────────
echo "──────────────────────────────────────────────"
echo "Step 4  POST /precheck/$ARTIFACT_ID"
WORD_COUNT=0
if [[ "$CONFIRMED" == "true" && -n "$ARTIFACT_ID" ]]; then
  RESP4=$(curl -sf -X POST "$API/precheck/$ARTIFACT_ID" \
    -H "$API_AUTH" -H "Content-Type: application/json" 2>&1) || RESP4=""

  PC_STATUS=$(python3 -c "import json; print(json.loads('''$RESP4''').get('status',''))" 2>/dev/null || echo "")
  if [[ "$PC_STATUS" == "completed" ]]; then
    PC_LANG=$(jfield "detected_language" "$RESP4")
    WORD_COUNT=$(jfield "word_count" "$RESP4")
    pass_step "POST /precheck → language=$PC_LANG word_count=$WORD_COUNT"
    body "$RESP4"
  elif [[ "$PC_STATUS" == "failed" ]]; then
    PC_ERR=$(jfield "error_code" "$RESP4")
    fail_step "POST /precheck/$ARTIFACT_ID" "status=failed error_code=$PC_ERR"
  else
    fail_step "POST /precheck/$ARTIFACT_ID" "Response: $RESP4"
  fi
else
  skip_step "POST /precheck" "No confirmed artifact from step 3"
fi

# ── Step 5: POST /jobs ────────────────────────────────────────────────────────
echo "──────────────────────────────────────────────"
echo "Step 5  POST /jobs"
[[ "$WORD_COUNT" -gt 0 ]] 2>/dev/null || WORD_COUNT=500
ART_FIELD="null"
[[ -n "$ARTIFACT_ID" ]] && ART_FIELD="\"$ARTIFACT_ID\""

RESP5=$(curl -sf -X POST "$API/jobs" \
  -H "$API_AUTH" -H "Content-Type: application/json" \
  -d "{
    \"mode\": \"translate\",
    \"target_language\": \"en\",
    \"source_language_override\": \"ru\",
    \"translation_style\": \"natural\",
    \"user_level\": \"B1\",
    \"explanation_depth\": \"standard\",
    \"source_artifact_id\": $ART_FIELD,
    \"word_count_estimate\": $WORD_COUNT,
    \"credit_estimate\": 0
  }" 2>&1) || RESP5=""

JOB_ID=""
if jcheck "$RESP5" "status" "queued"; then
  JOB_ID=$(jfield "job_id" "$RESP5")
  pass_step "POST /jobs → job_id=${JOB_ID:0:8}… status=queued"
  body "$RESP5"
else
  JOB_STATUS=$(python3 -c "import json; print(json.loads('''$RESP5''').get('status',''))" 2>/dev/null || echo "")
  fail_step "POST /jobs" "status='$JOB_STATUS' response: $RESP5"
fi

# ── Step 6: GET /jobs ─────────────────────────────────────────────────────────
echo "──────────────────────────────────────────────"
echo "Step 6  GET /jobs"
RESP6=$(curl -sf -X GET "$API/jobs" \
  -H "$API_AUTH" 2>&1) || RESP6=""

if jislist "$RESP6"; then
  NJOBS=$(python3 -c "import json; print(len(json.loads('''$RESP6''')))" 2>/dev/null || echo "?")
  if [[ -n "$JOB_ID" ]]; then
    IN_LIST=$(python3 -c "
import json, sys
jobs = json.loads('''$RESP6''')
ids = [j.get('job_id','') for j in jobs]
print('yes' if '$JOB_ID' in ids else 'no')
" 2>/dev/null || echo "no")
    if [[ "$IN_LIST" == "yes" ]]; then
      pass_step "GET /jobs → $NJOBS job(s), job_id present ✓"
    else
      fail_step "GET /jobs" "job_id=$JOB_ID not found in list of $NJOBS jobs"
    fi
  else
    pass_step "GET /jobs → $NJOBS job(s) returned"
  fi
  body "$RESP6"
else
  fail_step "GET /jobs" "Response: $RESP6"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════"
TOTAL=$((PASS_COUNT + FAIL_COUNT))
echo "  Results: $PASS_COUNT passed / $FAIL_COUNT failed (of $TOTAL executed steps)"
if [[ ${#FAILED_STEPS[@]} -gt 0 ]]; then
  echo "  Failed:  ${FAILED_STEPS[*]}"
fi
echo "══════════════════════════════════════════════"
echo ""

[[ $FAIL_COUNT -gt 0 ]] && exit 1 || exit 0
