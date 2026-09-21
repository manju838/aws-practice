#!/usr/bin/env bash
# usage: tools/doc-todos.sh
# Lists every TODO(result) placeholder still sitting in the project docs.
cd "$(dirname "${BASH_SOURCE[0]}")/.."
total=$(grep -rn --include='*.md' --exclude-dir=_template "TODO(result)" projects | wc -l | tr -d ' ')
grep -rn --include='*.md' --exclude-dir=_template "TODO(result)" projects | sed 's/^/  /'
echo
echo "$total result placeholder(s) left to fill in."
