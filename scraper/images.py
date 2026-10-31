#!/usr/bin/env python3
"""
Laddar ner alla bilder som inläggen använder och lägger dem i R2-bucketen.
Bilder som redan finns i bucketen hoppas över, så skriptet kan köras om.

Kräver miljövariablerna:
  CLOUDFLARE_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY
  (valfritt) R2_BUCKET, standard "alvert-bilder"
"""
import json
import mimetypes
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
import requests

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "data" / "posts"
MISSING_FILE = ROOT / "data" / "saknade-bilder.txt"
BUCKET = os.environ.get("R2_BUCKET", "alvert-bilder")

s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{os.environ['CLOUDFLARE_ACCOUNT_ID']}.r2.cloudflarestorage.com",
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    region_name="auto",
)
http = requests.Session()
http.headers["User-Agent"] = "Mozilla/5.0 (alvert-arkiv; privat kopia av egen blogg)"


def existing_keys():
    keys = set()
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET):
        for obj in page.get("Contents", []):
            keys.add(obj["Key"])
    return keys


def download(src):
    candidates = [src]
    if src.startswith("http://"):
        candidates.insert(0, "https://" + src[7:])
    for url in candidates:
        try:
            r = http.get(url, timeout=60)
            if r.status_code == 200 and r.content:
                return r.content, r.headers.get("content-type", "").split(";")[0]
        except requests.RequestException:
            pass
    return None, None


def copy_one(key, src):
    data, ctype = download(src)
    if data is None:
        return key, src, False
    if not ctype or not ctype.startswith("image/"):
        ctype = mimetypes.guess_type(key)[0] or "application/octet-stream"
    s3.put_object(Bucket=BUCKET, Key=key, Body=data, ContentType=ctype,
                  CacheControl="public, max-age=31536000, immutable")
    return key, src, True


def main():
    wanted = {}
    for f in sorted(POSTS_DIR.glob("*.json")):
        for img in json.loads(f.read_text(encoding="utf-8")).get("images", []):
            wanted[img["key"]] = img["src"]
    have = existing_keys()
    todo = {k: v for k, v in wanted.items() if k not in have}
    print(f"{len(wanted)} bilder totalt, {len(have)} finns i R2, {len(todo)} att ladda upp")

    missing, done = [], 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(copy_one, k, v) for k, v in todo.items()]
        for fut in as_completed(futures):
            key, src, ok = fut.result()
            done += 1
            if not ok:
                missing.append(src)
            if done % 100 == 0:
                print(f"  {done}/{len(todo)}")

    MISSING_FILE.write_text("\n".join(sorted(missing)) + ("\n" if missing else ""), encoding="utf-8")
    print(f"Klart. {len(todo) - len(missing)} uppladdade, {len(missing)} gick inte att hämta "
          f"(se data/saknade-bilder.txt)")


if __name__ == "__main__":
    sys.exit(main())
