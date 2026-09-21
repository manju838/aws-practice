#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# tools/lib/lambda.sh — create-or-update a Lambda function.
# Source AFTER common.sh (and after load_project_config).
#
#   deploy_lambda <name> <src_dir> <handler> <timeout_s> <memory_mb> <env_json_file> [layer_arn]
#
# Idempotent: creates the function the first time, updates code + config after.
# ─────────────────────────────────────────────────────────────────────

wait_lambda() {
  # An update in flight blocks the next call ("ResourceConflictException"), so wait.
  aws lambda wait function-updated --function-name "$1"
}

deploy_lambda() {
  local name="$1" src="$2" handler="$3" timeout="$4" memory="$5" env_file="$6" layer="${7:-}"
  local zip="build/${name}.zip"
  local layer_args=()
  [ -n "$layer" ] && layer_args=(--layers "$layer")

  step "Packaging $name from $src"
  make_zip "$src" "$zip"

  if aws lambda get-function --function-name "$name" >/dev/null 2>&1; then
    step "Updating existing function $name"
    aws lambda update-function-code --function-name "$name" --zip-file "fileb://$zip" >/dev/null
    wait_lambda "$name"
    aws lambda update-function-configuration \
        --function-name "$name" --handler "$handler" \
        --timeout "$timeout" --memory-size "$memory" \
        --environment "file://$env_file" ${layer_args[@]+"${layer_args[@]}"} >/dev/null
    wait_lambda "$name"
  else
    step "Creating function $name"
    local attempt out
    for attempt in 1 2 3 4 5 6; do
      if out=$(aws lambda create-function \
            --function-name "$name" --runtime python3.12 \
            --zip-file "fileb://$zip" --handler "$handler" \
            --role "$ROLE_ARN" --timeout "$timeout" --memory-size "$memory" \
            --environment "file://$env_file" ${layer_args[@]+"${layer_args[@]}"} \
            --tags "project=$PROJECT" 2>&1); then
        break
      fi
      # A brand-new IAM role takes several seconds to propagate. Retry, don't fail.
      if echo "$out" | grep -q "cannot be assumed"; then
        log "IAM role not propagated yet, retrying in 10s ($attempt/6)"
        sleep 10
      else
        die "$out"
      fi
      [ "$attempt" = 6 ] && die "Gave up waiting for the IAM role: $out"
    done
    aws lambda wait function-active --function-name "$name"
  fi
  ok "$name deployed"
}

# latest_layer_arn <layer_name>   -> ARN of the newest published version (dies if none)
latest_layer_arn() {
  local arn
  arn="$(aws lambda list-layer-versions --layer-name "$1" --query 'LayerVersions[0].LayerVersionArn' --output text 2>/dev/null || true)"
  { [ -n "$arn" ] && [ "$arn" != "None" ]; } || die "No published layer named '$1'. Run scripts/22-build-layer.sh first."
  echo "$arn"
}
