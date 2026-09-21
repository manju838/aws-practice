#!/usr/bin/env bash
# Phase 2: tell S3 to invoke the indexer when a .pdf lands in docs/ (and ONLY there: a trigger
# on index/ would make the indexer fire on its own output, forever).
T="$(dirname "${BASH_SOURCE[0]}")/../../../tools/lib"; source "$T/common.sh"
load_project_config

FN_ARN="arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:${INDEXER_FN}"

step "1/2  Let S3 (this bucket, this account) invoke the indexer"
aws lambda remove-permission --function-name "$INDEXER_FN" --statement-id s3-invoke 2>/dev/null || true
aws lambda add-permission --function-name "$INDEXER_FN" --statement-id s3-invoke \
  --action lambda:InvokeFunction --principal s3.amazonaws.com \
  --source-arn "arn:aws:s3:::$BUCKET" --source-account "$ACCOUNT_ID" >/dev/null

step "2/2  Tell S3 when to call it: ObjectCreated, prefix docs/, suffix .pdf"
cat > build/s3-notification.json <<JSON
{ "LambdaFunctionConfigurations": [ {
    "LambdaFunctionArn": "${FN_ARN}",
    "Events": ["s3:ObjectCreated:*"],
    "Filter": { "Key": { "FilterRules": [
      { "Name": "prefix", "Value": "docs/" },
      { "Name": "suffix", "Value": ".pdf" } ] } } } ] }
JSON
aws s3api put-bucket-notification-configuration --bucket "$BUCKET" \
  --notification-configuration file://build/s3-notification.json
ok "trigger attached"
