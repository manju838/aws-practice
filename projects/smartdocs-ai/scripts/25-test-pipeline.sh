#!/usr/bin/env bash
# Phase 2: upload a PDF and watch it get indexed.   usage: 25-test-pipeline.sh [path/to/file.pdf]
# With no argument it uses a generated sample manual full of made-up facts, so that later
# answers can only come from the document (Claude cannot know them).
T="$(dirname "${BASH_SOURCE[0]}")/../../../tools/lib"; source "$T/common.sh"
load_project_config

pdf="${1:-}"
if [ -z "$pdf" ]; then
  need uv
  uv run python tests/make_sample_pdf.py build/nimbus-kettle-manual.pdf
  pdf=build/nimbus-kettle-manual.pdf
fi
[ -f "$pdf" ] || die "no such file: $pdf"
name="$(basename "$pdf")"

step "Uploading $name to s3://$BUCKET/docs/"
aws s3 cp "$pdf" "s3://$BUCKET/docs/$name"

step "Waiting for the indexer (up to 2 min)"
for i in $(seq 1 24); do
  if aws logs tail "/aws/lambda/$INDEXER_FN" --since 10m --format short 2>/dev/null | grep -q "Index saved"; then
    ok "indexer finished"; break
  fi
  [ "$i" = 24 ] && die "no 'Index saved' log line after 2 minutes. Check: aws logs tail /aws/lambda/$INDEXER_FN"
  sleep 5
done
aws logs tail "/aws/lambda/$INDEXER_FN" --since 10m --format short | grep -E '"msg"' | tail -n 12

step "Index files in S3"
aws s3 ls "s3://$BUCKET/index/"
