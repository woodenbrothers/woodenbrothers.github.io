#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ré-héberge les photos des créations sur le site (au lieu du CDN d'Etsy).

Pour chaque photo listée dans data/products.json :
  * télécharge l'original (largeur 1588 px) dans .cache/images/src/<id>.jpg (une seule fois),
  * génère des versions WebP en 400, 800 et 1200 px de large, nommées d'après la création
    (ex. dessous-de-plat-chat-bois-1-800.webp) dans .cache/images/out/,
  * écrit .cache/images/manifest.json, utilisé par scripts/build.py.

Lancé automatiquement avant le build dans .github/workflows/static.yml (le cache
.cache/images est conservé entre deux déploiements). Sans Pillow ou sans accès
réseau, le script s'arrête proprement et le site utilise les photos du CDN Etsy.

    pip install pillow && python3 scripts/images.py
"""
import io
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "products.json"
CACHE = ROOT / ".cache" / "images"
SRC, OUT = CACHE / "src", CACHE / "out"
WIDTHS = (400, 800, 1200)
QUALITY = 82

try:
    from PIL import Image, ImageOps
except ImportError:
    print("Pillow absent (pip install pillow) : photos servies depuis le CDN Etsy.")
    sys.exit(0)


def etsy_id(url: str):
    m = re.search(r"/il_[0-9a-zA-Z]+x[0-9a-zA-Z]+\.(\d+)_", url or "")
    return m.group(1) if m else None


def download(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 1000:
        return True
    big = re.sub(r"il_[0-9a-zA-Z]+x[0-9a-zA-Z]+\.", "il_1588xN.", url, count=1)
    req = urllib.request.Request(big, headers={"User-Agent": "Mozilla/5.0 (compatible; woodenbrothers.fr build)"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                data = r.read()
            if len(data) < 1000:
                raise ValueError("réponse vide")
            dest.write_bytes(data)
            return True
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                print(f"  ! {url} : {e}")
                return False
            time.sleep(2 * (attempt + 1))
    return False


def main() -> int:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    SRC.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {}
    done = skipped = 0
    for p in data.get("products", []):
        slug = p.get("slug") or str(p["listing_id"])
        for n, url in enumerate(p.get("images", []), start=1):
            if url.startswith("/img/"):
                continue
            iid = etsy_id(url)
            if not iid:
                continue
            src = SRC / f"{iid}.jpg"
            if not download(url, src):
                skipped += 1
                continue
            base = f"/img/creations/{slug}-{n}"
            try:
                with Image.open(src) as im:
                    im = ImageOps.exif_transpose(im).convert("RGB")
                    w0, h0 = im.size
                    for w in WIDTHS:
                        target = OUT / f"{slug}-{n}-{w}.webp"
                        if target.exists() and target.stat().st_mtime >= src.stat().st_mtime:
                            continue
                        copy = im.copy()
                        if w0 > w:
                            copy.thumbnail((w, int(h0 * w / w0) + 1), Image.LANCZOS)
                        copy.save(target, "WEBP", quality=QUALITY, method=6)
                manifest[iid] = {"base": base, "width": w0, "height": h0}
                done += 1
            except Exception as e:  # noqa: BLE001
                print(f"  ! {src.name} : {e}")
                skipped += 1
    (CACHE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ {done} photo(s) ré-hébergées, {skipped} laissée(s) sur le CDN Etsy → {CACHE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
