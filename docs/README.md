# Conventions

Every project in this repo is built and documented the same way, so that
scripts, docs and infrastructure look familiar no matter which project you open.
This page is the contract. `projects/_template/` is a working copy of it.

## Repo layout

```
aws-practice/
├── README.md              GitHub landing page (plain markdown, no Liquid)
├── index.md               Website home (project cards, generated from the registry)
├── _config.yml            Site config: theme, plugins, excludes
├── _data/projects.yml     THE project registry: one entry = one nav tab + one home card
├── _includes/ _layouts/   Header (tabs) and project layout (phase bar + prev/next)
├── docs/                  These pages
├── tools/                 Shared scripts used by every project (never project-specific)
│   ├── lib/common.sh      Shell helpers: config loading, logging, zipping, confirmations
│   ├── new-project.sh     Scaffold a project from the template and register its tab
│   ├── capture.sh         Run a command and save its output for the docs
│   ├── doc-todos.sh       List result placeholders that still need filling in
│   └── serve.sh           Preview the site locally (Docker)
└── projects/
    ├── _template/         Copy of the standard project skeleton (not published)
    └── <project>/         One folder per project
```

## Project folder (identical in every project)

```
projects/<project>/
├── README.md            Landing page: what, why, architecture, status table, results summary
├── 00-background.md     Context: why this project exists, decisions, history
├── 01-<phase>.md  ...   One page per build phase, in build order
├── pyproject.toml       Python dependencies, managed with uv (groups: dev, infra, ...)
├── uv.lock              Exact versions. Commit it.
├── config.env.example   Every tunable in one place. Copy to config.env (git-ignored)
├── scripts/             Numbered CLI scripts (10-…, 20-…), one job each, safe to re-run
├── src/                 Code that gets deployed (Lambda handlers, containers, …)
├── infra/               Infrastructure as code (CDK app)
├── tests/               Local tests. Must run without AWS credentials
├── results/             Captured command outputs (.txt), linked from the phase pages
└── assets/              Screenshots (redact first, see below)
```

The website needs **no extra config** for new phase pages: any `NN-name.md` file
in the folder shows up in the project's phase bar and prev/next links, ordered by filename.

## Python dependencies: uv, by default

Every project manages Python with [uv](https://docs.astral.sh/uv/). There is no `requirements.txt`, no `pip install`,
and no venv to activate.

* `uv sync` creates `.venv` and installs the default groups (`dev` and `infra`).
* `uv run pytest` and `uv run python …` run inside that environment automatically.
* CDK runs its app through uv too (`infra/cdk.json` calls `uv run python app.py`), so `cdk deploy` just works.
* Add a dependency with `uv add --group dev <pkg>`. Groups keep concerns separate:
  `dev` (tests and local tools), `infra` (CDK), and, for Lambda, a `layer` group listing exactly what is packaged.
* **Lambda layers are built without Docker:** `uv pip install --group layer --target … --python-platform x86_64-manylinux_2_28`
  downloads the Linux wheels directly, so the build is identical on Windows, macOS and Linux.
* Commit `uv.lock` so every run resolves to the same versions.

## Phase page anatomy

Every phase page has the same headings in the same order. That is what makes the
site skimmable and makes it obvious what is still unfinished.

1. **Header table**: time budget, actual time, cost, status
2. **Why this phase exists**: the reasoning, in plain words
3. **Steps**: numbered; each says what, the command, and why
4. **Verify**: how you know it worked
5. **Results**: real output and screenshots, not intentions
6. **Gotchas & lessons**: what broke and how it was fixed

A placeholder that still needs real output is written `TODO(result)`. Run
`tools/doc-todos.sh` any time to see what is left to fill in.

## Script conventions

* Every script starts with the same two lines: `source …/tools/lib/common.sh` then `load_project_config`.
* **No hardcoded account IDs, regions, ARNs, paths or URLs.** Everything comes from `config.env`; the account ID is looked up at run time.
* Numbered by phase: `1x` foundation, `2x` storage/RAG, `3x` API, `5x` monitoring, `6x` security, `9x` teardown.
* **Idempotent:** re-running a script must not fail or duplicate things. Check-then-create.
* Destructive scripts ask for confirmation via `confirm`.
* Run anything worth documenting through `tools/capture.sh <project> <name> <command…>`.

## Naming

Resources are named `<project>-<thing>`, e.g. `smartdocs-indexer`, `smartdocs-conversations`.
The project name comes from `PROJECT` in `config.env`, so the pattern is enforced by the scripts.
Every CDK stack tags its resources with `project=<name>`, which makes the Cost Explorer breakdown per project trivial.

## Security rules for a public site

* **Never commit** `config.env`, access keys, API keys, or endpoint URLs. `.gitignore` and the site's `exclude:` already cover `config.env`.
* **Redact screenshots** before saving them to `assets/`: 12-digit account IDs, ARNs with account IDs, access key IDs, API URLs.
* Any API you expose while documenting must be behind an API key and throttled, and **torn down** when the project is done.
* Docs show placeholders such as `<ACCOUNT_ID>` and `https://<api-id>.execute-api.<region>.amazonaws.com`.

## More

* [Adding a project](adding-a-project.md)
* [Publishing and previewing the site](publishing.md)
