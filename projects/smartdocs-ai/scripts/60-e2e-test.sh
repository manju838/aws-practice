#!/usr/bin/env bash
# Phase 6: the whole product through the secured API:
#   request an upload URL -> PUT a PDF straight to S3 -> wait for indexing -> ask questions.
T="$(dirname "${BASH_SOURCE[0]}")/../../../tools/lib"; source "$T/common.sh"
load_project_config
need curl uv
[ -f build/cdk-outputs.json ] || die "Deploy first: scripts/40-cdk.sh deploy 6"

read -r CHAT_URL UPLOAD_URL SECRET_ARN BUCKET_CDK < <(py - <<'PY'
import json
o = next(iter(json.load(open("build/cdk-outputs.json")).values()))
print(o["ChatUrl"], o["UploadUrl"], o["ApiKeySecretArn"], o["BucketName"])
PY
)
KEY="$(aws secretsmanager get-secret-value --secret-id "$SECRET_ARN" --query SecretString --output text)"

step "Without an API key the API must refuse"
code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$UPLOAD_URL" -H 'Content-Type: application/json' -d '{"filename":"x.pdf"}')"
[ "$code" = "401" ] && ok "HTTP 401 without a key" || die "expected 401, got $code"

step "1/3  Ask for a presigned upload URL"
uv run python tests/make_sample_pdf.py build/nimbus-kettle-manual.pdf
resp="$(curl -s -X POST "$UPLOAD_URL" -H 'Content-Type: application/json' -H "x-api-key: $KEY" -d '{"filename":"nimbus-kettle-manual.pdf"}')"
put_url="$(echo "$resp" | py -c 'import json,sys; print(json.load(sys.stdin)["upload_url"])')"
log "key: $(echo "$resp" | py -c 'import json,sys; print(json.load(sys.stdin)["key"])')"

step "2/3  PUT the PDF straight to S3 (it never touches Lambda or API Gateway)"
code="$(curl -s -o /dev/null -w '%{http_code}' -X PUT "$put_url" -H 'Content-Type: application/pdf' --data-binary @build/nimbus-kettle-manual.pdf)"
[ "$code" = "200" ] && ok "HTTP 200 from S3" || die "upload failed with HTTP $code"

step "3/3  Wait for the indexer (its log group is created by the stack)"
sleep 20
aws s3 ls "s3://$BUCKET_CDK/index/"

"$(dirname "${BASH_SOURCE[0]}")/33-test-chat.sh" --cdk
