#!/usr/bin/env bash
# Phase 5: create some real traffic so the dashboard and Logs Insights have something to show:
# 12 good questions across 3 sessions, 1 bad request (HTTP 400), 1 request with a wrong API key.
T="$(dirname "${BASH_SOURCE[0]}")/../../../tools/lib"; source "$T/common.sh"
load_project_config
need curl
[ -f build/cdk-outputs.json ] || die "Deploy first: scripts/40-cdk.sh deploy 5"

read -r URL SECRET_ARN < <(py - <<'PY'
import json
out = next(iter(json.load(open("build/cdk-outputs.json")).values()))
print(out["ChatUrl"], out.get("ApiKeySecretArn", "-"))
PY
)
KEY=""; [ "$SECRET_ARN" != "-" ] && KEY="$(aws secretsmanager get-secret-value --secret-id "$SECRET_ARN" --query SecretString --output text)"

post() {  # post <body> <key>
  curl -s -o /dev/null -w '%{http_code} ' -X POST "$URL" -H 'Content-Type: application/json' -H "x-api-key: $2" -d "$1"
}

step "12 good requests"
qs=("What temperature does the NK-4471 reach?" "How long is the warranty?" "Who founded the company?"
    "What is the safety valve pressure?" "How often should I descale it?" "What colours does it come in?")
for i in $(seq 0 11); do
  post "{\"question\": \"${qs[$((i % 6))]}\", \"session_id\": \"traffic-$((i % 3))\"}" "$KEY"
done; echo
step "1 bad request (expect 400)"
post '{"question": ""}' "$KEY"; echo
step "1 request with a wrong API key (expect 401 if phase 6 is deployed, else 200)"
post '{"question": "hello"}' "wrong-key"; echo
ok "done. Give CloudWatch a minute, then open the dashboard (see the DashboardUrl stack output)."
