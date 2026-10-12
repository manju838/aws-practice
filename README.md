# AWS Practice

Hands-on AWS projects, documented as they were built: process, results and lessons.
Everything in this repo is published as a GitHub Pages site (Jekyll, minima theme).

| Project | Status | What it is |
| --- | --- | --- |
| [SmartDocs AI](projects/smartdocs-ai/README.md) | in progress | Serverless RAG assistant: S3, Lambda, FAISS, Bedrock (Claude), DynamoDB, API Gateway, CDK |

## Repo map

* `projects/<name>/` : one folder per project; its `README.md` is the project's landing page
* `_data/projects.yml` : project registry (one entry = one site tab)
* `tools/` : shared scripts used by every project
* `docs/` : conventions, adding a project, publishing the site
* `_layouts/`: Holds **page templates**. Each one defines the overall structure of a whole page, with a placeholder where the page's own content goes.
* `_includes/`: Contains small reusable snippets of HTML that is injected into layouts(or other includes).

Start with [docs/README.md](docs/README.md) (Conventions).
