---
layout: page
title: AWS Practice
---
{% comment %} Site home. README.md is the GitHub landing page; this file is the website's. {% endcomment %}

Hands-on AWS projects, **documented as they were built**: what I did, why, the
commands, the results, and what went wrong. Each project is a tab above and
follows the same layout, so they read the same way.

<div class="project-cards">
{% for p in site.data.projects %}
  <a class="project-card" href="{{ p.url | relative_url }}">
    <h3>{{ p.title }} <span class="badge {{ p.status }}">{{ p.status | replace: '-', ' ' }}</span></h3>
    <p>{{ p.summary }}</p>
    {% for s in p.services %}<span class="chip">{{ s }}</span>{% endfor %}
  </a>
{% endfor %}
</div>

### How this site works

* Every project lives in its own folder under `projects/` and its **README.md is the project's landing page**.
* Extra pages (`00-background.md`, `01-foundation.md`, …) are the build phases, in filename order.
* Adding a project is one command. See [Conventions]({{ '/docs/' | relative_url }}).
