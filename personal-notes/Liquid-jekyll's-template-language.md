<!-- markdownlint-disable-file -->
## Liquid-Jekyll's Template Language

Liquid is Jekyll's Template Language. ```_includes/``` and ```_layouts/``` are written in Liquid.

### Liquid in five minutes
{% raw %}
| Syntax          | Meaning                                                            | Example                                |
|-----------------|--------------------------------------------------------------------|----------------------------------------|
| {{ ... }}       | Output: print a value                                              | {{ site.title }} prints "AWS Practice" |
| {% ... %}       | Logic: no output (if, for, assign, include)                        | {% for p in site.data.projects %}      |
| \|              | Filter: pipe a value through a function                            | {{ '/' \| relative_url }}              |
| {%- / -%}       | Strip surrounding whitespace so the HTML isn't full of blank lines | everywhere in your files               |
| {%- comment -%} | A note that is not output                                          | top of each file                       |
|                 |                                                                    |                                        |

Variables are available in every template:

| Variable | What it is                                                                                         |
|----------|----------------------------------------------------------------------------------------------------|
| site     | Everything from _config.yml, plus site.data (from _data/) and site.pages (every page Jekyll found) |
| page     | The page currently being built (its url, dir, title, name)                                         |
| content  | The rendered body of that page, only inside a layout                                               |

- **A layout is a wrapper. The page's content goes inside it** through {{ content }}. A page picks one layout, and layouts can nest (project wraps in default).
- **An include is a piece you paste in** with {% include file.html %}. It has no {{ content }}, and it sees the same page and site variables as whoever included it.

{% endraw %}
