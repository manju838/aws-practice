<!-- markdownlint-disable-file -->
# How to add a new project?

1. Duplicate ```projects/_template``` folder inside ```projects/``` and rename it with the new project name
2. The template of any project is as follows:
{% raw %}
```
projects/
    |__<new-project-name>/
        |__ assets/
        |__ infra/
        |__ results/
        |__ scripts/
        |__ src/
        |__ tests/
        |__ .python-version
        |__ pyproject.toml
        |__ README.md
        |__ 00-background.md     Context: why this project exists, decisions, history
        |__ 01-<phase>.md        One page per build phase, in build order
```
{% endraw %}