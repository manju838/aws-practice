#!/usr/bin/env bash
# Phase 3: a public HTTPS front door: POST /chat -> chat Lambda. Throttled from day one.
T="$(dirname "${BASH_SOURCE[0]}")/../../../tools/lib"; source "$T/common.sh"
load_project_config

API_ID="$(aws apigatewayv2 get-apis --query "Items[?Name=='$API_NAME'].ApiId | [0]" --output text)"
if [ -n "$API_ID" ] && [ "$API_ID" != "None" ]; then
  ok "API $API_NAME already exists ($API_ID); reusing it"
else
  FN_ARN="arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:${CHAT_FN}"

  step "1/5  HTTP API (cheaper and faster than REST API for Lambda backends)"
  cat > build/cors.json <<'JSON'
{"AllowOrigins":["*"],"AllowMethods":["POST","OPTIONS"],"AllowHeaders":["Content-Type","x-api-key"]}
JSON
  API_ID="$(aws apigatewayv2 create-api --name "$API_NAME" --protocol-type HTTP \
    --cors-configuration file://build/cors.json \
    --tags "project=$PROJECT" --query ApiId --output text)"

  step "2/5  Lambda proxy integration"
  INTEGRATION_ID="$(aws apigatewayv2 create-integration --api-id "$API_ID" --integration-type AWS_PROXY \
    --integration-uri "$FN_ARN" --payload-format-version 2.0 --query IntegrationId --output text)"

  step "3/5  Route POST /chat"
  aws apigatewayv2 create-route --api-id "$API_ID" --route-key "POST /chat" \
    --target "integrations/$INTEGRATION_ID" >/dev/null

  step "4/5  Stage 'prod', throttled to 5 req/s (burst 10). It is public and calls a paid model."
  aws apigatewayv2 create-stage --api-id "$API_ID" --stage-name prod --auto-deploy \
    --default-route-settings ThrottlingBurstLimit=10,ThrottlingRateLimit=5 >/dev/null

  step "5/5  Let API Gateway invoke the Lambda"
  aws lambda remove-permission --function-name "$CHAT_FN" --statement-id apigateway-invoke 2>/dev/null || true
  aws lambda add-permission --function-name "$CHAT_FN" --statement-id apigateway-invoke \
    --action lambda:InvokeFunction --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:${AWS_REGION}:${ACCOUNT_ID}:${API_ID}/*/*" >/dev/null
fi

URL="https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/prod/chat"
echo "$URL" > build/api-url.txt
ok "endpoint saved to build/api-url.txt (not committed; it's in .gitignore)"
echo "    $URL"
