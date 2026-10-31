#!/usr/bin/env python3
"""
Laddar ner alla bilder som inläggen använder till .cache/img/.
Bilder som redan finns hoppas över, så skriptet kan köras om.
Stora bilder krymps till max 1400 px breda för att hålla nere storleken
(GitHub Pages tillåter högst 1 GB per sajt).
"""
import io
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "data" / "posts"
CACHE = ROOT / ".cache" / "img"
MISSING_FILE = ROOT / "data" / "saknade-bilder.txt"
MAX_WIDTH = 1400

http = requests.Session()
http.headers["User-Agent"] = "Mozilla/5.0 (alvert-arkiv; privat kopia av egen blogg)"


def download(src):
    candidates = [src]
    if src.startswith("http://"):
        candidates.insert(0, "https://" + src[7:])
    for url in candidates:
        try:
            r = http.get(url, timeout=60)
            if r.status_code == 200 and r.content:
                return r.content
        except requests.RequestException:
            pass
    return None


def shrink(data, key):
    """Krymper JPEG/PNG/WebP som är bredare än MAX_WIDTH. GIF lämnas orörda."""
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        if fmt not in ("JPEG", "PNG", "WEBP") or img.width <= MAX_WIDTH:
            return data
        try:
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        h = round(img.height * MAX_WIDTH / img.width)
        img = img.resize((MAX_WIDTH, h), Image.LANCZOS)
        out = io.BytesIO()
        if fmt == "JPEG":
            img.convert("RGB").save(out, "JPEG", quality=84, optimize=True, progressive=True)
        else:
            img.save(out, fmt, optimize=True)
        return out.getvalue() if out.tell() < len(data) else data
    except Exception:
        return data


def fetch_one(key, src):
    data = download(src)
    if data is None:
        return key, src, False
    path = CACHE / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(shrink(data, key))
    return key, src, True


def main():
    wanted = {}
    for f in sorted(POSTS_DIR.glob("*.json")):
        for img in json.loads(f.read_text(encoding="utf-8")).get("images", []):
            wanted[img["key"]] = img["src"]
    todo = {k: v for k, v in wanted.items() if not (CACHE / k).exists()}
    print(f"{len(wanted)} bilder totalt, {len(wanted) - len(todo)} redan hämtade, {len(todo)} att hämta")

    missing, done = [], 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        for fut in as_completed([pool.submit(fetch_one, k, v) for k, v in todo.items()]):
            key, src, ok = fut.result()
            done += 1
            if not ok:
                missing.append(src)
            if done % 100 == 0:
                print(f"  {done}/{len(todo)}")

    MISSING_FILE.write_text("\n".join(sorted(missing)) + ("\n" if missing else ""), encoding="utf-8")
    size = sum(p.stat().st_size for p in CACHE.rglob("*") if p.is_file()) if CACHE.exists() else 0
    print(f"Klart. {len(todo) - len(missing)} nya bilder, {len(missing)} gick inte att hämta. "
          f"Totalt {size / 1e6:.0f} MB bilder.")


if __name__ == "__main__":
    main()
