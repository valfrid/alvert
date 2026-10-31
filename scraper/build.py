#!/usr/bin/env python3
"""
Bygger den statiska bloggen i dist/ från data/posts/*.json.
Behåller samma adresser som på blogg.se, så gamla länkar fortsätter fungera:
  /2021/july/hon-har-ett-namn.html, /2021/july/, /category/fritid.html

Miljövariabeln BASE_PATH sätts när sajten ligger i en undermapp,
t.ex. BASE_PATH=/alvert för valfrid.github.io/alvert/.
"""
import json
import os
import re
import shutil
from collections import OrderedDict, defaultdict
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "data" / "posts"
DIST = ROOT / "dist"
IMG_CACHE = ROOT / ".cache" / "img"
BASE = os.environ.get("BASE_PATH", "").rstrip("/")


def u(path):
    """Gör en sökväg på sajten till en adress med rätt bas."""
    return BASE + path

SITE = "Alvert.se"
PER_PAGE = 8

EN = ["january", "february", "march", "april", "may", "june", "july",
      "august", "september", "october", "november", "december"]
SV = ["januari", "februari", "mars", "april", "maj", "juni", "juli",
      "augusti", "september", "oktober", "november", "december"]
SV_SHORT = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]

CSS = """
:root{
  --bg:#f3f5f4; --surface:#ffffff; --ink:#1e2b2f; --muted:#5d6d71;
  --accent:#8c3b5e; --rule:#d9e1df; --focus:#2f6f8a;
  color-scheme: light;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#131a1c; --surface:#1a2326; --ink:#e4ebe9; --muted:#9aa9ab;
    --accent:#e48db3; --rule:#2b373a; --focus:#7cc0db;
    color-scheme: dark;
  }
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font-family:"Literata", Georgia, "Times New Roman", serif;
  font-size:1.0625rem; line-height:1.7;
  padding:env(safe-area-inset-top,0) 0 env(safe-area-inset-bottom,0);
}
a{color:var(--accent); text-underline-offset:.18em; text-decoration-thickness:1px}
a:hover{text-decoration-thickness:2px}
:focus-visible{outline:2px solid var(--focus); outline-offset:3px; border-radius:2px}
.wrap{max-width:40rem; margin:0 auto; padding:0 1.25rem}

.site{padding:2.5rem 0 1.5rem; border-bottom:1px solid var(--rule); margin-bottom:2.5rem}
.site .wrap{display:flex; flex-wrap:wrap; align-items:baseline; justify-content:space-between; gap:.5rem 1.5rem}
.site-name{font-size:1.9rem; font-weight:600; letter-spacing:-.01em; color:var(--ink); text-decoration:none}
.site nav{display:flex; gap:1.25rem; font-size:.95rem}
.site nav a{color:var(--muted); text-decoration:none}
.site nav a:hover, .site nav a[aria-current]{color:var(--ink)}

.post{margin:0 0 4rem}
.post-head{display:grid; grid-template-columns:3.6rem 1fr; gap:1rem; align-items:start; margin-bottom:1.25rem}
.stamp{color:var(--accent); text-align:center; line-height:1; padding-top:.2rem}
.stamp .d{display:block; font-size:2.4rem; font-weight:600; font-variant-numeric:lining-nums}
.stamp .m{display:block; font-size:.8rem; color:var(--muted); margin-top:.3rem; white-space:nowrap}
.post h1, .post h2{font-size:1.65rem; line-height:1.25; margin:0; font-weight:600; letter-spacing:-.005em}
.post h2 a{color:var(--ink); text-decoration:none}
.post h2 a:hover{color:var(--accent)}
.cats{margin:.4rem 0 0; font-size:.9rem; color:var(--muted)}
.cats a{color:var(--muted)}
.body{overflow-wrap:break-word}
.body img{max-width:100%; height:auto; display:block; margin:1.25rem auto; border-radius:3px}
.body iframe{max-width:100%; width:100%; aspect-ratio:16/9; height:auto; border:0; margin:1.25rem 0}
.body p{margin:0 0 1em}
.body table{display:block; max-width:100%; overflow-x:auto}

.pager{display:flex; justify-content:space-between; gap:1rem; border-top:1px solid var(--rule);
  padding:1.5rem 0 3rem; font-size:.95rem}
.pager a{text-decoration:none}
.pager .older{margin-left:auto; text-align:right}
.pager small{display:block; color:var(--muted)}

.list{list-style:none; padding:0; margin:0 0 3rem}
.list li{display:grid; grid-template-columns:6.5rem 1fr; gap:1rem; padding:.55rem 0; border-bottom:1px solid var(--rule)}
.list time{color:var(--muted); font-size:.9rem; font-variant-numeric:tabular-nums}
.list a{color:var(--ink); text-decoration:none}
.list a:hover{color:var(--accent)}
.page-title{font-size:1.65rem; font-weight:600; margin:0 0 1.5rem}
.year{font-size:1.3rem; margin:2rem 0 .5rem}
.months{display:flex; flex-wrap:wrap; gap:.4rem 1rem; margin:0 0 1rem; padding:0; list-style:none}
.months small{color:var(--muted)}
.catlist{columns:2 12rem; padding:0; list-style:none; margin:0 0 3rem}
.catlist li{padding:.2rem 0; break-inside:avoid}
.catlist small{color:var(--muted)}

footer{color:var(--muted); font-size:.85rem; padding:2rem 0 3rem; border-top:1px solid var(--rule)}
@media (max-width:30rem){
  .post-head{grid-template-columns:2.8rem 1fr; gap:.75rem}
  .stamp .d{font-size:1.9rem}
  .post h1,.post h2{font-size:1.4rem}
  .list li{grid-template-columns:1fr; gap:0}
}
"""


