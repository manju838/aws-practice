#!/usr/bin/env bash
# Phases 3-6: ask real questions and CHECK the answers.   usage: 33-test-chat.sh [--cdk]
#   default : the hand-built API      (build/api-url.txt)
#   --cdk   : the CDK-deployed API    (build/cdk-outputs.json), sending the API key if there is one
#
# The sample manual is fictional, so the right answers can only come from retrieval.
T="$(dirname "${BASH_SOURCE[0]}")/../../../tools/lib"; source "$T/common.sh"
load_project_config
need curl

API_KEY="${API_KEY:-}"
if [ "${1:-}" = "--cdk" ]; then
  [ -f build/cdk-outputs.json ] || die "build/cdk-outputs.json not found. Deploy first: scripts/40-cdk.sh deploy"
  read -r URL SECRET_ARN < <(py - <<'PY'
import json
out = next(iter(json.load(open("build/cdk-outputs.json")).values()))
print(out["ChatUrl"], out.get("ApiKeySecretArn", "-"))
PY
)
  if [ -z "$API_KEY" ] && [ "$SECRET_ARN" != "-" ]; then
    API_KEY="$(aws secretsmanager get-secret-value --secret-id "$SECRET_ARN" --query SecretString --output text)"
  fi
else
  [ -f build/api-url.txt ] || die "build/api-url.txt not found. Run scripts/32-create-api.sh first."
  URL="$(cat build/api-url.txt)"
fi
SESSION="test-$(date +%s)"
failures=0

ask() {   # ask <question> <expected-substring or "-"> ; prints the answer, checks the substring
  local q="$1" expect="$2" body reply status answer
  body="$(py -c 'import json,sys; print(json.dumps({"question": sys.argv[1], "session_id": sys.argv[2]}))' "$q" "$SESSION")"
  reply="$(curl -s -w '\n%{http_code}' -X POST "$URL" -H 'Content-Type: application/json' \
            ${API_KEY:+-H "x-api-key: $API_KEY"} -d "$body")"
  status="$(echo "$reply" | tail -n 1)"; reply="$(echo "$reply" | sed '$d')"
  step "Q: $q   [HTTP $status]"
  echo "$reply" | py -c 'import json,sys; d=json.load(sys.stdin); print("    A:", d.get("answer") or d); print("    sources:", d.get("sources"), " model:", d.get("model"))' || echo "$reply"
  [ "$status" = "200" ] || { warn "expected HTTP 200"; failures=$((failures+1)); return; }
  answer="$(echo "$reply" | py -c 'import json,sys; print(json.load(sys.stdin)["answer"])')"
  if [ "$expect" != "-" ]; then
    if echo "$answer" | grep -qi -- "$expect"; then ok "answer contains '$expect'"
    else warn "answer does NOT contain '$expect'"; failures=$((failures+1)); fi
  fi
}

ask "How hot does the NK-4471 kettle get, and how fast?"      "87.5"
ask "How long is its warranty?"                               "26"        # follow-up: needs the history
ask "In which city was the company founded?"                  "Lisbon"
ask "What is the capital of Australia?"                       "-"         # not in the document: should decline

echo
[ "$failures" = 0 ] && ok "all checks passed" || die "$failures check(s) failed"
