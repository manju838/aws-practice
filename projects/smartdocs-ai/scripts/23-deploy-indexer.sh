#!/usr/bin/env bash
# Phase 2: create or update the indexer Lambda (PDF -> chunks -> embeddings -> FAISS index).
T="$(dirname "${BASH_SOURCE[0]}")/../../../tools/lib"; source "$T/common.sh"; source "$T/lambda.sh"
load_project_config

write_env_json build/indexer-env.json DOCS_BUCKET="$BUCKET" EMBED_MODEL_ID="$EMBED_MODEL_ID"
deploy_lambda "$INDEXER_FN" src/indexer lambda_function.lambda_handler 300 1024 \
  build/indexer-env.json "$(latest_layer_arn "$LAYER_NAME")"
