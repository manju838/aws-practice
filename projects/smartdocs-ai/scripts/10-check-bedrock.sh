#!/usr/bin/env bash
# Phase 1: prove who you are, and which Claude + embedding models this account can actually call.
# Run this with your ADMIN credentials: the first call to a third-party model is what creates its
# AWS Marketplace subscription, and the Lambda role deliberately has no Marketplace permissions.
T="$(dirname "${BASH_SOURCE[0]}")/../../../tools/lib"; source "$T/common.sh"
load_project_config

step "Identity"
aws sts get-caller-identity --query Arn --output text
log "region: $AWS_REGION"

step "Anthropic inference profiles visible in $AWS_REGION"
aws bedrock list-inference-profiles \
  --query "inferenceProfileSummaries[?contains(inferenceProfileId,'anthropic')].[inferenceProfileId,status]" --output table

step "Calling each candidate chat model (Converse API)"
cat > build/converse-messages.json <<'JSON'
[{"role":"user","content":[{"text":"Reply with the single word: ready"}]}]
JSON
cat > build/converse-config.json <<'JSON'
{"maxTokens":20}
JSON
chat_ok=0
for model in $CANDIDATE_MODELS; do
  if out=$(aws bedrock-runtime converse --model-id "$model" \
        --messages file://build/converse-messages.json --inference-config file://build/converse-config.json \
        --query 'output.message.content[?text].text | [0]' --output text 2>&1); then
    ok "$model  ->  $out"
    [ "$model" = "$CHAT_MODEL_ID" ] && chat_ok=1
  else
    warn "$model  ->  FAILED: $(echo "$out" | tail -n 1 | cut -c1-200)"
    echo "$out" | grep -q "INVALID_PAYMENT_INSTRUMENT" && \
      log "   hint: AWS Marketplace -> Manage subscriptions: cancel failed Anthropic entries, fix the payment method, retry."
  fi
done

step "Embedding model ($EMBED_MODEL_ID)"
echo '{"inputText":"hello world"}' > build/embed-request.json
aws bedrock-runtime invoke-model --model-id "$EMBED_MODEL_ID" --body fileb://build/embed-request.json \
  --cli-binary-format raw-in-base64-out build/embed-response.json >/dev/null
dim="$(py -c "import json; print(len(json.load(open('build/embed-response.json'))['embedding']))")"
[ "$dim" = "1024" ] && ok "returned a $dim-dimensional vector" || die "expected 1024 dimensions, got $dim"

echo
[ "$chat_ok" = "1" ] && ok "CHAT_MODEL_ID ($CHAT_MODEL_ID) works. Phase 1 complete." \
  || die "CHAT_MODEL_ID ($CHAT_MODEL_ID) is not callable. Pick a working ID from above and set it in config.env."
