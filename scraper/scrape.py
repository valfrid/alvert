#!/usr/bin/env python3
"""
Hämtar alla inlägg från alvert.se (blogg.se) och sparar dem som JSON i data/posts/.

Bara själva inläggen sparas: rubrik, datum, kategorier, text och bilder.
Reklam, skript, delningsknappar och kommentarer rensas bort.

Exempel:
  python scraper/scrape.py                 # hämta alla nya inlägg
  python scraper/scrape.py --limit 5       # testkörning med 5 inlägg
  python scraper/scrape.py --refresh       # hämta om även redan sparade inlägg
  python scraper/scrape.py --debug https://alvert.se/2021/july/hon-har-ett-namn.html
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


# ---------- hitta alla inlägg ----------

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
            url = f"{BASE}/{m.group(1)}/{m.group(2)}/"
            if url not in months:
                months.append(url)
    return months


def posts_in_month(month_url, delay):
    month_path = urlparse(month_url).path
    queue, seen, posts = [month_url], set(), []
    while queue and len(seen) < 60:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        html = fetch(url, delay)
        if not html:
            continue
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            full, host, path, query = split_url(a["href"], url)
            if not is_internal(host):
                continue
            if POST_RE.match(path) and path.startswith(month_path):
                post_url = BASE + path
                if post_url not in posts:
                    posts.append(post_url)
            elif path.rstrip("/") == month_path.rstrip("/") and query:
                # sidnumrering, t.ex. ?page=2
                queue.append(f"{BASE}{month_path}?{query}")
            elif path.startswith(month_path) and path != month_path and not path.endswith(".html"):
                queue.append(BASE + path)
    return posts


# ---------- plocka ut ett inlägg ----------

def count_category_links(tag):
    return sum(1 for a in tag.find_all("a", href=True) if "/category/" in a["href"])


def find_heading(soup, path):
    for a in soup.find_all("a", href=True):
        _, host, p, _ = split_url(a["href"], BASE)
        if is_internal(host) and p == path and a.get_text(strip=True):
            h = a.find_parent(["h1", "h2", "h3", "h4"])
            if h:
                return h
    return None


def find_container(heading):
    best, node = heading, heading
    while node.parent is not None and node.parent.name not in ("body", "html", "[document]"):
        node = node.parent
        too_many_cats = count_category_links(node) > 5
        too_many_posts = len([h for h in node.find_all(["h1", "h2", "h3"]) if h.find("a")]) > 2
        if too_many_cats or too_many_posts:
            break
        best = node
    return best


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


def extract_post(url, html):
    soup = BeautifulSoup(html, "lxml")
    path = urlparse(url).path
    year, month_en, slug = POST_RE.match(path).groups()

    heading = find_heading(soup, path)
    if heading is None:
        og = soup.find("meta", property="og:title")
        title = (og["content"] if og else slug).replace(" - Alvert.se", "").strip()
        container = soup.find("article") or soup.body
        heading_text = title
    else:
        title = heading.get_text(" ", strip=True)
        container = find_container(heading)
        heading_text = title
        heading.decompose()

    # kategorier
    categories = []
    for a in list(container.find_all("a", href=True)):
        _, host, p, _ = split_url(a["href"], url)
        m = CATEGORY_RE.match(p)
        if is_internal(host) and m:
            cat = {"name": a.get_text(" ", strip=True), "slug": m.group(1)}
            if cat["name"] and cat not in categories:
                categories.append(cat)
            parent = a.parent
            a.decompose()
            if parent is not None and parent is not container and not parent.get_text(strip=True) and not parent.find("img"):
                parent.decompose()

    # datum
    date_iso, date_text = None, None
    time_tag = container.find("time")
    text = container.get_text(" ", strip=True)
    m = DATE_RE.search(text)
    if m:
        d, mon, y, hh, mm = m.groups()
        date_text = m.group(0).strip()
        date_iso = f"{int(y):04d}-{SV_MONTHS[mon.lower()]:02d}-{int(d):02d}"
        if hh:
            date_iso += f"T{int(hh):02d}:{mm}"
        # ta bort det minsta elementet som bara innehåller datumet
        for el in container.find_all(True):
            t = el.get_text(" ", strip=True)
            if date_text in t and len(t) < len(date_text) + 30 and not el.find("img"):
                el.decompose()
                break
    elif time_tag and time_tag.get("datetime"):
        date_iso = time_tag["datetime"][:16]
    if time_tag and time_tag.parent is not None:
        time_tag.decompose()
    if not date_iso:
        date_iso = f"{year}-{EN_MONTHS.index(month_en) + 1:02d}-01"

    remove_noise(container)

    # bilder
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
        for attr in ("srcset", "data-src", "data-original", "data-lazy-src", "sizes", "style"):
            img.attrs.pop(attr, None)
        if not img.get("alt"):
            img["alt"] = ""

    # länkar
    for a in container.find_all("a", href=True):
        full, host, p, q = split_url(a["href"], url)
        if IMG_EXT_RE.search(urlparse(full).path) and full.startswith("http"):
            key = image_key(full)
            images[key] = full
            a["href"] = "/img/" + key
        elif is_internal(host):
            a["href"] = p + (f"?{q}" if q else "")
        a.attrs.pop("onclick", None)

    for el in container.find_all(True):
        for attr in list(el.attrs):
            if attr.startswith("on") or attr in ("class", "id"):
                del el.attrs[attr]

    body = container.decode_contents().strip() if container.name in ("article", "div", "section", "main") \
        else str(container)
    body = re.sub(r"(\s*<br/?>\s*){3,}", "<br/><br/>", body)

    return {
        "url": url,
        "path": path,
        "year": int(year),
        "month": month_en,
        "slug": slug,
        "title": title or heading_text,
        "date": date_iso,
        "date_text": date_text,
        "categories": categories,
        "html": body,
        "images": [{"key": k, "src": v} for k, v in images.items()],
    }


def post_file(url):
    year, month, slug = POST_RE.match(urlparse(url).path).groups()
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", unquote(slug))
    return POSTS_DIR / f"{year}-{EN_MONTHS.index(month) + 1:02d}-{safe}.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="max antal inlägg att hämta (0 = alla)")
    ap.add_argument("--refresh", action="store_true", help="hämta om redan sparade inlägg")
    ap.add_argument("--delay", type=float, default=0.7, help="paus i sekunder mellan anrop")
    ap.add_argument("--debug", metavar="URL", help="visa resultatet för ett enda inlägg")
    args = ap.parse_args()

    if args.debug:
        html = fetch(args.debug, 0)
        post = extract_post(args.debug, html)
        print(json.dumps(post, ensure_ascii=False, indent=2))
        return

    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    months = discover_months(args.delay)
    print(f"Hittade {len(months)} månader i arkivet")

    saved = skipped = failed = 0
    for month_url in months:
        urls = posts_in_month(month_url, args.delay)
        print(f"{month_url}: {len(urls)} inlägg")
        for order, url in enumerate(urls):
            f = post_file(url)
            if f.exists() and not args.refresh:
                skipped += 1
                continue
            html = fetch(url, args.delay)
            if not html:
                failed += 1
                continue
            try:
                post = extract_post(url, html)
            except Exception as e:  # ett trasigt inlägg ska inte stoppa resten
                print(f"  ! kunde inte tolka {url}: {e}", file=sys.stderr)
                failed += 1
                continue
            post["order"] = order
            f.write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")
            saved += 1
            print(f"  + {post['date'][:10]} {post['title']}")
            if args.limit and saved >= args.limit:
                print(f"Gräns på {args.limit} nådd.")
                print(f"Klart: {saved} nya, {skipped} fanns redan, {failed} misslyckades")
                return
    print(f"Klart: {saved} nya, {skipped} fanns redan, {failed} misslyckades")


if __name__ == "__main__":
    main()
