#!/usr/bin/env bash
# Phases 4-6: drive the CDK app in infra/.
#   usage: 40-cdk.sh <bootstrap|synth|diff|deploy|destroy> [phase]      phase: 4 (default) | 5 | 6
# Phase 4 = storage + Lambdas + API.  5 adds monitoring.  6 adds API-key auth + upload endpoint.
# Python dependencies are handled by uv (see infra/cdk.json), so there is no venv to activate.
T="$(dirname "${BASH_SOURCE[0]}")/../../../tools/lib"; source "$T/common.sh"
load_project_config
need uv node
command -v cdk >/dev/null || die "CDK CLI missing. Install once with:  npm install -g aws-cdk"

action="${1:-}"; phase="${2:-4}"
[[ "$action" =~ ^(bootstrap|synth|diff|deploy|destroy)$ ]] || { sed -n '2,5p' "$0"; exit 1; }
[[ "$phase" =~ ^[456]$ ]] || die "phase must be 4, 5 or 6"

if [ "$action" != "bootstrap" ] && [ "$action" != "destroy" ] && [ ! -d layer/build/python ]; then
  die "Layer not built. Run scripts/22-build-layer.sh first (CDK packages layer/build/ as the Lambda layer)."
fi

export CDK_DEFAULT_ACCOUNT="$ACCOUNT_ID" CDK_DEFAULT_REGION="$AWS_REGION"
ctx=(-c "phase=$phase" -c "project=$PROJECT" -c "chat_model=$CHAT_MODEL_ID" -c "embed_model=$EMBED_MODEL_ID"
     -c "temperature=${CHAT_TEMPERATURE:-}" -c "alert_email=${ALERT_EMAIL:-}")

cd infra
case "$action" in
  bootstrap) cdk bootstrap "aws://$ACCOUNT_ID/$AWS_REGION" ;;
  synth)     cdk synth "${ctx[@]}" --quiet && ok "template synthesised (nothing deployed)" ;;
  diff)      cdk diff "${ctx[@]}" || true ;;
  deploy)    cdk deploy "${ctx[@]}" --outputs-file ../build/cdk-outputs.json ;;
  destroy)   confirm "Destroy the CDK stack and everything in it?"; cdk destroy "${ctx[@]}" --force; rm -f ../build/cdk-outputs.json ;;
esac
