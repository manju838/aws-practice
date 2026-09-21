# Publishing and previewing the site

## One-time GitHub setup

1. Create a **public** repo (GitHub Pages on private repos needs a paid plan) and push this folder to it.
2. Edit `_config.yml`: set `url` to `https://<username>.github.io` and `baseurl` to `/<repo-name>`.
3. Repo **Settings → Pages → Build and deployment → Deploy from a branch**, branch `main`, folder `/ (root)`.
4. Wait about a minute. The site appears at `https://<username>.github.io/<repo-name>/`.

There is no build step to maintain: GitHub builds the site itself on every push.

## Preview locally

Requires Docker.

```bash
tools/serve.sh
# open http://localhost:4000/aws-practice/   (matches baseurl in _config.yml)
```

The first run installs gems and takes a couple of minutes. After that, saving a file rebuilds the site.

## If a page is missing or a link is broken

| Symptom | Cause |
| --- | --- |
| Project tab missing | No entry for it in `_data/projects.yml` |
| Project page 404 | Folder has no `README.md`; the README is what becomes the folder's index page |
| Page shows raw template braces (double curly braces) | Liquid only runs on pages that have front matter; keep Liquid out of README files |
| Links or styles missing on the live site | `baseurl` in `_config.yml` doesn't match the repo name |
| Folder missing from the site | It starts with `_` or is listed under `exclude:` in `_config.yml` |
| A `README.md` doesn't render as a page | It's in an excluded folder, or the same folder also has an `index.md` (the index wins) |

## Tooling you need on your machine

| Tool | Used for | Install |
| --- | --- | --- |
| [uv](https://docs.astral.sh/uv/) | Python dependencies, running tests and CDK | `curl -LsSf https://astral.sh/uv/install.sh \| sh` (Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"`) |
| AWS CLI v2 | Every script | [aws.amazon.com/cli](https://aws.amazon.com/cli/) |
| Node.js + `npm install -g aws-cdk` | CDK CLI | [nodejs.org](https://nodejs.org) |
| Docker | Only for `tools/serve.sh` (site preview) | Docker Desktop |
| Git Bash (Windows) | Runs the `.sh` scripts | comes with Git for Windows |
