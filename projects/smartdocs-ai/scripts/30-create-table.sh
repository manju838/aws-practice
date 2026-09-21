#!/usr/bin/env bash
# Phase 3: conversation history. Lambda is stateless, so memory has to live somewhere.
# Key = session_id (which chat) + timestamp (order). TTL deletes old chats for free.
T="$(dirname "${BASH_SOURCE[0]}")/../../../tools/lib"; source "$T/common.sh"
load_project_config

if aws dynamodb describe-table --table-name "$TABLE_NAME" >/dev/null 2>&1; then
  ok "table $TABLE_NAME already exists"
else
  step "Creating $TABLE_NAME (pay-per-request)"
  aws dynamodb create-table --table-name "$TABLE_NAME" \
    --attribute-definitions AttributeName=session_id,AttributeType=S AttributeName=timestamp,AttributeType=N \
    --key-schema AttributeName=session_id,KeyType=HASH AttributeName=timestamp,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST --tags "Key=project,Value=$PROJECT" >/dev/null
  aws dynamodb wait table-exists --table-name "$TABLE_NAME"
fi
step "Enabling TTL on the 'ttl' attribute"
aws dynamodb update-time-to-live --table-name "$TABLE_NAME" \
  --time-to-live-specification Enabled=true,AttributeName=ttl >/dev/null 2>&1 || log "(TTL was already enabled)"
aws dynamodb describe-table --table-name "$TABLE_NAME" --query "Table.[TableName,TableStatus,BillingModeSummary.BillingMode]" --output text