def clean_title(t):
    """Tar bort "Alvert.se - " som blogg.se lägger före rubriken."""
    t = re.sub(r"^\s*Alvert\.se\s*[-–—|:]\s*", "", t, flags=re.I)
    t = re.sub(r"\s*[-–—|:]\s*Alvert\.se\s*$", "", t, flags=re.I)
    return t.strip() or "Utan rubrik"


def load_posts():
    posts = [json.loads(f.read_text(encoding="utf-8")) for f in POSTS_DIR.glob("*.json")]
    for p in posts:
        p["title"] = clean_title(p["title"])
    # nyast först; inom samma tidpunkt gäller ordningen i blogg.se:s månadsarkiv
    posts.sort(key=lambda p: (p["date"], -p.get("order", 0)), reverse=True)
    return posts


def month_label(p):
    y, m = p["date"][:4], int(p["date"][5:7])
    return f"{SV_SHORT[m - 1]} {y}"


def date_long(p):
    y, m, d = p["date"][:4], int(p["date"][5:7]), int(p["date"][8:10])
    return f"{d} {SV[m - 1]} {y}"


def page(title, body, current=""):
    nav = [("/", "Senaste", "home"), ("/arkiv/", "Arkiv", "arkiv"), ("/kategorier/", "Kategorier", "kat")]
    links = "".join(
        f'<a href="{u(h)}"{" aria-current=\"page\"" if k == current else ""}>{t}</a>' for h, t, k in nav
    )
    full_title = SITE if title == SITE else f"{title} – {SITE}"
    return f"""<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{escape(full_title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Literata:opsz,wght@7..72,400;7..72,600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{u("/style.css")}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🌷</text></svg>">
</head>
<body>
<header class="site"><div class="wrap">
<a class="site-name" href="{u("/")}">{SITE}</a>
<nav>{links}</nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer><div class="wrap">{SITE} · arkiv över bloggen</div></footer>
</body>
</html>
"""


def post_html(p, level="h2"):
    d = int(p["date"][8:10])
    cats = ", ".join(f'<a href="{u("/category/" + escape(c["slug"]) + ".html")}">{escape(c["name"])}</a>'
                     for c in p.get("categories", []))
    title = escape(p["title"])
    head = title if level == "h1" else f'<a href="{u(escape(p["path"]))}">{title}</a>'
    return f"""<article class="post">
<div class="post-head">
<div class="stamp" aria-hidden="true"><span class="d">{d}</span><span class="m">{month_label(p)}</span></div>
<div>
<{level}>{head}</{level}>
<p class="cats"><time datetime="{escape(p["date"])}">{date_long(p)}</time>{" i " + cats if cats else ""}</p>
</div>
</div>
<div class="body">
{body_html(p)}
</div>
</article>"""


MISSING_IMAGES = set()


def body_html(p):
    html = p["html"]
    # bilder som inte gick att hämta pekar på originalet hos blogg.se
    for img in p.get("images", []):
        if img["key"] in MISSING_IMAGES:
            html = html.replace(f'"/img/{img["key"]}"', f'"{escape(img["src"])}"')
    # interna länkar och bilder får rätt bas
    return re.sub(r'(\s(?:href|src)=")/(?!/)', lambda m: m.group(1) + BASE + "/", html)


def copy_images(posts):
    copied = 0
    for p in posts:
        for img in p.get("images", []):
            src = IMG_CACHE / img["key"]
            if src.exists():
                dst = DIST / "img" / img["key"]
                if not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, dst)
                    copied += 1
            else:
                MISSING_IMAGES.add(img["key"])
    return copied


