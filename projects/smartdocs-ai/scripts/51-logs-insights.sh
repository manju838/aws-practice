#!/usr/bin/env bash
# Phase 5: run CloudWatch Logs Insights queries from the terminal.
# Lambda's text log format wraps our JSON lines, so fields are pulled out with `parse`.
T="$(dirname "${BASH_SOURCE[0]}")/../../../tools/lib"; source "$T/common.sh"
load_project_config
[ -f build/cdk-outputs.json ] || die "Deploy first: scripts/40-cdk.sh deploy 5"
cat > build/print_results.py <<'PY'
import json, sys
for row in json.load(sys.stdin)["results"]:
    cells = [f'{c["field"].lstrip("@")}={c["value"]}' for c in row if c["field"] != "@ptr"]
    print("   ", "  ".join(cells))
PY
LOG_GROUP="$(py -c "import json; print(next(iter(json.load(open('build/cdk-outputs.json')).values()))['ChatLogGroup'])")"

run_query() {  # run_query <title> <query>
  step "$1"
  local now start qid status
  now="$(date +%s)"; start=$((now - 3600))
  qid="$(aws logs start-query --log-group-name "$LOG_GROUP" --start-time "$start" --end-time "$now" \
        --query-string "$2" --query queryId --output text)"
  for _ in $(seq 1 30); do
    status="$(aws logs get-query-results --query-id "$qid" --query status --output text)"
    [ "$status" = "Complete" ] && break; sleep 2
  done
  aws logs get-query-results --query-id "$qid" --output json | py build/print_results.py
}

run_query "Slowest requests (last hour)" '
filter @message like /Request complete/
| parse @message /"duration_ms": (?<duration_ms>[0-9]+)/
| parse @message /"session_id": "(?<session>[^"]*)"/
| parse @message /"chunks": (?<chunks>[0-9]+)/
| sort duration_ms desc | limit 5 | fields @timestamp, session, duration_ms, chunks'

run_query "Latency and token usage (last hour)" '
filter @message like /Request complete/
| parse @message /"duration_ms": (?<d>[0-9]+)/
| parse @message /"input_tokens": (?<tin>[0-9]+)/
| parse @message /"output_tokens": (?<tout>[0-9]+)/
| stats count() as requests, avg(d) as avg_ms, pct(d, 95) as p95_ms, sum(tin) as input_tokens, sum(tout) as output_tokens'

run_query "Errors (last hour)" '
filter @message like /Model call failed/ or @message like /Unauthorized/
| fields @timestamp, @message | sort @timestamp desc | limit 10'
