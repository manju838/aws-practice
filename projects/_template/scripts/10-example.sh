#!/usr/bin/env bash
# Example script showing the standard skeleton. Numbered by phase, safe to re-run.
source "$(dirname "${BASH_SOURCE[0]}")/../../../tools/lib/common.sh"
load_project_config

step "Who am I?"
aws sts get-caller-identity --query Arn --output text
log "project=$PROJECT region=$AWS_REGION bucket=$BUCKET"
ok "config loaded"