def post_list(posts):
    rows = "".join(
        f'<li><time datetime="{p["date"][:10]}">{p["date"][:10]}</time>'
        f'<a href="{u(escape(p["path"]))}">{escape(p["title"])}</a></li>'
        for p in posts
    )
    return f'<ul class="list">{rows}</ul>'


def write(rel, html):
    out = DIST / rel.lstrip("/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")


def build():
    posts = load_posts()
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    (DIST / "style.css").write_text(CSS, encoding="utf-8")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")
    copied = copy_images(posts)

    # startsida med sidnumrering
    pages = [posts[i:i + PER_PAGE] for i in range(0, len(posts), PER_PAGE)] or [[]]
    for n, chunk in enumerate(pages, start=1):
        body = "\n".join(post_html(p) for p in chunk) or "<p>Inga inlägg ännu. Kör hämtningen först.</p>"
        newer = "" if n == 1 else f'<a href="{u("/" if n == 2 else f"/sida/{n - 1}/")}">Nyare inlägg</a>'
        older = "" if n == len(pages) else f'<a class="older" href="{u(f"/sida/{n + 1}/")}">Äldre inlägg</a>'
        body += f'<nav class="pager">{newer}{older}</nav>'
        rel = "index.html" if n == 1 else f"sida/{n}/index.html"
        write(rel, page(SITE if n == 1 else f"Sida {n}", body, "home" if n == 1 else ""))

    # enskilda inlägg (posts är nyast först)
    for i, p in enumerate(posts):
        newer = posts[i - 1] if i > 0 else None
        older = posts[i + 1] if i + 1 < len(posts) else None
        nav = '<nav class="pager">'
        if newer:
            nav += f'<a href="{u(escape(newer["path"]))}"><small>Nyare</small>{escape(newer["title"])}</a>'
        if older:
            nav += f'<a class="older" href="{u(escape(older["path"]))}"><small>Äldre</small>{escape(older["title"])}</a>'
        nav += "</nav>"
        write(p["path"], page(p["title"], post_html(p, "h1") + nav))

    # månader och arkiv
    by_month = OrderedDict()
    for p in posts:
        by_month.setdefault((p["year"], p["month"]), []).append(p)
    years = OrderedDict()
    for (y, m), ps in by_month.items():
        label = f"{SV[EN.index(m)].capitalize()} {y}"
        write(f"{y}/{m}/index.html",
              page(label, f'<h1 class="page-title">{label}</h1>' + "\n".join(post_html(p) for p in reversed(ps))))
        years.setdefault(y, []).append((m, len(ps)))
    arch = '<h1 class="page-title">Arkiv</h1>'
    for y, months in years.items():
        items = "".join(
            f'<li><a href="{u(f"/{y}/{m}/")}">{SV[EN.index(m)].capitalize()}</a> <small>{n}</small></li>'
            for m, n in sorted(months, key=lambda x: EN.index(x[0]), reverse=True)
        )
        arch += f'<h2 class="year">{y}</h2><ul class="months">{items}</ul>'
    write("arkiv/index.html", page("Arkiv", arch, "arkiv"))

    # kategorier
    cats = defaultdict(list)
    names = {}
    for p in posts:
        for c in p.get("categories", []):
            cats[c["slug"]].append(p)
            names[c["slug"]] = c["name"]
    for slug, ps in cats.items():
        write(f"category/{slug}.html",
              page(names[slug], f'<h1 class="page-title">{escape(names[slug])}</h1>' + post_list(ps)))
    catlist = "".join(
        f'<li><a href="{u("/category/" + escape(s) + ".html")}">{escape(names[s])}</a> <small>{len(cats[s])}</small></li>'
        for s in sorted(cats, key=lambda s: names[s].lower())
    )
    write("kategorier/index.html",
          page("Kategorier", f'<h1 class="page-title">Kategorier</h1><ul class="catlist">{catlist}</ul>', "kat"))

    write("404.html", page("Sidan finns inte",
                           '<h1 class="page-title">Sidan finns inte</h1>'
                           f'<p>Adressen leder inte till något inlägg. Leta i <a href="{u("/arkiv/")}">arkivet</a> '
                           f'eller gå till <a href="{u("/")}">startsidan</a>.</p>'))

    files = [f for f in DIST.rglob("*") if f.is_file()]
    size = sum(f.stat().st_size for f in files) / 1e6
    print(f"Byggde {len(posts)} inlägg, {len(by_month)} månader, {len(cats)} kategorier, "
          f"{copied} bilder ({len(MISSING_IMAGES)} länkas till blogg.se). {len(files)} filer, {size:.0f} MB.")
    if size > 950:
        print("VARNING: sajten är nära eller över GitHub Pages gräns på 1 GB.")


if __name__ == "__main__":
    build()
