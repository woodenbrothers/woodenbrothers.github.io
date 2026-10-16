#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Synchronise data/products.json avec la boutique Etsy (Open API v3).

Le script interroge l'API publique d'Etsy avec une simple clé d'application
(pas besoin de connexion OAuth) et met à jour le catalogue du site :

  * articles actifs de la boutique (titre, prix, lien, photos, quantité, section),
  * sections de la boutique (-> catégories du site),
  * informations de la boutique (note moyenne, nombre d'avis, favoris).

Les champs « éditoriaux » du catalogue (short_title, description, details,
kind, featured, free_shipping, hidden, category si category_locked) sont
conservés d'une synchronisation à l'autre : vous pouvez les retoucher à la
main dans data/products.json, ils ne seront pas écrasés.

Utilisation :
    ETSY_API_KEY=votre_cle python3 scripts/sync_etsy.py            # met à jour data/products.json
    ETSY_API_KEY=votre_cle python3 scripts/sync_etsy.py --dry-run  # affiche seulement ce qui changerait

Codes de sortie : 0 = ok (modifié ou non), 1 = erreur (le fichier n'est pas touché),
                  2 = clé API absente.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_BASE = "https://openapi.etsy.com/v3/application"
USER_AGENT = "woodenbrothers.fr catalogue sync (+https://www.woodenbrothers.fr)"
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "data" / "products.json"

# Champs du catalogue que la synchronisation ne doit jamais écraser.
EDITORIAL_FIELDS = ("short_title", "slug", "seo_title", "seo_description", "description", "description_long",
                    "details", "kind", "featured", "free_shipping", "hidden", "category_locked", "share_url")

# Règles de rattachement d'une section Etsy à une catégorie du site.
# (mot-clé normalisé contenu dans le titre de la section -> slug de catégorie)
SECTION_RULES = [
    ("pokemon", "cartes-pokemon"),
    ("carte", "cartes-pokemon"),
    ("anime", "manga-anime"),
    ("manga", "manga-anime"),
    ("animaux", "animaux"),
    ("animal", "animaux"),
    ("disney", "disney"),
    ("horloge", "horloges"),
    ("personnalis", "personnalise"),
    ("sur mesure", "personnalise"),
    ("custom", "personnalise"),
]

DEFAULT_DETAILS = {
    "dessous-de-plat": [
        "Dimensions : environ 20 cm de diamètre, épaisseur 2 cm",
        "Gravure fine et précise réalisée avec soin",
        "Bois massif sélectionné pour sa durabilité",
        "Vernis de protection pour une finition soignée et un entretien facile",
    ],
    "carte": [
        "Format carte à collectionner : 6,3 × 8,8 cm, épaisseur 0,6 cm",
        "Superposition de couches de bois pour un effet de relief 3D",
        "Gravure fine et précise réalisée avec soin",
    ],
    "horloge": ["Pièce unique au design original", "Bois naturel, finition soignée"],
    "autre": ["Pièce réalisée dans notre atelier"],
}


# --------------------------------------------------------------------------- #
# Outils
# --------------------------------------------------------------------------- #
def log(msg: str) -> None:
    print(msg, flush=True)


def normalize(text: str) -> str:
    """minuscules, sans accents, espaces simples"""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower()).strip()


def slugify(text: str) -> str:
    text = normalize(text)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "autres"


def api_get(path: str, api_key: str, params: dict | None = None, retries: int = 4):
    url = API_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    last_error: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"x-api-key": api_key,
                                                   "Accept": "application/json",
                                                   "User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = 2 ** attempt * 3
                log(f"  ! HTTP {e.code} sur {path}, nouvel essai dans {wait}s ({body})")
                time.sleep(wait)
                last_error = e
                continue
            hint = {
                401: "clé API invalide ou manquante (vérifiez le secret ETSY_API_KEY).",
                403: "accès refusé : l'application Etsy n'est peut-être pas encore approuvée, ou la ressource est privée.",
                404: "ressource introuvable (identifiant de boutique incorrect ?).",
            }.get(e.code, "")
            raise RuntimeError(f"HTTP {e.code} sur {path} : {hint} {body}".strip()) from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < retries - 1:
                wait = 2 ** attempt * 3
                log(f"  ! Erreur réseau sur {path} ({e}), nouvel essai dans {wait}s")
                time.sleep(wait)
                last_error = e
                continue
            raise RuntimeError(f"Erreur réseau sur {path} : {e}") from e
    raise RuntimeError(f"Échec sur {path} : {last_error}")


def safe_listing_url(api_url, old_url, lid: int) -> str:
    """URL de la fiche Etsy, limitée au domaine etsy.com en https (sinon URL canonique de l'article)."""
    for u in (api_url, old_url):
        if u and re.match(r"^https://([a-z0-9-]+\.)*etsy\.com/", u, re.I):
            return re.sub(r"\?.*$", "", u)
    return f"https://www.etsy.com/listing/{lid}"


def image_url(img: dict) -> str | None:
    """Retourne l'URL « 794xN » (largeur 794 px) de la photo, dérivée de l'URL fullxfull."""
    url = img.get("url_fullxfull") or img.get("url_570xN") or img.get("url_170x135")
    if not url or not re.match(r"^https://i\.etsystatic\.com/", url):
        return None
    return re.sub(r"il_[0-9a-zA-Z]+x[0-9a-zA-Z]+\.", "il_794xN.", url, count=1)


def short_title_from(title: str) -> str:
    # On garde la partie avant le premier séparateur « - », « – » ou « | ».
    part = re.split(r"\s+[-–—|]\s*|\s*[–—]\s*", title.strip(), maxsplit=1)[0]
    part = re.sub(r"\s+", " ", part).strip(" -–—|")
    return part[:70] if part else title[:70]


def kind_from(title: str) -> str:
    t = normalize(title)
    if "dessous de plat" in t or "dessous-de-plat" in t:
        return "dessous-de-plat"
    if "horloge" in t:
        return "horloge"
    if "carte" in t:
        return "carte"
    return "autre"


def description_from(text: str, limit: int = 320) -> str:
    text = re.sub(r"\r", "", text or "")
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    base = paragraphs[0] if paragraphs else text.strip()
    base = re.sub(r"\s+", " ", base)
    if len(base) <= limit:
        return base
    cut = base[:limit]
    m = re.search(r"^(.*[.!?])\s", cut)
    return (m.group(1) if m else cut.rstrip() + "…")


def category_from_section(section_id, sections: dict, categories: list, title: str) -> str | None:
    """Trouve le slug de catégorie correspondant à la section Etsy (ou au titre)."""
    # 1. correspondance explicite déclarée dans products.json
    for cat in categories:
        if section_id is not None and section_id in (cat.get("etsy_section_ids") or []):
            return cat["slug"]
    # 2. mots-clés sur le titre de la section
    sec_title = normalize(sections.get(section_id, "")) if section_id is not None else ""
    for keyword, slug in SECTION_RULES:
        if keyword in sec_title:
            return slug
    # 3. mots-clés sur le titre de l'article (ex. articles sans section)
    t = normalize(title)
    for keyword, slug in SECTION_RULES:
        if keyword in t and slug in ("personnalise",):
            return slug
    return None


# --------------------------------------------------------------------------- #
# Synchronisation
# --------------------------------------------------------------------------- #
def fetch_catalog(api_key: str, shop_id: int) -> tuple[dict, dict, list]:
    log(f"→ Boutique Etsy #{shop_id}")
    shop = {}
    try:
        shop = api_get(f"/shops/{shop_id}", api_key)
    except RuntimeError as e:
        log(f"  (infos boutique indisponibles : {e})")

    sections: dict = {}
    try:
        res = api_get(f"/shops/{shop_id}/sections", api_key)
        for s in res.get("results", []):
            sections[int(s["shop_section_id"])] = s.get("title") or ""
        log(f"  {len(sections)} section(s) : " + ", ".join(sections.values()))
    except RuntimeError as e:
        log(f"  (sections indisponibles : {e})")

    listings: list = []
    offset, limit = 0, 100
    while True:
        res = api_get(f"/shops/{shop_id}/listings/active", api_key,
                      {"limit": limit, "offset": offset, "sort_on": "created", "sort_order": "desc"})
        batch = res.get("results", [])
        listings.extend(batch)
        total = int(res.get("count", len(listings)))
        offset += limit
        if not batch or offset >= total or offset >= 2000:
            break
    log(f"  {len(listings)} article(s) actif(s)")

    # Photos : endpoint « batch » (1 requête pour 100 articles), repli par article.
    images_by_id: dict[int, list] = {}
    ids = [int(l["listing_id"]) for l in listings]
    for i in range(0, len(ids), 100):
        chunk = ids[i:i + 100]
        try:
            res = api_get("/listings/batch", api_key,
                          {"listing_ids": ",".join(map(str, chunk)), "includes": "Images"})
            for l in res.get("results", []):
                imgs = l.get("images") or []
                images_by_id[int(l["listing_id"])] = sorted(imgs, key=lambda x: x.get("rank", 0))
        except RuntimeError as e:
            log(f"  (lot de photos indisponible : {e}) → récupération article par article")
    for lid in ids:
        if lid in images_by_id:
            continue
        try:
            res = api_get(f"/listings/{lid}/images", api_key)
            images_by_id[lid] = sorted(res.get("results", []), key=lambda x: x.get("rank", 0))
        except RuntimeError as e:
            log(f"  (photos de l'article {lid} indisponibles : {e})")
            images_by_id[lid] = []
        time.sleep(0.15)

    for l in listings:
        l["_images"] = images_by_id.get(int(l["listing_id"]), [])
    return shop, sections, listings


def merge(data: dict, shop: dict, sections: dict, listings: list) -> dict:
    new = copy.deepcopy(data)
    categories = new.setdefault("categories", [])
    old_products = {int(p["listing_id"]): p for p in data.get("products", [])}

    # Nouvelles sections Etsy inconnues -> nouvelles catégories
    known_ids = {sid for c in categories for sid in (c.get("etsy_section_ids") or [])}
    for sid, title in sections.items():
        if sid in known_ids:
            continue
        slug = None
        for keyword, s in SECTION_RULES:
            if keyword in normalize(title):
                slug = s
                break
        target = next((c for c in categories if c["slug"] == slug), None) if slug else None
        if target is not None:
            target.setdefault("etsy_section_ids", []).append(sid)
            log(f"  + section « {title} » rattachée à la catégorie « {target['name']} »")
        else:
            categories.append({"slug": slugify(title), "name": title.strip().capitalize(),
                               "tagline": "", "etsy_section_ids": [sid], "image": None})
            log(f"  + nouvelle catégorie « {title} »")

    products = []
    used_slugs = set()
    for l in sorted(listings, key=lambda x: x.get("original_creation_timestamp") or x.get("creation_timestamp") or 0, reverse=True):
        lid = int(l["listing_id"])
        old = old_products.get(lid, {})
        title = (l.get("title") or "").strip()
        price = l.get("price") or {}
        try:
            amount = float(price.get("amount", 0)) / float(price.get("divisor") or 100)
        except (TypeError, ValueError):
            amount = old.get("price")
        images = [u for u in (image_url(i) for i in l.get("_images", [])) if u]
        if not images:
            images = old.get("images") or []
        section_id = l.get("shop_section_id")
        section_id = int(section_id) if section_id else None

        kind = old.get("kind") or kind_from(title)
        if old.get("category_locked") and old.get("category"):
            category = old["category"]
        else:
            category = (category_from_section(section_id, sections, categories, title)
                        or old.get("category") or "autres")
        if not any(c["slug"] == category for c in categories):
            categories.append({"slug": category, "name": category.replace("-", " ").capitalize(),
                               "tagline": "", "etsy_section_ids": [], "image": None})

        featured_rank = l.get("featured_rank")
        if isinstance(featured_rank, int):
            featured = featured_rank >= 0
        else:
            featured = bool(old.get("featured", False))

        short_title = old.get("short_title") or short_title_from(title)
        slug_base = old.get("slug") or slugify(short_title)
        slug, n = slug_base, 2
        while slug in used_slugs:
            slug, n = f"{slug_base}-{n}", n + 1
        used_slugs.add(slug)
        product = {
            "listing_id": lid,
            "title": title or old.get("title", ""),
            "short_title": short_title,
            "slug": slug,
            "category": category,
            "kind": kind,
            "price": round(amount, 2) if amount is not None else None,
            "currency": price.get("currency_code") or old.get("currency") or "EUR",
            "url": safe_listing_url(l.get("url"), old.get("url"), lid),
            "images": images,
            "description": old.get("description") or description_from(l.get("description", "")),
            "details": old.get("details") or DEFAULT_DETAILS.get(kind, DEFAULT_DETAILS["autre"]),
            "featured": featured,
            "free_shipping": bool(old.get("free_shipping", False)),
            "quantity": l.get("quantity"),
            "etsy_section_id": section_id,
            "created_timestamp": l.get("original_creation_timestamp") or l.get("creation_timestamp"),
        }
        for key in ("seo_title", "seo_description", "description_long", "share_url"):
            if old.get(key):
                product[key] = old[key]
        if old.get("hidden"):
            product["hidden"] = True
        if old.get("category_locked"):
            product["category_locked"] = True
        if l.get("is_customizable") or l.get("is_personalizable"):
            product["customizable"] = True
        products.append(product)

    removed = sorted(set(old_products) - {p["listing_id"] for p in products})
    added = sorted({p["listing_id"] for p in products} - set(old_products))
    if removed:
        # Les articles qui ne sont plus actifs (vendus, désactivés) sont conservés avec le statut
        # « unavailable » : leur page reste en ligne avec un bandeau, ils sortent des grilles.
        # Pour les retirer définitivement, ajoutez "hidden": true dans data/products.json.
        log("  − articles plus actifs sur Etsy, conservés en « indisponible » : " + ", ".join(str(r) for r in removed))
        for lid in removed:
            keep = copy.deepcopy(old_products[lid])
            keep["status"] = "unavailable"
            products.append(keep)
    if added:
        log("  + nouveaux articles : " + ", ".join(str(a) for a in added))

    # Image de couverture des catégories : première photo du premier article de la catégorie
    for cat in categories:
        first = next((p for p in products if p["category"] == cat["slug"] and p["images"]), None)
        if first and (not cat.get("image") or not any(cat["image"] in p["images"] for p in products)):
            cat["image"] = first["images"][0]

    new["products"] = products
    s = new.setdefault("shop", {})
    if shop:
        for key in ("review_average", "review_count", "num_favorers"):
            if shop.get(key) is not None:
                s[key] = shop[key]
        if shop.get("url"):
            s["url"] = shop["url"]
    new["source"] = "Etsy Open API v3 (synchronisation automatique)"
    return new


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default=str(DEFAULT_DATA), help="chemin du catalogue JSON")
    parser.add_argument("--dry-run", action="store_true", help="n'écrit rien, affiche seulement le résultat")
    args = parser.parse_args()

    api_key = (os.environ.get("ETSY_API_KEY") or "").strip()
    if not api_key:
        log("Aucune clé API : définissez la variable d'environnement ETSY_API_KEY (voir README.md).")
        return 2

    path = Path(args.data)
    data = json.loads(path.read_text(encoding="utf-8"))
    shop_id = int(data["shop"]["etsy_shop_id"])

    try:
        shop, sections, listings = fetch_catalog(api_key, shop_id)
    except RuntimeError as e:
        log(f"ERREUR : {e}")
        return 1
    if not listings:
        log("ERREUR : aucun article actif renvoyé par l'API, le catalogue n'est pas modifié par sécurité.")
        return 1

    new = merge(data, shop, sections, listings)

    def comparable(d: dict) -> dict:
        d = copy.deepcopy(d)
        d.pop("updated_at", None)
        return d

    if comparable(new) == comparable(data):
        log("✓ Catalogue déjà à jour, rien à faire.")
        return 0

    new["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if args.dry_run:
        log("(dry-run) Le catalogue serait mis à jour :")
        for p in new["products"]:
            log(f"   {p['listing_id']}  {p['price']} {p['currency']}  [{p['category']}]  {p['short_title']}")
        return 0

    path.write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"✓ {len(new['products'])} article(s) écrits dans {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
