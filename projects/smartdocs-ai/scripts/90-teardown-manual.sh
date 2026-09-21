#!/usr/bin/env bash
# Deletes everything the hand-built scripts (20-32) created, using the names in config.env.
# Used twice: (1) to wipe the old attempt before starting fresh, (2) before Phase 4, so the
# CDK stack can prove it rebuilds everything from code. Safe to re-run; skips what's missing.
# (CDK-created resources are removed with:  scripts/40-cdk.sh destroy)
T="$(dirname "${BASH_SOURCE[0]}")/../../../tools/lib"; source "$T/common.sh"
load_project_config

cat <<MSG
This will DELETE, in account $ACCOUNT_ID / $AWS_REGION:
  API Gateway       $API_NAME
  Lambda functions  $INDEXER_FN, $CHAT_FN  (+ their log groups)
  Lambda layer      $LAYER_NAME (all versions)
  DynamoDB table    $TABLE_NAME
  IAM role          $ROLE_NAME
  S3 bucket         $BUCKET  (every object and version inside it)
MSG
confirm "Really delete all of this?"

step "API Gateway"
for id in $(aws apigatewayv2 get-apis --query "Items[?Name=='$API_NAME'].ApiId" --output text); do
  [ "$id" = "None" ] && continue
  aws apigatewayv2 delete-api --api-id "$id" && ok "deleted API $id"
done

step "Lambda functions and log groups"
for fn in "$INDEXER_FN" "$CHAT_FN"; do
  aws lambda delete-function --function-name "$fn" 2>/dev/null && ok "deleted $fn" || log "$fn: not found"
  aws logs delete-log-group --log-group-name "/aws/lambda/$fn" 2>/dev/null || true
done

step "Lambda layer versions"
for v in $(aws lambda list-layer-versions --layer-name "$LAYER_NAME" --query 'LayerVersions[].Version' --output text 2>/dev/null); do
  [ "$v" = "None" ] && continue
  aws lambda delete-layer-version --layer-name "$LAYER_NAME" --version-number "$v" && ok "deleted layer version $v"
done

step "DynamoDB table"
aws dynamodb delete-table --table-name "$TABLE_NAME" >/dev/null 2>&1 && ok "deleting $TABLE_NAME" || log "not found"

step "S3 bucket"
if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo '{}' > build/empty-notification.json
  aws s3api put-bucket-notification-configuration --bucket "$BUCKET" --notification-configuration file://build/empty-notification.json
  log "emptying (all versions and delete markers)..."
  empty_versioned_bucket "$BUCKET"
  aws s3api delete-bucket --bucket "$BUCKET" && ok "deleted $BUCKET"
else
  log "not found"
fi

step "IAM role"
if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  for arn in $(aws iam list-attached-role-policies --role-name "$ROLE_NAME" --query 'AttachedPolicies[].PolicyArn' --output text); do
    aws iam detach-role-policy --role-name "$ROLE_NAME" --policy-arn "$arn"
  done
  for name in $(aws iam list-role-policies --role-name "$ROLE_NAME" --query 'PolicyNames' --output text); do
    aws iam delete-role-policy --role-name "$ROLE_NAME" --policy-name "$name"
  done
  aws iam delete-role --role-name "$ROLE_NAME" && ok "deleted $ROLE_NAME"
else
  log "not found"
fi

rm -f build/api-url.txt
echo; ok "teardown complete"
