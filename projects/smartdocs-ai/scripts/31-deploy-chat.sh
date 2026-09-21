#!/usr/bin/env bash
# Phase 3: create or update the chat Lambda (the RAG loop that calls Claude).
T="$(dirname "${BASH_SOURCE[0]}")/../../../tools/lib"; source "$T/common.sh"; source "$T/lambda.sh"
load_project_config

write_env_json build/chat-env.json DOCS_BUCKET="$BUCKET" CONVERSATIONS_TABLE="$TABLE_NAME" \
  CHAT_MODEL_ID="$CHAT_MODEL_ID" EMBED_MODEL_ID="$EMBED_MODEL_ID" TEMPERATURE="${CHAT_TEMPERATURE:-}"
deploy_lambda "$CHAT_FN" src/chat lambda_function.lambda_handler 30 512 \
  build/chat-env.json "$(latest_layer_arn "$LAYER_NAME")"
