#!/usr/bin/env bash
# usage: tools/serve.sh     → preview the site at http://localhost:4000/<baseurl>/
# Uses Docker with the same 'github-pages' gem set GitHub uses to build the site.
# Ruby 2.7 is required: the github-pages gem pins old Jekyll/Liquid versions that
# call String#untaint, a method removed in Ruby 3.2+.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
command -v docker >/dev/null || { echo "Docker is required (or: bundle install && bundle exec jekyll serve)"; exit 1; }
export MSYS_NO_PATHCONV=1
HERE="$(pwd -W 2>/dev/null || pwd)"        # Windows path under Git Bash, normal path elsewhere
docker run --rm -it -p 4000:4000 -v "$HERE":/site -v aws-practice-gems-27:/usr/local/bundle -w /site \
  -e BUNDLE_FORCE_RUBY_PLATFORM=1 ruby:2.7 \
  bash -c "rm -f Gemfile.lock && bundle install --quiet && bundle exec jekyll serve --host 0.0.0.0 --livereload --force_polling"