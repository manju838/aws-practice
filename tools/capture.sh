#!/usr/bin/env bash
# usage: tools/capture.sh <project> <name> <command...>
#
# Runs the command from the project folder, shows the output live, and saves a
# REDACTED copy to projects/<project>/results/<name>.txt for the docs to link to.
#   tools/capture.sh smartdocs-ai 25-index-files aws s3 ls s3://my-bucket/index/
# For pipes or &&, wrap in bash -c '...'.
#
# Redacted automatically: 12-digit account IDs, access key IDs, API Gateway ids,
# and x-api-key values. Still eyeball the file before you commit it.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL="*"

project="${1:-}"; name="${2:-}"; shift 2 2>/dev/null || true
[ -n "$project" ] && [ -n "$name" ] && [ $# -gt 0 ] || { sed -n '2,11p' "$0"; exit 1; }
[ -d "projects/$project" ] || { echo "No such project: projects/$project"; exit 1; }

out="projects/$project/results/$name.txt"
mkdir -p "projects/$project/results"
cd "projects/$project"
out="results/$name.txt"

redact() {
  sed -E \
    -e 's/(^|[^0-9])[0-9]{12}([^0-9]|$)/\1<ACCOUNT_ID>\2/g' \
    -e 's/(^|[^0-9])[0-9]{12}([^0-9]|$)/\1<ACCOUNT_ID>\2/g' \
    -e 's/(AKIA|ASIA)[0-9A-Z]{16}/<ACCESS_KEY_ID>/g' \
    -e 's#https://[a-z0-9]+\.execute-api\.#https://<api-id>.execute-api.#g' \
    -e 's#(execute-api:[a-z0-9-]+:<ACCOUNT_ID>:)[a-z0-9]+#\1<api-id>#g' \
    -e 's/([Xx]-[Aa]pi-[Kk]ey:? *)[A-Za-z0-9_-]{8,}/\1<API_KEY>/g'
}

{
  printf '$ %s\n' "$*"
  printf '# captured %s (account IDs, keys and API ids redacted)\n\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} | redact > "$out"           # the command line itself can contain secrets too

"$@" 2>&1 | tee >(redact >> "$out")
status=${PIPESTATUS[0]}
sleep 0.3   # let the redaction subshell finish flushing
echo
echo "saved -> projects/$project/$out   (exit status $status)"
exit "$status"
