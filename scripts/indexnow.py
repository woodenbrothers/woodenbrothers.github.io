#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Signale les URL du site aux moteurs compatibles IndexNow (Bing, Yandex, Naver,
Seznam… ; l'index Bing alimente aussi ChatGPT search et Copilot).

Appelé après chaque déploiement par .github/workflows/static.yml :
    python3 scripts/indexnow.py _site/sitemap.xml

La clé est le nom du fichier <clé>.txt à la racine du dépôt (fichier public,
c'est le fonctionnement normal d'IndexNow).
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = "www.woodenbrothers.fr"


def main() -> int:
    sitemap = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "_site" / "sitemap.xml")
    keys = [f for f in ROOT.glob("*.txt") if re.fullmatch(r"[0-9a-f]{32}", f.stem)]
    if not keys:
        print("Aucun fichier clé IndexNow (<clé>.txt) à la racine : étape ignorée.")
        return 0
    key = keys[0].stem
    urls = re.findall(r"<loc>(.*?)</loc>", sitemap.read_text(encoding="utf-8"))
    if not urls:
        print("Sitemap vide : rien à soumettre.")
        return 0
    payload = {"host": HOST, "key": key, "keyLocation": f"https://{HOST}/{key}.txt", "urlList": urls[:10000]}
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"IndexNow : HTTP {resp.status}, {len(urls)} URL soumises.")
    except urllib.error.HTTPError as e:
        print(f"IndexNow : HTTP {e.code} ({e.read().decode('utf-8', 'replace')[:200]})")
        return 0  # ne bloque jamais le déploiement
    return 0


if __name__ == "__main__":
    sys.exit(main())
