#!/usr/bin/env bash
# Phase 4: the CDK stack has its OWN bucket (auto-named), so upload the sample manual there
# and wait until the indexer has written the index.
T="$(dirname "${BASH_SOURCE[0]}")/../../../tools/lib"; source "$T/common.sh"
load_project_config
need uv
[ -f build/cdk-outputs.json ] || die "Deploy first: scripts/40-cdk.sh deploy"
B="$(py -c "import json; print(next(iter(json.load(open('build/cdk-outputs.json')).values()))['BucketName'])")"

uv run python tests/make_sample_pdf.py build/nimbus-kettle-manual.pdf
step "Uploading to s3://$B/docs/"
aws s3 cp build/nimbus-kettle-manual.pdf "s3://$B/docs/nimbus-kettle-manual.pdf"

step "Waiting for index/faiss.index (up to 2 min)"
for i in $(seq 1 24); do
  aws s3api head-object --bucket "$B" --key index/faiss.index >/dev/null 2>&1 && { ok "index written"; aws s3 ls "s3://$B/index/"; exit 0; }
  sleep 5
done
die "index not written after 2 minutes. Look at the indexer's log group in CloudWatch."
