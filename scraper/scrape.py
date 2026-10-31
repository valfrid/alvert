#!/usr/bin/env python3
"""
Hämtar alla inlägg från alvert.se (blogg.se) och sparar dem som JSON i data/posts/.

Bara själva inläggen sparas: rubrik, datum, kategorier, text och bilder.
Reklam, skript, delningsknappar och kommentarer rensas bort.

Exempel:
  python scraper/scrape.py                 # hämta alla nya inlägg
  python scraper/scrape.py --limit 5       # testkörning med 5 inlägg
  python scraper/scrape.py --refresh       # hämta om även redan sparade inlägg
  python scraper/scrape.py --debug 2021-june
"""
import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Comment

BASE = "https://alvert.se"
INTERNAL_HOSTS = {"alvert.se", "alvert.blogg.se"}
ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "data" / "posts"

SV_MONTHS = {
    "januari": 1, "februari": 2, "mars": 3, "april": 4, "maj": 5, "juni": 6,
    "juli": 7, "augusti": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
}
EN_MONTHS = ["january", "february", "march", "april", "may", "june", "july",
             "august", "september", "october", "november", "december"]

POST_RE = re.compile(r"^/(\d{4})/([a-z]+)/([^/]+)\.html$")
MONTH_RE = re.compile(r"^/(\d{4})/([a-z]+)/?$")
CATEGORY_RE = re.compile(r"^/category/([^/]+)\.html$")
DATE_RE = re.compile(
    r"(\d{1,2})\s+(" + "|".join(SV_MONTHS) + r")\s+(\d{4})(?:[^\d]{0,12}?(\d{1,2})[:.](\d{2}))?",
    re.I,
)
IMG_EXT_RE = re.compile(r"\.(jpe?g|png|gif|webp|bmp)$", re.I)

# Klass/id-ord som betyder reklam eller annat brus inuti ett inlägg
NOISE_RE = re.compile(
    r"(^|[-_\s])(ad|ads|adv|advert\w*|annons\w*|banner\w*|sponsor\w*|adform\w*|adsense|"
    r"adtech|dfp|gpt|outbrain|taboola|widget|share\w*|sharing|social|comment\w*|"
    r"related|pagination|pager|nav|navigation|footer)($|[-_\s])",
    re.I,
)
SHARE_HOSTS = ("facebook.com", "twitter.com", "x.com", "pinterest.", "linkedin.com", "bloglovin")
VIDEO_HOSTS = ("youtube.com", "youtube-nocookie.com", "youtu.be", "vimeo.com")

session = requests.Session()
session.headers["User-Agent"] = "Mozilla/5.0 (alvert-arkiv; privat kopia av egen blogg)"


def fetch(url, delay):
    for attempt in range(4):
        try:
            r = session.get(url, timeout=30)
            if r.status_code == 200:
                r.encoding = r.apparent_encoding if not r.encoding else r.encoding
                time.sleep(delay)
                return r.text
            if r.status_code == 404:
                print(f"  404: {url}", file=sys.stderr)
                return None
            print(f"  HTTP {r.status_code}: {url}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  fel: {url}: {e}", file=sys.stderr)
        time.sleep(3 * (attempt + 1))
    print(f"  ! gav upp: {url}", file=sys.stderr)
    return None


def split_url(href, base):
    full = urljoin(base, href.strip())
    p = urlparse(full)
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return full, host, p.path, p.query


def is_internal(host):
    return host in INTERNAL_HOSTS


def classes_of(tag):
    return " ".join(tag.get("class", []) or []) + " " + (tag.get("id") or "")


# ---------- hitta alla inlägg via blogg.se:s "ladda fler"-adress ----------
# Arkivsidorna visar bara ett inlägg och laddar resten med JavaScript från
# /_more/entries_<år>-<månad>_<tidsstämpel>, som svarar med JSON:
# {"count": n, "last_ts": ..., "entries": [{title, body, iso8601, permalink, categories, tags, ...}]}

def discover_months(delay):
    html = fetch(BASE + "/", delay)
    if not html:
        sys.exit("Kunde inte hämta startsidan.")
    soup = BeautifulSoup(html, "lxml")
    months = []
    for a in soup.find_all("a", href=True):
        _, host, path, _ = split_url(a["href"], BASE)
        m = MONTH_RE.match(path)
        if is_internal(host) and m and m.group(2) in EN_MONTHS:
            key = (m.group(1), m.group(2))
            if key not in months:
                months.append(key)
    return months


def fetch_json(url, delay):
    text = fetch(url, delay)
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        print(f"  ! inte JSON: {url}", file=sys.stderr)
        return None


def entries_in_month(year, month, delay):
    ts, seen, entries = 1900000000, set(), []  # börja "i framtiden" = nyaste först
    for _ in range(200):
        data = fetch_json(f"{BASE}/_more/entries_{year}-{month}_{ts}", delay)
        if not data or not data.get("count"):
            break
        for e in data.get("entries", []):
            if e.get("id") not in seen:
                seen.add(e.get("id"))
                entries.append(e)
        new_ts = data.get("last_ts")
        if not new_ts or new_ts >= ts:
            break
        ts = new_ts
    return entries


# ---------- städa ett inlägg ----------

def image_key(url):
    p = urlparse(url)
    host = p.netloc.lower()
    path = re.sub(r"[^A-Za-z0-9._/-]", "_", unquote(p.path)).strip("/")
    path = re.sub(r"/+", "/", path).replace("..", "_")
    if p.query:
        stem, dot, ext = path.rpartition(".")
        h = hashlib.sha1(p.query.encode()).hexdigest()[:8]
        path = f"{stem}-{h}.{ext}" if dot else f"{path}-{h}"
    return f"{host}/{path}"


