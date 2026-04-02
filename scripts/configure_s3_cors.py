#!/usr/bin/env python3
"""
Configure CORS on the S3/MinIO bucket so the browser can PUT files
directly to presigned upload URLs.

Reads configuration from environment variables (same set used by the API):
  S3_BUCKET_NAME       — bucket name (required)
  S3_ENDPOINT_URL      — custom endpoint, e.g. http://localhost:9000 for MinIO
  AWS_ACCESS_KEY_ID    — access key
  AWS_SECRET_ACCESS_KEY — secret key
  AWS_REGION           — region (default: us-east-1)

Usage:
  # Load vars from .env then run:
  source .env && python3 scripts/configure_s3_cors.py

  # Or pass vars inline:
  S3_BUCKET_NAME=unfolda-dev python3 scripts/configure_s3_cors.py
"""

import json
import os
import sys

import boto3
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BUCKET = os.environ.get("S3_BUCKET_NAME")
ENDPOINT = os.environ.get("S3_ENDPOINT_URL")  # None for real AWS
REGION = os.environ.get("AWS_REGION", "us-east-1")
KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
SECRET = os.environ.get("AWS_SECRET_ACCESS_KEY")

if not BUCKET:
    print("ERROR: S3_BUCKET_NAME is required.", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# CORS policy
#
# AllowedOrigins:
#   "*" covers all origins for MVP.
#   Tighten to specific origins (e.g. https://app.unfolda.com) before
#   production deployment.
#
# AllowedMethods: PUT for direct upload, GET for download link previews.
# AllowedHeaders: "*" required because presigned PUT URLs include
#   content-type and x-amz-* headers that vary per request.
# ExposeHeaders: ETag is needed by some S3 multipart upload clients.
# MaxAgeSeconds: 1 hour browser preflight cache.
# ---------------------------------------------------------------------------

CORS_CONFIG = {
    "CORSRules": [
        {
            "AllowedOrigins": [
                "http://localhost:3000",
                "http://localhost:3001",
                "*",
            ],
            "AllowedMethods": ["PUT", "GET", "HEAD"],
            "AllowedHeaders": ["*"],
            "ExposeHeaders": ["ETag"],
            "MaxAgeSeconds": 3600,
        }
    ]
}

# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

kwargs: dict = dict(region_name=REGION)
if ENDPOINT:
    kwargs["endpoint_url"] = ENDPOINT
if KEY_ID:
    kwargs["aws_access_key_id"] = KEY_ID
if SECRET:
    kwargs["aws_secret_access_key"] = SECRET

s3 = boto3.client("s3", **kwargs)

print(f"Bucket  : {BUCKET}")
print(f"Endpoint: {ENDPOINT or '(AWS default)'}")
print(f"Region  : {REGION}")
print()
print("CORS policy to apply:")
print(json.dumps(CORS_CONFIG, indent=2))
print()

try:
    s3.put_bucket_cors(
        Bucket=BUCKET,
        CORSConfiguration=CORS_CONFIG,
    )
    print("✓ CORS policy applied successfully.")
except ClientError as exc:
    code = exc.response["Error"]["Code"]
    msg = exc.response["Error"]["Message"]
    print(f"ERROR [{code}]: {msg}", file=sys.stderr)
    sys.exit(1)

# Verify
try:
    result = s3.get_bucket_cors(Bucket=BUCKET)
    rules = result.get("CORSRules", [])
    print(f"✓ Verified: {len(rules)} CORS rule(s) active on bucket.")
except ClientError as exc:
    print(f"WARNING: Could not verify CORS: {exc}", file=sys.stderr)
