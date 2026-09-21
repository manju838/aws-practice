#!/usr/bin/env bash
# usage: tools/new-project.sh <folder-name> "<Title>"
# Scaffolds projects/<folder-name> from projects/_template and registers the nav tab.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

name="${1:-}"; title="${2:-}"
[[ "$name" =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo "usage: tools/new-project.sh <folder-name> \"<Title>\"   (folder: lowercase letters, digits, hyphens)"; exit 1; }
[ -n "$title" ] || { echo "Give the project a title, e.g. \"Step Functions ETL\""; exit 1; }
[ ! -e "projects/$name" ] || { echo "projects/$name already exists"; exit 1; }
PY="$(command -v python3 || command -v python)"

cp -R projects/_template "projects/$name"

# replace __PROJECT__ / __TITLE__ tokens in every text file of the copy
"$PY" - "projects/$name" "$name" "$title" <<'PY'
import os, sys
root, name, title = sys.argv[1:4]
for d, _, files in os.walk(root):
    for f in files:
        p = os.path.join(d, f)
        try:
            s = open(p, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        if "__PROJECT__" in s or "__TITLE__" in s:
            open(p, "w", encoding="utf-8", newline="\n").write(s.replace("__PROJECT__", name).replace("__TITLE__", title))
PY
chmod +x "projects/$name"/scripts/*.sh 2>/dev/null || true

cat >> _data/projects.yml <<YML
- title: $title
  tab: $title
  url: /projects/$name/
  status: planned
  summary: One sentence on what this project does.
  services: []
YML

cat <<MSG

Created projects/$name and registered the tab "$title" in _data/projects.yml.

Next:
  cd projects/$name
  cp config.env.example config.env      # set PROJECT and AWS_REGION
  edit README.md and 00-background.md   # the what and the why
  copy 01-phase-template.md to add phases (01-..., 02-...)
  edit _data/projects.yml               # summary + services for the home card

Preview the site:  tools/serve.sh
MSG