def remove_noise(container):
    for c in container.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for t in container.find_all(["script", "style", "noscript", "ins", "form", "button",
                                 "input", "textarea", "select", "link", "meta"]):
        t.decompose()
    for t in container.find_all(["iframe", "embed", "object"]):
        src = t.get("src") or t.get("data") or ""
        if not any(h in src for h in VIDEO_HOSTS):
            t.decompose()
        elif src.startswith("//"):
            t["src"] = "https:" + src
        elif src.startswith("http:"):
            t["src"] = "https:" + src[5:]
    total = len(container.get_text(" ", strip=True)) or 1
    for t in list(container.find_all(True)):
        if getattr(t, "decomposed", False) or t.parent is None:
            continue
        if NOISE_RE.search(classes_of(t)):
            # ta aldrig bort något som innehåller större delen av texten
            if len(t.get_text(" ", strip=True)) < total * 0.5:
                t.decompose()
    for a in list(container.find_all("a", href=True)):
        href = a["href"]
        if any(h in href for h in SHARE_HOSTS) and ("share" in href or "intent" in href or "sharer" in href):
            a.decompose()
        elif href.endswith("#comment") or "#comments" in href:
            a.decompose()



def clean_body(html, url):
    soup = BeautifulSoup(f"<div>{html}</div>", "lxml")
    container = soup.body.div if soup.body and soup.body.div else soup
    remove_noise(container)

    images = {}
    for img in container.find_all("img"):
        src = img.get("data-src") or img.get("data-original") or img.get("data-lazy-src") or img.get("src")
        if not src or src.startswith("data:"):
            continue
        full, _, _, _ = split_url(src, url)
        if not full.startswith("http"):
            continue
        key = image_key(full)
        images[key] = full
        img["src"] = "/img/" + key
        img["loading"] = "lazy"
        for attr in ("srcset", "data-src", "data-original", "data-lazy-src", "sizes", "style",
                     "width", "height", "data-oid"):
            img.attrs.pop(attr, None)
        if not img.get("alt"):
            img["alt"] = ""

    for a in container.find_all("a", href=True):
        full, host, p, q = split_url(a["href"], url)
        if IMG_EXT_RE.search(urlparse(full).path) and full.startswith("http"):
            key = image_key(full)
            images[key] = full
            a["href"] = "/img/" + key
        elif is_internal(host):
            a["href"] = p + (f"?{q}" if q else "")

    for el in container.find_all(True):
        for attr in list(el.attrs):
            if attr.startswith("on") or attr in ("class", "id") or attr.startswith("data-"):
                del el.attrs[attr]

    body = container.decode_contents().strip()
    body = body.replace("\\r\\n", "\n")
    body = re.sub(r"(\s*<br/?>\s*){3,}", "<br/><br/>", body)
    return body, [{"key": k, "src": v} for k, v in images.items()]


def entry_to_post(e):
    path = e.get("permalink") or e.get("url") or "/" + e["slug"]
    m = POST_RE.match(path)
    if not m:
        raise ValueError(f"okänd adress: {path}")
    year, month_en, slug = m.groups()
    url = BASE + path
    body, images = clean_body(e.get("body", ""), url)
    title = re.sub(r"^\s*Alvert\.se\s*[-–—|:]\s*", "", e.get("title") or slug, flags=re.I).strip()
    return {
        "url": url,
        "path": path,
        "year": int(year),
        "month": month_en,
        "slug": slug,
        "title": title,
        "date": (e.get("iso8601") or e.get("date") or f"{year}-01-01")[:16],
        "timestamp": e.get("timestamp", 0),
        "categories": [{"name": c["name"], "slug": c["slug"]} for c in e.get("categories", [])],
        "tags": e.get("tags", []),
        "html": body,
        "images": images,
    }


def post_file(url):
    year, month, slug = POST_RE.match(urlparse(url).path).groups()
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", unquote(slug))
    return POSTS_DIR / f"{year}-{EN_MONTHS.index(month) + 1:02d}-{safe}.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="max antal inlägg att spara (0 = alla)")
    ap.add_argument("--refresh", action="store_true", help="skriv över redan sparade inlägg")
    ap.add_argument("--delay", type=float, default=0.7, help="paus i sekunder mellan anrop")
    ap.add_argument("--debug", metavar="ÅR-MÅNAD", help="visa resultatet för en månad, t.ex. 2021-june")
    args = ap.parse_args()

    if args.debug:
        y, m = args.debug.split("-")
        for e in entries_in_month(y, m, 0):
            print(json.dumps(entry_to_post(e), ensure_ascii=False, indent=2))
        return

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    months = discover_months(args.delay)
    print(f"Hittade {len(months)} månader i arkivet")

    saved = skipped = failed = total = 0
    for year, month in months:
        entries = entries_in_month(year, month, args.delay)
        total += len(entries)
        print(f"{year} {month}: {len(entries)} inlägg")
        for e in entries:
            try:
                post = entry_to_post(e)
            except Exception as ex:  # ett trasigt inlägg ska inte stoppa resten
                print(f"  ! kunde inte tolka {e.get('permalink')}: {ex}", file=sys.stderr)
                failed += 1
                continue
            f = post_file(post["url"])
            if f.exists() and not args.refresh:
                skipped += 1
                continue
            f.write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")
            saved += 1
            if args.limit and saved >= args.limit:
                print(f"Gräns på {args.limit} nådd.")
                print(f"Klart: {saved} sparade, {skipped} fanns redan, {failed} misslyckades")
                return
    print(f"Klart: {total} inlägg hittade, {saved} sparade, {skipped} fanns redan, {failed} misslyckades")


if __name__ == "__main__":
    main()
