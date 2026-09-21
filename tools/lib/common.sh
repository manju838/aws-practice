#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# tools/lib/common.sh — helpers shared by EVERY project's scripts.
# Source it, don't run it:
#
#     source "$(dirname "${BASH_SOURCE[0]}")/../../../tools/lib/common.sh"
#     load_project_config
#
# After load_project_config you have: PROJECT_DIR, ACCOUNT_ID, AWS_REGION,
# everything defined in the project's config.env, and the current directory
# is PROJECT_DIR (so relative paths like build/x.zip always work, which also
# avoids Windows/Git-Bash path-conversion problems with the AWS CLI).
# ─────────────────────────────────────────────────────────────────────
set -euo pipefail

# Git Bash on Windows rewrites arguments that look like paths (/aws/lambda/...),
# which breaks AWS CLI calls. Turn that off.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$TOOLS_DIR/.." && pwd)"

# ── output ───────────────────────────────────────────────────────────
_color() { if [ -t 1 ]; then printf '\033[%sm' "$1"; fi; }
step() { printf '\n%s==> %s%s\n' "$(_color 1)" "$*" "$(_color 0)"; }
log()  { printf '    %s\n' "$*"; }
ok()   { printf '%s    ✔ %s%s\n' "$(_color 32)" "$*" "$(_color 0)"; }
warn() { printf '%s    ! %s%s\n' "$(_color 33)" "$*" "$(_color 0)" >&2; }
die()  { printf '%sERROR: %s%s\n' "$(_color 31)" "$*" "$(_color 0)" >&2; exit 1; }

need() {
  local c
  for c in "$@"; do command -v "$c" >/dev/null 2>&1 || die "'$c' is required but not installed or not on PATH"; done
}

# python3 on Linux/macOS, python on Windows
PY="$(command -v python3 || command -v python || true)"
py() { [ -n "$PY" ] || die "Python is required"; "$PY" "$@"; }

confirm() {
  # ASSUME_YES=1 skips the prompt (for scripted runs).
  [ "${ASSUME_YES:-0}" = "1" ] && return 0
  local answer
  read -r -p "$1 [y/N] " answer
  [[ "$answer" =~ ^[Yy]$ ]] || die "Aborted."
}

# ── project config ───────────────────────────────────────────────────
load_project_config() {
  local caller="${BASH_SOURCE[1]}"
  PROJECT_DIR="$(cd "$(dirname "$caller")/.." && pwd)"
  [ -f "$PROJECT_DIR/config.env" ] || die "Missing $PROJECT_DIR/config.env. Run:  cp config.env.example config.env"
  need aws

  # Account ID is looked up, never hardcoded. config.env may reference $ACCOUNT_ID.
  ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)" \
    || die "AWS credentials are not working. Run 'aws configure', then 'aws sts get-caller-identity'."

  # tr -d '\r' so a config.env saved with Windows line endings still works
  set -a
  # shellcheck disable=SC1090
  . <(tr -d '\r' < "$PROJECT_DIR/config.env")
  set +a

  : "${PROJECT:?PROJECT must be set in config.env}"
  : "${AWS_REGION:?AWS_REGION must be set in config.env}"
  export AWS_DEFAULT_REGION="$AWS_REGION"
  export ACCOUNT_ID PROJECT_DIR

  cd "$PROJECT_DIR"
  mkdir -p build results
}

# ── files ────────────────────────────────────────────────────────────
# make_zip <source_dir> <zip_path>
# Zips the CONTENTS of source_dir (no top-level folder), skipping caches.
# Uses Python so nothing depends on a `zip` binary being installed (Git Bash has none).
make_zip() {
  py - "$1" "$2" <<'PY'
import os, sys, zipfile
src, out = sys.argv[1], sys.argv[2]
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
if os.path.exists(out):
    os.remove(out)
count = 0
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.endswith(".pyc"):
                continue
            full = os.path.join(root, f)
            z.write(full, os.path.relpath(full, src))
            count += 1
print(f"    zipped {count} files -> {out} ({os.path.getsize(out) / 1e6:.1f} MB)")
PY
}

# write_env_json <file> KEY=VALUE ...   (Lambda --environment payload)
write_env_json() {
  local file="$1"; shift
  py - "$file" "$@" <<'PY'
import json, sys
path, pairs = sys.argv[1], sys.argv[2:]
env = dict(p.split("=", 1) for p in pairs)
json.dump({"Variables": env}, open(path, "w"))
PY
}

# ── s3 ───────────────────────────────────────────────────────────────
# empty_versioned_bucket <bucket>   deletes every object version and delete marker
empty_versioned_bucket() {
  local bucket="$1" key ver
  aws s3api list-object-versions --bucket "$bucket" \
      --query '[Versions,DeleteMarkers][][].[Key,VersionId]' --output text 2>/dev/null \
    | while IFS=$'\t' read -r key ver; do
        [ -z "$key" ] || [ "$key" = "None" ] && continue
        aws s3api delete-object --bucket "$bucket" --key "$key" --version-id "$ver" >/dev/null
      done
}
