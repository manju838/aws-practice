# Adding a project

One command scaffolds everything and registers the new tab.

```bash
tools/new-project.sh step-functions-etl "Step Functions ETL"
```

It will:

1. Copy `projects/_template/` to `projects/step-functions-etl/`.
2. Fill in the project name and title in the copied files.
3. Append an entry to `_data/projects.yml`, which creates the nav tab and the home-page card.
4. Print what to do next.

## Then

1. `cd projects/step-functions-etl && cp config.env.example config.env` and set `PROJECT` and `AWS_REGION`.
2. `uv sync` to create the Python environment from the copied `pyproject.toml` (add libraries with `uv add`).
3. Edit the project `README.md` (goal, architecture, phase table) and `00-background.md` (why).
4. Add phases by creating `01-….md`, `02-….md`. Copy `01-phase-template.md` for the standard headings.
5. Put scripts in `scripts/`, deployable code in `src/`, CDK in `infra/`.
6. Change the registry `status` from `planned` to `in-progress` to `done` as you go.

## What you get for free

* A tab in the nav bar and a card on the home page.
* A phase bar and prev/next links on every page in the project folder.
* Shared shell helpers in `tools/lib/common.sh`, so scripts look the same across projects.
* `tools/capture.sh` and `tools/doc-todos.sh` for results-driven documentation.
