#!/usr/bin/env bash
# Phase 2: the role both Lambdas run as. Least privilege: one small inline policy, no *FullAccess.
T="$(dirname "${BASH_SOURCE[0]}")/../../../tools/lib"; source "$T/common.sh"
load_project_config

cat > build/trust-policy.json <<'JSON'
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}
JSON

cat > build/lambda-policy.json <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "ReadWriteOurBucket", "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::${BUCKET}/*" },
    { "Sid": "ListOurBucket", "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::${BUCKET}" },
    { "Sid": "ConversationHistory", "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query"],
      "Resource": "arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT_ID}:table/${TABLE_NAME}" },
    { "Sid": "InvokeModels", "Effect": "Allow",
      "Action": ["bedrock:InvokeModel"],
      "Resource": ["arn:aws:bedrock:*::foundation-model/*",
                   "arn:aws:bedrock:*:${ACCOUNT_ID}:inference-profile/*"] }
  ]
}
JSON

if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  ok "role $ROLE_NAME already exists"
else
  step "Creating role $ROLE_NAME"
  aws iam create-role --role-name "$ROLE_NAME" --assume-role-policy-document file://build/trust-policy.json \
    --tags "Key=project,Value=$PROJECT" >/dev/null
  log "waiting 10s for IAM to propagate"; sleep 10
fi

step "Attaching policies"
aws iam attach-role-policy --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole      # CloudWatch Logs
aws iam put-role-policy --role-name "$ROLE_NAME" --policy-name "${PROJECT}-least-privilege" \
  --policy-document file://build/lambda-policy.json
ok "role ready"
aws iam list-attached-role-policies --role-name "$ROLE_NAME" --query 'AttachedPolicies[].PolicyName' --output text
aws iam list-role-policies --role-name "$ROLE_NAME" --query 'PolicyNames' --output text
