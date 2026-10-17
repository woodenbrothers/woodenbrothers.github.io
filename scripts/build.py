#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Construit le site publiable dans _site/ à partir des fichiers sources du dépôt.

  python3 scripts/build.py            # génère _site/
  npx serve _site                     # aperçu local

Ce que fait le build :
  * copie les pages et ressources du dépôt (les pages HTML à la racine restent
    les sources que vous éditez) ;
  * injecte dans index.html et produits.html les grilles de produits pré-rendues
    (entre les marqueurs <!-- wb:... --> / <!-- /wb:... -->) pour que le contenu
    soit lisible par Google et les IA sans JavaScript ;
  * génère une page par création (/creations/<slug>/) et une page par collection
    (/collections/<slug>/) avec données structurées (schema.org) ;
  * génère sitemap.xml et llms.txt.

L'en-tête et le pied de page des pages générées sont extraits de index.html
(marqueurs wb:header / wb:footer) : modifiez-les dans index.html, le build suit.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "_site"
DATA = ROOT / "data" / "products.json"
REVIEWS = ROOT / "data" / "reviews.json"              # avis clients (saisis vous-même ou récupérés par la synchro Etsy)
SITE = "https://www.woodenbrothers.fr"
BRAND = "Wooden Brothers"
ETSY_SHOP = "https://www.etsy.com/fr/shop/WoodenBrothersArt"

IMAGES_CACHE = ROOT / ".cache" / "images"                  # produit par scripts/images.py (photos ré-hébergées)
SIZE_TO_WIDTH = {"75x75": 400, "170x135": 400, "300x300": 400, "340x270": 400, "570xN": 800, "600x600": 800,
                 "794xN": 800, "800x800": 800, "1140xN": 1200, "1588xN": 1200, "fullxfull": 1200}
_manifest: dict = {}
SKIP = {".git", ".github", "_site", "scripts", "README.md", ".gitignore", "sitemap.xml", "__pycache__", ".DS_Store"}

ICON_EXT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17 17 7M8 7h9v9"/></svg>'
ICON_PREV = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 5-7 7 7 7"/></svg>'
ICON_NEXT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 5 7 7-7 7"/></svg>'
ICON_CHECK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/></svg>'

MADE_IN_FR = "Fabriqué dans notre atelier et expédié depuis la France"
MADE_IN_FR_LONG = ("Toutes nos créations sont dessinées et fabriquées dans notre atelier, puis expédiées depuis la France, "
                   "soigneusement emballées. Les délais et frais de livraison sont indiqués sur chaque fiche Etsy.")

# Livraison et retours déclarés à Google (données « fiches de marchand »). Surcharge dans data/products.json, clé shop :
#   "shipping": {"country": "FR", "rate": 4.9, "currency": "EUR", "handling_days": [1, 3], "transit_days": [2, 5]}
#   "returns": {"country": "FR", "days": 14, "fees": "customer"}        (fees : "customer" ou "free")
SHIPPING_DEFAULTS = {"country": "FR", "rate": None, "currency": "EUR", "handling_days": None, "transit_days": None}
RETURNS_DEFAULTS = {"country": "FR", "days": 14, "fees": "customer"}

# Textes par type de pièce (modifiables)
KINDS = {
    "dessous-de-plat": {
        "label": "Dessous de plat",
        "plural": "dessous de plat",
        "subtitle": "Dessous de plat en bois de Paulownia, gravé dans notre atelier en France",
        "title": "{name} en bois gravé | Wooden Brothers",
        "ld_name": "{name} en bois gravé",
        "alt": "{name} en bois gravé",
        "caption": "{name} : rondin de Paulownia gravé dans notre atelier, fabriqué et expédié depuis la France.",
        "why": [
            "Un véritable rondin de Paulownia, écorce comprise : chaque pièce est unique",
            "Protège votre table des plats chauds tout en décorant la cuisine",
            "Motif dessiné par nos soins et gravé avec finesse, vernis de protection",
        ],
        "wood": "Nos dessous de plat sont découpés dans des rondins de Paulownia, un bois naturellement léger, résistant et élégant, qui pousse vite et stocke beaucoup de CO₂. Son grain clair met en valeur la gravure.",
        "care": "Un chiffon doux légèrement humide suffit. Évitez le lave-vaisselle et les immersions prolongées : le bois est une matière vivante qui n'aime pas l'eau stagnante. Laissez sécher à plat, à l'abri d'une source de chaleur directe.",
        "gift": "Un cadeau utile et décoratif pour une pendaison de crémaillère, un anniversaire, Noël, la fête des mères ou des pères. Il se glisse facilement dans un paquet et ne craint pas le transport.",
        "faq": [
            ("Quelles sont les dimensions ?", "Environ 20 cm de diamètre pour 2 cm d'épaisseur. Chaque rondin étant naturel, le diamètre et la forme varient légèrement d'une pièce à l'autre."),
            ("Peut-on poser un plat très chaud dessus ?", "Oui, c'est son rôle : il protège la table des plats et casseroles sortant du four. Évitez simplement le contact direct avec une flamme ou une plaque brûlante pendant une longue durée."),
            ("Le motif peut-il être personnalisé ?", "Oui : nous proposons un dessous de plat personnalisé gravé d'après votre photo, votre dessin ou votre texte. Voir la collection « Sur mesure »."),
            ("D'où est-il expédié ?", "De France. Chaque dessous de plat est fabriqué dans notre atelier puis expédié depuis la France, soigneusement emballé. Les délais et frais de livraison sont indiqués sur la fiche Etsy."),
        ],
    },
    "carte": {
        "label": "Carte Pokémon en bois 3D",
        "plural": "cartes Pokémon en bois 3D",
        "subtitle": "Carte Pokémon en bois 3D gravée en relief, format carte à collectionner",
        "title": "{name} en bois 3D | Wooden Brothers",
        "ld_name": "{name} en bois 3D",
        "alt": "{name} en bois 3D",
        "caption": "{name} en bois 3D : couches de bois gravées puis superposées dans notre atelier, fabriquée et expédiée depuis la France.",
        "why": [
            "Format carte à collectionner (6,3 × 8,8 cm), relief 3D par superposition de couches de bois",
            "Un objet de collection original, à exposer ou à offrir, dès 5,99 €",
            "Modèle dessiné par nos soins, gravure fine et assemblage soigné",
        ],
        "wood": "Chaque carte est composée de plusieurs couches de bois fin, découpées et gravées puis superposées pour créer la profondeur. Le bois naturel donne à chaque exemplaire des nuances de teinte qui lui sont propres.",
        "care": "À conserver à l'abri de l'humidité et du soleil direct, comme une carte à collectionner classique. Un dépoussiérage avec un chiffon sec suffit.",
        "gift": "Le petit cadeau Pokémon qui change : pour un anniversaire, un calendrier de l'avent, une pochette surprise, ou pour compléter la collection d'un dresseur. Il se glisse dans une enveloppe.",
        "faq": [
            ("Est-ce une carte Pokémon officielle ?", "Non. Il s'agit d'une création artisanale en bois, un fan art dessiné par nos soins. Elle n'est pas affiliée à The Pokémon Company et ne se joue pas."),
            ("Quelle est sa taille ?", "6,3 cm de large sur 8,8 cm de haut, soit le format d'une carte à collectionner, pour environ 0,6 cm d'épaisseur avec le relief."),
            ("Puis-je demander un autre Pokémon ?", "Oui : commandez notre carte Pokémon sur mesure en indiquant le Pokémon souhaité. Nous le dessinons, le gravons et l'assemblons en relief 3D, quelle que soit sa génération."),
            ("D'où est-elle expédiée ?", "De France. Chaque carte est fabriquée dans notre atelier puis expédiée depuis la France, protégée pour le transport. Les délais et frais de livraison sont indiqués sur la fiche Etsy."),
        ],
    },
    "horloge": {
        "label": "Horloge murale",
        "plural": "horloges",
        "subtitle": "Horloge murale en bois conçue et fabriquée dans notre atelier en France",
        "title": "{name} artisanale | Wooden Brothers",
        "ld_name": "{name}",
        "alt": "{name}",
        "caption": "{name} conçue et fabriquée dans notre atelier, expédiée depuis la France. Livraison offerte.",
        "why": [
            "Une pièce unique en bois naturel, conçue et fabriquée dans notre atelier",
            "Habille un salon, une entrée ou une cuisine avec chaleur et caractère",
            "Livraison offerte sur ce modèle",
        ],
        "wood": "Le bois naturel et la gravure font de chaque horloge une pièce différente de la précédente : grain, nuances de teinte et finition sont propres à chaque exemplaire.",
        "care": "Dépoussiérez avec un chiffon doux et sec. Évitez l'exposition prolongée à l'humidité ou au soleil direct pour préserver la teinte du bois.",
        "gift": "Un cadeau déco qui marque les esprits : crémaillère, mariage, Noël ou anniversaire.",
        "faq": [
            ("Les piles sont-elles fournies ?", "Consultez la fiche Etsy pour les détails de livraison et de mécanisme ; nous y répondons aussi à toutes vos questions avant commande."),
            ("Comment est-elle livrée ?", "Soigneusement emballée pour protéger le bois pendant le transport, et expédiée depuis la France. La livraison est offerte sur ce modèle."),
        ],
    },
    "autre": {
        "label": "Création en bois",
        "plural": "créations",
        "subtitle": "Création en bois conçue et fabriquée dans notre atelier en France",
        "title": "{name} | Wooden Brothers",
        "ld_name": "{name}",
        "alt": "{name}",
        "caption": "{name}, fabriqué dans notre atelier et expédié depuis la France.",
        "why": ["Pièce conçue et réalisée dans notre atelier", "Bois naturel, finition soignée", "Design original Wooden Brothers"],
        "wood": "Nous travaillons des bois naturels sélectionnés pour leur grain et leur résistance.",
        "care": "Un chiffon doux et sec suffit pour l'entretien courant.",
        "gift": "Une idée cadeau originale, conçue dans notre atelier.",
        "faq": [],
    },
}


# --------------------------------------------------------------------------- #
# Outils
# --------------------------------------------------------------------------- #
def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def etsy_image_id(url: str) -> str | None:
    m = re.search(r"/il_[0-9a-zA-Z]+x[0-9a-zA-Z]+\.(\d+)_", url or "")
    return m.group(1) if m else None


def img_size(url: str, size: str) -> str:
    """URL d'une photo dans la taille demandée : version locale (WebP) si elle a été
    générée par scripts/images.py, sinon la taille correspondante sur le CDN Etsy."""
    if not url:
        return ""
    local = re.match(r"^(/img/creations/.+)-(\d+)\.webp$", url)
    if local:
        return f"{local.group(1)}-{SIZE_TO_WIDTH.get(size, 800)}.webp"
    entry = _manifest.get(etsy_image_id(url) or "")
    if entry:
        return f"{entry['base']}-{SIZE_TO_WIDTH.get(size, 800)}.webp"
    return re.sub(r"il_[0-9a-zA-Z]+x[0-9a-zA-Z]+\.", f"il_{size}.", url, count=1)


ETSY_URL_RE = re.compile(r"^https://([a-z0-9-]+\.)*etsy\.com/", re.I)
IMAGE_URL_RE = re.compile(r"^(/img/creations/[a-z0-9-]+-\d+-\d+\.webp|https://i\.etsystatic\.com/[A-Za-z0-9_./-]+)$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")


def safe_slug(value: str, fallback: str) -> str:
    return value if value and SLUG_RE.fullmatch(value) else slugify(fallback)


def etsy_url(p: dict) -> str:
    """Lien Etsy de l'article : lien traçable « Share & Save » s'il est renseigné.
    Seules les adresses https sur etsy.com sont acceptées (sinon : la boutique)."""
    for u in (p.get("share_url"), p.get("url")):
        if u and ETSY_URL_RE.match(u):
            return u
    return ETSY_SHOP


def price_fmt(p, cur="EUR") -> str:
    if p is None:
        return ""
    s = f"{float(p):,.2f}".replace(",", " ").replace(".", ",")
    return f"{s} €" if cur == "EUR" else f"{s} {cur}"


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "creation"


def truncate(text: str, n: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= n:
        return text
    cut = text[: n - 1]
    return cut[: cut.rfind(" ")].rstrip(" ,;:") + "…"


def paragraphs(text: str, cls: str = "") -> str:
    attr = f' class="{cls}"' if cls else ""
    return "".join(f"<p{attr}>{esc(p.strip())}</p>" for p in re.split(r"\n\s*\n", text or "") if p.strip())


def extract(src: str, name: str) -> str:
    m = re.search(rf"<!-- wb:{name} -->(.*?)<!-- /wb:{name} -->", src, re.S)
    if not m:
        sys.exit(f"Marqueur wb:{name} introuvable dans index.html")
    return m.group(1)


def inject(src: str, name: str, fragment: str) -> str:
    pattern = re.compile(rf"(<!-- wb:{name} -->).*?(<!-- /wb:{name} -->)", re.S)
    if not pattern.search(src):
        sys.exit(f"Marqueur wb:{name} introuvable")
    return pattern.sub(lambda m: m.group(1) + fragment + m.group(2), src, count=1)


def git_date(*paths) -> str | None:
    """Date (AAAA-MM-JJ) du dernier commit touchant l'un des fichiers, ou None hors dépôt git."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", *[str(p) for p in paths]],
                             cwd=ROOT, capture_output=True, text=True, timeout=20)
        return out.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def asset_hash(rel: str) -> str:
    f = ROOT / rel.lstrip("/")
    return hashlib.sha1(f.read_bytes()).hexdigest()[:8] if f.exists() else ""


def fingerprint(html_text: str) -> str:
    """Ajoute ?v=<empreinte> aux feuilles de style et scripts du site (cache des robots)."""
    for rel in ("/assets/css/fonts.css", "/assets/css/style.css", "/assets/js/site.js", "/assets/js/catalogue.js"):
        h = asset_hash(rel)
        if h:
            html_text = html_text.replace(f'"{rel}"', f'"{rel}?v={h}"')
    return html_text


def jsonld(obj) -> str:
    # « </ » et « <!-- » sont échappés pour qu'aucune donnée ne puisse fermer la balise <script>
    txt = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/").replace("<!--", "<\\!--")
    return '<script type="application/ld+json">' + txt + "</script>"


# --------------------------------------------------------------------------- #
# Catalogue
# --------------------------------------------------------------------------- #
class Catalogue:
    def __init__(self, data: dict):
        self.data = data
        self.shop = data.get("shop", {})
        self.all_products = [p for p in data.get("products", []) if not p.get("hidden") and p.get("price") is not None]
        self.products = [p for p in self.all_products if p.get("status") != "unavailable"]   # affichés dans les grilles
        self.categories = data.get("categories", [])
        self.virtual = data.get("collections_virtuelles", [])
        self.cat_by_slug = {c["slug"]: c for c in self.categories}
        for c in self.categories + self.virtual:
            c["slug"] = safe_slug(c.get("slug", ""), c.get("name", "collection"))
        used = set()
        for p in self.all_products:
            p["images"] = [u for u in p.get("images", []) if isinstance(u, str) and IMAGE_URL_RE.match(u)]
            base = safe_slug(p.get("slug", ""), p.get("short_title") or p.get("title") or str(p["listing_id"]))
            s, i = base, 2
            while s in used:
                s, i = f"{base}-{i}", i + 1
            used.add(s)
            p["slug"] = s
            p["page_url"] = f"/creations/{s}/"
            if not p.get("kind"):
                p["kind"] = "autre"
        self.by_id = {str(p["listing_id"]): p for p in self.all_products}

    def in_category(self, slug: str) -> list:
        return [p for p in self.products if p["category"] == slug]

    def in_collection(self, col: dict) -> list:
        if col.get("kind"):
            return [p for p in self.products if p["kind"] == col["kind"]]
        return self.in_category(col["slug"])

    def collections(self) -> list:
        """Catégories (non vides) + collections virtuelles, avec leurs produits."""
        out = []
        for c in self.categories:
            items = self.in_category(c["slug"])
            if items:
                out.append((c, items))
        for c in self.virtual:
            items = self.in_collection(c)
            if items:
                out.append((c, items))
        return out


def badges(p: dict) -> list:
    b = []
    if p.get("quantity") == 1:
        b.append(("Dernier exemplaire", "badge--alert"))
    if p.get("free_shipping"):
        b.append(("Livraison offerte", "badge--wood"))
    if p.get("category") == "personnalise" or p.get("customizable"):
        b.append(("Sur mesure", ""))
    return b


def product_card(p: dict, cat: Catalogue, show_category=True, reveal=True, eager=False, sizes=None) -> str:
    """Même structure que WB.productCard dans assets/js/site.js."""
    c = cat.cat_by_slug.get(p["category"])
    img0 = p["images"][0] if p.get("images") else None
    img1 = p["images"][1] if len(p.get("images") or []) > 1 else None
    sizes = sizes or "(max-width: 640px) 50vw, (max-width: 1100px) 33vw, 300px"
    title = esc(p.get("short_title") or p.get("title"))
    b = "".join(f'<span class="badge {cls}">{esc(t)}</span>' for t, cls in badges(p))
    srcset = f"{img_size(img0, '300x300')} 300w, {img_size(img0, '600x600')} 600w, {img_size(img0, '800x800')} 800w" if img0 else ""
    return (
        f'<article class="product-card" data-id="{p["listing_id"]}" data-category="{esc(p["category"])}"{" data-reveal" if reveal else ""}>'
        f'<div class="product-card__media">'
        f'<a class="product-card__link" href="{p["page_url"]}">'
        + (f'<img class="product-card__img" src="{esc(img_size(img0, "600x600"))}" srcset="{esc(srcset)}" sizes="{esc(sizes)}" alt="{title}" width="600" height="600" loading="{"eager" if eager else "lazy"}" decoding="async">' if img0 else "")
        + (f'<img class="product-card__img product-card__img--alt" src="{esc(img_size(img1, "600x600"))}" alt="" width="600" height="600" loading="lazy" decoding="async" aria-hidden="true">' if img1 else "")
        + "</a>"
        + (f'<span class="product-card__badges">{b}</span>' if b else "")
        + f'<button type="button" class="product-card__quick btn btn--light btn--sm" data-quickview="{p["listing_id"]}">Aperçu rapide</button>'
        + "</div>"
        f'<div class="product-card__body">'
        + (f'<span class="product-card__cat">{esc(c["name"])}</span>' if c and show_category else "")
        + f'<h3 class="product-card__title"><a href="{p["page_url"]}">{title}</a></h3>'
        f'<p class="product-card__price">{esc(price_fmt(p["price"], p.get("currency", "EUR")))}</p>'
        "</div>"
        f'<div class="product-card__actions">'
        f'<a class="btn btn--secondary btn--sm" href="{p["page_url"]}">Détails</a>'
        f'<a class="btn btn--primary btn--sm" href="{esc(etsy_url(p))}" target="_blank" rel="noopener">Commander sur Etsy</a>'
        "</div></article>"
    )


def chips(cat: Catalogue, active: str) -> str:
    out = [f'<a class="chip{" is-active" if active == "all" else ""}" href="/produits" data-filter="all">Tout <span class="chip__count">{len(cat.products)}</span></a>']
    for c, items in cat.collections():
        slug = c["slug"]
        out.append(f'<a class="chip{" is-active" if active == slug else ""}" href="/collections/{slug}/" data-filter="{slug}"{" data-kind=\"" + c["kind"] + "\"" if c.get("kind") else ""}>{esc(c["name"])} <span class="chip__count">{len(items)}</span></a>')
    return "".join(out)


# --------------------------------------------------------------------------- #
# Avis clients (data/reviews.json)
# --------------------------------------------------------------------------- #
ICON_STAR = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2.6l2.9 6 6.6.9-4.8 4.6 1.2 6.6-5.9-3.2-5.9 3.2 1.2-6.6L2.5 9.5l6.6-.9z"/></svg>'
MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
REVIEWS_LEAD = "Des avis déposés sur notre boutique Etsy par des clients qui ont reçu leur création."
_reviews: dict = {"items": [], "url": ETSY_SHOP + "/reviews"}


def load_reviews() -> dict:
    """Avis clients : entrées « manuel » (recopiées d'Etsy) + entrées « etsy » (synchronisation). Seuls les avis
    avec une note de 1 à 5 et un texte sont affichés ; les doublons sont ignorés."""
    out = {"items": [], "url": ETSY_SHOP + "/reviews"}
    if not REVIEWS.exists():
        return out
    try:
        data = json.loads(REVIEWS.read_text(encoding="utf-8"))
    except ValueError as e:
        sys.exit(f"data/reviews.json illisible : {e}")
    url = data.get("etsy_reviews_url")
    if isinstance(url, str) and ETSY_URL_RE.match(url):
        out["url"] = url
    seen = set()
    for source in ("manuel", "etsy"):
        for r in data.get(source) or []:
            if not isinstance(r, dict):
                continue
            rating, text = r.get("rating"), re.sub(r"\s+", " ", str(r.get("text") or "")).strip()
            if isinstance(rating, bool) or not isinstance(rating, (int, float)) or not 1 <= rating <= 5 or not text:
                continue
            key = (text.lower(), str(r.get("listing_id") or ""))
            if key in seen:
                continue
            seen.add(key)
            d = str(r.get("date") or "")
            out["items"].append({
                "rating": int(round(rating)),
                "text": text[:600],
                "author": re.sub(r"\s+", " ", str(r.get("author") or "")).strip()[:40],
                "date": d if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) else "",
                "listing_id": str(r.get("listing_id") or ""),
                "source": source,
            })
    out["items"].sort(key=lambda r: (r["date"], r["rating"]), reverse=True)
    return out


def pick_reviews(n: int, listing_ids=None) -> list:
    """Les n avis à montrer : meilleures notes d'abord, puis textes de longueur agréable, puis les plus récents."""
    pool = [r for r in _reviews["items"] if not listing_ids or r["listing_id"] in listing_ids]
    return sorted(pool, key=lambda r: (r["rating"], 1 if 40 <= len(r["text"]) <= 420 else 0, r["date"]), reverse=True)[:n]


def fr_month(iso: str) -> str:
    try:
        y, m = iso.split("-")[:2]
        return f"{MONTHS_FR[int(m) - 1]} {y}"
    except (ValueError, IndexError):
        return ""


def stars(rating: float, label: str | None = None) -> str:
    """Cinq étoiles (pleines, demi, vides) ; note arrondie au demi-point ; libellé pour les lecteurs d'écran."""
    half = round(max(0.0, min(5.0, float(rating))) * 2)
    full, has_half = divmod(half, 2)
    classes = ["star--on"] * full + (["star--half"] if has_half else []) + ["star--off"] * (5 - full - has_half)
    label = label or f"{str(round(float(rating), 1)).replace('.', ',')} sur 5"
    return (f'<span class="stars" role="img" aria-label="{esc(label)}">'
            + "".join(f'<span class="star {c}">{ICON_STAR}{ICON_STAR if c == "star--half" else ""}</span>' for c in classes)
            + "</span>")


def review_summary(cat: Catalogue, variant: str = "") -> str:
    """Bandeau « note moyenne » : note et nombre d'avis de la boutique Etsy quand ils sont connus
    (synchronisation Etsy ou champs shop.review_average / shop.review_count de data/products.json),
    sinon simple rappel des avis affichés. Vide s'il n'y a aucun avis."""
    avg, count = cat.shop.get("review_average"), cat.shop.get("review_count")
    url = esc(_reviews["url"])
    if isinstance(avg, (int, float)) and not isinstance(avg, bool) and isinstance(count, int) and count > 0 and 1 <= avg <= 5:
        note = str(round(float(avg), 1)).replace(".", ",")
        return (f'<a class="review-strip{variant}" href="{url}" target="_blank" rel="noopener">{stars(avg, f"{note} sur 5")}'
                f'<span><strong>{note}/5</strong> · {count} avis client{"s" if count > 1 else ""} sur Etsy</span></a>')
    if _reviews["items"]:
        avg_items = sum(r["rating"] for r in _reviews["items"]) / len(_reviews["items"])
        return (f'<a class="review-strip{variant}" href="{url}" target="_blank" rel="noopener">{stars(avg_items)}'
                f'<span><strong>Avis clients vérifiés</strong> · lire sur Etsy</span></a>')
    return ""


def review_card(r: dict, cat: Catalogue, show_product: bool = True) -> str:
    p = cat.by_id.get(r["listing_id"]) if show_product else None
    who = esc(r["author"] or "Client Etsy")
    when = fr_month(r["date"])
    about = f'<a class="review__product" href="{p["page_url"]}">{esc(p.get("short_title") or p["title"])}</a>' if p else ""
    return (f'<figure class="review">{stars(r["rating"], f"{r['rating']} étoile{'s' if r['rating'] > 1 else ''} sur 5")}'
            f'<blockquote class="review__text"><p>{esc(r["text"])}</p></blockquote>'
            f'<figcaption class="review__meta"><span class="review__author">{who}</span>'
            + (f'<span>{esc(when)}</span>' if when else "") + about
            + '<span class="review__source">Avis Etsy</span></figcaption></figure>')


def reviews_section(cat: Catalogue, n: int = 6, listing_ids=None, eyebrow: str = "Avis clients",
                    title: str = "Ils ont reçu <em>leur création</em>", lead: str | None = None,
                    alt: bool = True, show_product: bool = True) -> str:
    """Section « avis clients » complète, ou chaîne vide s'il n'y a rien à montrer."""
    picked = pick_reviews(n, listing_ids)
    if not picked:
        return ""
    return f"""<section class="section section--tight{' section--alt' if alt else ''}" id="avis">
    <div class="container">
      <div class="section__head">
        <span class="eyebrow">{esc(eyebrow)}</span>
        <h2>{title}</h2>
        {('<p class="section__lead">' + esc(lead) + '</p>') if lead else ''}
        {review_summary(cat)}
      </div>
      <div class="reviews">{''.join(review_card(r, cat, show_product) for r in picked)}</div>
      <p class="section__foot"><a class="btn btn--secondary" href="{esc(_reviews['url'])}" target="_blank" rel="noopener">Lire tous les avis sur Etsy {ICON_EXT}</a></p>
    </div>
  </section>
"""


# --------------------------------------------------------------------------- #
# Gabarits
# --------------------------------------------------------------------------- #
FAVICONS = """<link rel="icon" type="image/png" sizes="32x32" href="/Images/logo32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/Images/logo16.png">
<link rel="icon" type="image/png" sizes="48x48" href="/Images/logo48.png">
<link rel="icon" type="image/png" sizes="192x192" href="/Images/logo192.png">
<link rel="icon" type="image/png" sizes="512x512" href="/Images/logo512.png">
<link rel="apple-touch-icon" sizes="180x180" href="/Images/logo192.png">"""


def head(title: str, desc: str, path: str, image: str | None = None, extra: str = "", og_type="website") -> str:
    image = image or f"{SITE}/og-image.jpg"
    return f"""<!DOCTYPE html>
<html lang="fr" class="no-js">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="author" content="{BRAND}">
{'' if 'noindex' in extra else '<meta name="robots" content="index, follow, max-image-preview:large">'}
<link rel="canonical" href="{SITE}{path}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="{BRAND}">
<meta property="og:locale" content="fr_FR">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:image" content="{esc(image)}">
<meta property="og:url" content="{SITE}{path}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#2F5B37">
<meta name="p:domain_verify" content="dc20c129c06bf8a643d454ab923d57de">
{FAVICONS}
<link rel="preconnect" href="https://i.etsystatic.com">
<link rel="preload" href="/assets/fonts/fraunces-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/fonts.css">
<link rel="stylesheet" href="/assets/css/style.css">
<script>document.documentElement.classList.replace('no-js', 'js');</script>
{extra}
</head>
"""


def set_active(header: str, href: str) -> str:
    header = header.replace(' aria-current="page"', "")
    return header.replace(f'<a href="{href}" class="nav__link">', f'<a href="{href}" class="nav__link" aria-current="page">', 1)


def breadcrumb(items: list) -> str:
    """items = [(label, href|None), ...]"""
    lis = []
    for label, href in items:
        if href:
            lis.append(f'<li><a href="{href}">{esc(label)}</a></li>')
        else:
            lis.append(f'<li aria-current="page">{esc(label)}</li>')
    return f'<nav class="breadcrumb" aria-label="Fil d\'Ariane"><ol>{"".join(lis)}</ol></nav>'


def breadcrumb_ld(items: list) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": label, **({"item": SITE + href} if href else {})}
            for i, (label, href) in enumerate(items)
        ],
    }


def faq_html(items: list) -> str:
    return '<div class="faq">' + "".join(
        f"<details{' open' if i == 0 else ''}><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for i, (q, a) in enumerate(items)
    ) + "</div>"


def product_page(p: dict, cat: Catalogue, header: str, footer: str) -> str:
    kind = KINDS.get(p["kind"], KINDS["autre"])
    c = cat.cat_by_slug.get(p["category"], {"name": "Nos créations", "slug": ""})
    name = p.get("short_title") or p["title"]
    images = p.get("images") or []
    alt = kind["alt"].format(name=name)
    title = p.get("seo_title") or kind["title"].format(name=name)
    desc = p.get("seo_description") or truncate(f"{p.get('description', '')} {price_fmt(p['price'])}. Création Wooden Brothers, disponible sur Etsy.", 155)
    crumbs = [("Accueil", "/"), ("Nos créations", "/produits"), (c["name"], f"/collections/{c['slug']}/" if c.get("slug") else None), (name, None)]
    b = badges(p)
    related = [x for x in cat.in_category(p["category"]) if x["listing_id"] != p["listing_id"]][:4]
    if len(related) < 4:
        related += [x for x in cat.products if x["category"] != p["category"] and x["kind"] == p["kind"] and x not in related][: 4 - len(related)]
    other_cols = [(c2, items) for c2, items in cat.collections() if c2["slug"] != c.get("slug")][:6]

    unavailable = p.get("status") == "unavailable"
    reviews_html = (reviews_section(cat, 3, listing_ids={str(p["listing_id"])}, title="Avis sur <em>cette création</em>", show_product=False)
                    or reviews_section(cat, 3, title="Ce que disent <em>nos clients</em>", lead="Avis déposés sur notre boutique Etsy, toutes créations confondues."))
    product_ld = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": kind["ld_name"].format(name=name),
        "image": [img_size(u, "1588xN") for u in images[:6]],
        "description": p.get("description", ""),
        "sku": str(p["listing_id"]),
        "brand": {"@type": "Brand", "name": BRAND},
        "material": "Bois de Paulownia" if p["kind"] == "dessous-de-plat" else "Bois",
        "category": kind["label"],
        "countryOfOrigin": {"@type": "Country", "name": "FR"},
        "url": SITE + p["page_url"],
        "offers": {
            "@type": "Offer",
            "url": etsy_url(p),
            "priceCurrency": p.get("currency", "EUR"),
            "price": f"{float(p['price']):.2f}",
            "availability": "https://schema.org/OutOfStock" if unavailable else "https://schema.org/InStock",
            "itemCondition": "https://schema.org/NewCondition",
            "seller": {"@type": "Organization", "name": BRAND, "url": SITE + "/"},
        },
    }
    # Livraison et retours (réglables dans data/products.json, voir SHIPPING_DEFAULTS / RETURNS_DEFAULTS)
    shipping = {**SHIPPING_DEFAULTS, **(cat.shop.get("shipping") or {})}
    returns = {**RETURNS_DEFAULTS, **(cat.shop.get("returns") or {})}
    ship = {"@type": "OfferShippingDetails", "shippingDestination": {"@type": "DefinedRegion", "addressCountry": shipping["country"]}}
    rate = 0 if p.get("free_shipping") else shipping.get("rate")
    if rate is not None:
        ship["shippingRate"] = {"@type": "MonetaryAmount", "value": f"{float(rate):.2f}", "currency": shipping.get("currency") or "EUR"}
    delivery = {}
    for key, prop in (("handling_days", "handlingTime"), ("transit_days", "transitTime")):
        rng = shipping.get(key)
        if isinstance(rng, (list, tuple)) and len(rng) == 2:
            delivery[prop] = {"@type": "QuantitativeValue", "minValue": int(rng[0]), "maxValue": int(rng[1]), "unitCode": "DAY"}
    if delivery:
        ship["deliveryTime"] = {"@type": "ShippingDeliveryTime", **delivery}
    product_ld["offers"]["shippingDetails"] = ship
    if p.get("category") == "personnalise" or p.get("customizable"):       # sur mesure : pas de rétractation (art. L221-28 3°)
        product_ld["offers"]["hasMerchantReturnPolicy"] = {"@type": "MerchantReturnPolicy", "applicableCountry": returns["country"], "returnPolicyCategory": "https://schema.org/MerchantReturnNotPermitted"}
    else:
        product_ld["offers"]["hasMerchantReturnPolicy"] = {
            "@type": "MerchantReturnPolicy", "applicableCountry": returns["country"],
            "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow", "merchantReturnDays": int(returns["days"]),
            "returnMethod": "https://schema.org/ReturnByMail", "refundType": "https://schema.org/FullRefund",
            "returnFees": "https://schema.org/FreeReturn" if returns.get("fees") == "free" else "https://schema.org/ReturnFeesCustomerResponsibility",
        }
    # Avis portant sur cette création et affichés sur la page -> extraits d'avis Google (jamais la note globale de la boutique)
    own = [r for r in _reviews["items"] if r["listing_id"] == str(p["listing_id"])]
    if own:
        product_ld["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": round(sum(r["rating"] for r in own) / len(own), 1), "reviewCount": len(own), "bestRating": 5, "worstRating": 1}
        product_ld["review"] = [{"@type": "Review", "author": {"@type": "Person", "name": r["author"] or "Client Etsy"}, **({"datePublished": r["date"]} if r["date"] else {}),
                                 "reviewBody": r["text"], "reviewRating": {"@type": "Rating", "ratingValue": r["rating"], "bestRating": 5, "worstRating": 1}}
                                for r in pick_reviews(3, {str(p["listing_id"])})]

    gallery_imgs = json.dumps([img_size(u, "794xN") for u in images], ensure_ascii=False)
    thumbs = "".join(
        f'<button type="button" class="gallery__thumb{" is-active" if i == 0 else ""}" data-index="{i}" aria-label="Photo {i + 1}"><img src="{esc(img_size(u, "300x300"))}" alt="{esc(alt)} – photo {i + 1}" width="66" height="66" loading="lazy"></button>'
        for i, u in enumerate(images)
    )
    main_img = (
        f'<img class="gallery__img" src="{esc(img_size(images[0], "794xN"))}" srcset="{esc(img_size(images[0], "794xN"))} 794w, {esc(img_size(images[0], "1588xN"))} 1588w" sizes="(max-width: 900px) 100vw, 560px" alt="{esc(alt)}, vue principale" width="794" height="794" fetchpriority="high" decoding="async">'
        if images else ""
    )
    nav_btns = (
        f'<button type="button" class="gallery__nav gallery__nav--prev" data-dir="-1" aria-label="Photo précédente">{ICON_PREV}</button>'
        f'<button type="button" class="gallery__nav gallery__nav--next" data-dir="1" aria-label="Photo suivante">{ICON_NEXT}</button>'
        if len(images) > 1 else ""
    )
    body = f"""<main id="main">
  <div class="container">{breadcrumb(crumbs)}</div>
  <section class="product-hero container">
    <div class="gallery" data-gallery data-images='{esc(gallery_imgs)}'>
      <div class="gallery__main">{main_img}{('<span class="badge ' + b[0][1] + '">' + esc(b[0][0]) + '</span>') if b else ''}{nav_btns}</div>
      {('<div class="gallery__thumbs">' + thumbs + '</div>') if len(images) > 1 else ''}
      {('<p class="gallery__caption">' + esc(kind["caption"].format(name=name)) + '</p>') if images else ''}
    </div>
    <div class="product-info">
      <span class="eyebrow">{esc(c["name"])}</span>
      <h1 class="product-info__title">{esc(name)}</h1>
      <p class="product-info__sub">{esc(kind["subtitle"])}</p>
      {review_summary(cat, " review-strip--product")}
      <p class="product-info__price">{esc(price_fmt(p["price"], p.get("currency", "EUR")))} <small>{"Livraison offerte" if p.get("free_shipping") else "Frais de livraison calculés sur Etsy"}</small></p>
      {('<div class="notice"><p><strong>Momentanément indisponible.</strong> Cette création n\'est pas en stock pour le moment. <a href="/contact">Contactez-nous</a> pour être prévenu de son retour ou pour une fabrication à la demande.</p></div>') if unavailable else ''}
      <div class="product-info__cta">
        <a class="btn btn--primary btn--lg" href="{esc(etsy_url(p))}" target="_blank" rel="noopener">{"Voir sur Etsy" if unavailable else "Commander sur Etsy"} {ICON_EXT}</a>
        <button type="button" class="btn btn--secondary btn--lg" data-quickview="{p["listing_id"]}">Aperçu rapide</button>
      </div>
      <p class="product-info__note">Paiement sécurisé, suivi de commande et protection des achats gérés par Etsy. Une question ? <a href="/contact">Contactez-nous</a>.</p>
      <div class="prose product-info__desc">
        {paragraphs(p.get("description", "")) if not p.get("description_long") else ''}
        {''.join(f'<p>{esc(x)}</p>' for x in p.get("description_long", []))}
        {('<ul>' + ''.join(f'<li>{esc(d)}</li>' for d in p.get('details', [])) + '</ul>') if p.get('details') else ''}
      </div>
      <ul class="icon-list product-info__why">{''.join(f'<li>{ICON_CHECK} <span>{esc(w)}</span></li>' for w in kind['why'] + [MADE_IN_FR])}</ul>
    </div>
  </section>

  <section class="section section--tight section--alt">
    <div class="container info-cols">
      <div class="info-col"><h2>Le bois</h2><p>{esc(kind["wood"])}</p></div>
      <div class="info-col"><h2>L'entretien</h2><p>{esc(kind["care"])}</p></div>
      <div class="info-col"><h2>Idée cadeau</h2><p>{esc(kind["gift"])}</p></div>
    </div>
  </section>

  {('<section class="section section--tight"><div class="container"><div class="section__head"><span class="eyebrow">Questions fréquentes</span><h2>À propos de cette création</h2></div>' + faq_html(kind["faq"]) + '</div></section>') if kind.get("faq") else ''}

  {reviews_html}
  <section class="section section--tight{'' if reviews_html else ' section--alt'}">
    <div class="container">
      <div class="section__head section__head--row">
        <div><span class="eyebrow">Dans la même veine</span><h2>Vous aimerez aussi</h2></div>
        {('<a class="btn btn--secondary" href="/collections/' + c["slug"] + '/">Toute la collection ' + esc(c["name"]) + '</a>') if c.get("slug") else ''}
      </div>
      <div class="product-grid">{''.join(product_card(x, cat, reveal=False) for x in related)}</div>
      <p class="muted mt-3">Autres collections : {' · '.join(f'<a href="/collections/{c2["slug"]}/">{esc(c2["name"])}</a>' for c2, _ in other_cols)}.</p>
    </div>
  </section>
</main>
"""
    extra = (jsonld(product_ld) + "\n" + jsonld(breadcrumb_ld(crumbs)) +
             f'\n<meta property="product:price:amount" content="{float(p["price"]):.2f}">\n<meta property="product:price:currency" content="{esc(p.get("currency", "EUR"))}">'
             + ('\n<meta name="robots" content="noindex, follow">' if unavailable else ''))
    page_img = img_size(images[0], "1588xN") if images else None
    return head(title, desc, p["page_url"], page_img, extra, og_type="product") + "<body>\n" + set_active(header, "/produits") + body + footer + '<script src="/assets/js/site.js" defer></script>\n</body>\n</html>\n'


def collection_page(col: dict, items: list, cat: Catalogue, header: str, footer: str) -> str:
    slug = col["slug"]
    name = col["name"]
    h1 = col.get("h1") or name
    title = col.get("seo_title") or f"{h1} | {BRAND}"
    intro = col.get("intro") or col.get("tagline") or ""
    paras = [x.strip() for x in re.split(r"\n\s*\n", intro) if x.strip()]
    desc = col.get("seo_description") or truncate(paras[0] if paras else f"{name} : créations en bois gravé Wooden Brothers.", 155)
    path = f"/collections/{slug}/"
    crumbs = [("Accueil", "/"), ("Nos créations", "/produits"), (name, None)]
    kind = KINDS.get(col.get("kind") or (items[0]["kind"] if items else "autre"), KINDS["autre"])
    others = [(c2, its) for c2, its in cat.collections() if c2["slug"] != slug]
    reviews_html = reviews_section(cat, 3, listing_ids={str(x["listing_id"]) for x in items}, title="Avis sur <em>cette collection</em>")
    ld = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": h1,
        "url": SITE + path,
        "description": desc,
        "isPartOf": {"@type": "WebSite", "name": BRAND, "url": SITE + "/"},
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": len(items),
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "url": SITE + p["page_url"], "name": p.get("short_title") or p["title"], "image": img_size(p["images"][0], "794xN") if p.get("images") else None}
                for i, p in enumerate(items)
            ],
        },
    }
    body = f"""<main id="main">
  <section class="page-head">
    <div class="rings" aria-hidden="true"></div>
    <div class="container">
      {breadcrumb(crumbs)}
      <span class="eyebrow">Collection</span>
      <h1>{esc(h1)}</h1>
      <p class="page-head__lead">{esc(paras[0]) if paras else ''}</p>
      {review_summary(cat)}
    </div>
  </section>

  <div class="toolbar">
    <div class="container toolbar__inner">
      <div class="chips" id="chips" role="group" aria-label="Filtrer par collection">{chips(cat, slug)}</div>
      <div class="toolbar__sort">
        <label for="sort">Trier</label>
        <select id="sort" class="select">
          <option value="recent">Plus récents</option>
          <option value="price-asc">Prix croissant</option>
          <option value="price-desc">Prix décroissant</option>
          <option value="name">Nom A → Z</option>
        </select>
      </div>
    </div>
  </div>

  <section class="section section--tight">
    <div class="container">
      <div class="catalogue-head">
        <h2 id="catalogue-title">{esc(name)}</h2>
        <span class="results-count" id="results-count" aria-live="polite">{len(items)} création{'s' if len(items) > 1 else ''}</span>
      </div>
      <div class="product-grid" id="catalogue-grid" data-prerendered="{esc(slug)}">{''.join(product_card(p, cat, eager=i < 6) for i, p in enumerate(items))}</div>
      <div class="empty-state" id="empty-state" hidden><h3>Aucune création dans cette collection pour le moment</h3><p>De nouvelles pièces arrivent régulièrement. <a href="/produits">Voir toutes nos créations</a>.</p></div>
    </div>
  </section>

  {reviews_html}
  <section class="section section--tight{'' if reviews_html else ' section--alt'}">
    <div class="container info-cols info-cols--wide">
      <div class="info-col prose">
        <h2>À propos de cette collection</h2>
        {''.join(f'<p>{esc(x)}</p>' for x in paras[1:]) or f'<p>{esc(kind["wood"])}</p>'}
      </div>
      <div class="info-col prose">
        <h2>Bon à savoir</h2>
        <p>{esc(kind["care"])}</p>
        <p>{esc(kind["gift"])}</p>
        <p>{esc(MADE_IN_FR_LONG)}</p>
      </div>
    </div>
  </section>

  <section class="section section--tight">
    <div class="container">
      <div class="section__head section__head--left"><span class="eyebrow">Explorer</span><h2>Nos autres collections</h2></div>
      <div class="collection-links">{''.join(f'<a class="collection-link" href="/collections/{c2["slug"]}/"><strong>{esc(c2["name"])}</strong><span>{len(its)} création{"s" if len(its) > 1 else ""}</span></a>' for c2, its in others)}</div>
    </div>
  </section>
</main>
"""
    extra = jsonld(ld) + "\n" + jsonld(breadcrumb_ld(crumbs))
    image = img_size(items[0]["images"][0], "1588xN") if items and items[0].get("images") else None
    return head(title, desc, path, image, extra) + f'<body data-collection="{esc(slug)}">\n' + set_active(header, "/produits") + body + footer + '<script src="/assets/js/site.js" defer></script>\n<script src="/assets/js/catalogue.js" defer></script>\n</body>\n</html>\n'


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #
def copy_sources() -> list:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    copied = []
    for item in sorted(ROOT.iterdir()):
        if item.name in SKIP or item.name.startswith("."):
            continue
        if item.is_dir():
            shutil.copytree(item, OUT / item.name, ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"))
        else:
            shutil.copy2(item, OUT / item.name)
        copied.append(item.name)
    return copied


def html_pages(directory: Path) -> list:
    """Chemins publics (sans extension) des pages HTML sources."""
    urls = []
    for f in sorted(directory.rglob("*.html")):
        rel = f.relative_to(directory).as_posix()
        top = rel.split("/")[0]
        if top in SKIP or top.startswith(".") or rel.startswith("google") or rel == "404.html":
            continue
        url = "/" + rel[:-5]
        if url.endswith("/index"):
            url = url[:-5]
        if url == "/index":
            url = "/"
        urls.append((url, git_date(f) or date.fromtimestamp(f.stat().st_mtime).isoformat()))
    return urls


def main() -> int:
    global _manifest, _reviews
    data = json.loads(DATA.read_text(encoding="utf-8"))
    cat = Catalogue(data)
    _reviews = load_reviews()
    copy_sources()
    (OUT / "data" / "reviews.json").unlink(missing_ok=True)      # fichier de travail, inutile en ligne

    # Photos ré-hébergées (si scripts/images.py a tourné) : copie + réécriture des URL dans data/products.json
    manifest_file = IMAGES_CACHE / "manifest.json"
    if manifest_file.exists():
        _manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        out_dir = IMAGES_CACHE / "out"
        if out_dir.exists():
            shutil.copytree(out_dir, OUT / "img" / "creations", dirs_exist_ok=True)
        for p in data.get("products", []):
            p["images"] = [img_size(u, "794xN") if _manifest.get(etsy_image_id(u) or "") else u for u in p.get("images", [])]
        for c in data.get("categories", []) + data.get("collections_virtuelles", []):
            if c.get("image") and _manifest.get(etsy_image_id(c["image"]) or ""):
                c["image"] = img_size(c["image"], "794xN")
        (OUT / "data" / "products.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  photos locales : {len(_manifest)} image(s) servies depuis /img/creations/")

    index_src = (ROOT / "index.html").read_text(encoding="utf-8")
    header = extract(index_src, "header")
    footer = extract(index_src, "footer")

    # ----- accueil : sélection de l'atelier + articles à la une
    buckets = [cat.in_category(c["slug"]) for c in cat.categories]
    buckets = [b for b in buckets if b]
    picked, rnd = [], 0
    while len(picked) < 8 and any(len(b) > rnd for b in buckets):
        for b in buckets:
            if len(b) > rnd and len(picked) < 8:
                picked.append(b[rnd])
        rnd += 1
    featured = [p for p in cat.products if p.get("featured")][:2] or cat.in_category("personnalise")[:2]
    index_out = inject(index_src, "selection", "".join(product_card(p, cat, eager=i < 4) for i, p in enumerate(picked)))
    index_out = inject(index_out, "featured", "".join(product_card(p, cat, show_category=False, reveal=False, sizes="(max-width: 480px) 90vw, 260px") for p in featured))
    summary = review_summary(cat)
    if summary:                                                   # note Etsy dans le héros (sinon le paragraphe reste masqué)
        index_out = index_out.replace('<p class="hero__reviews" data-shop-reviews hidden></p>', f'<p class="hero__reviews" data-shop-reviews>{summary}</p>', 1)
    (OUT / "index.html").write_text(index_out, encoding="utf-8")

    # ----- catalogue complet
    prod_src = (ROOT / "produits.html").read_text(encoding="utf-8")
    prod_out = inject(prod_src, "chips", chips(cat, "all"))
    prod_out = inject(prod_out, "catalogue", "".join(product_card(p, cat, eager=i < 6) for i, p in enumerate(cat.products)))
    (OUT / "produits.html").write_text(prod_out, encoding="utf-8")

    # ----- pages générées
    generated = []
    for p in cat.all_products:
        d = OUT / "creations" / p["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(product_page(p, cat, header, footer), encoding="utf-8")
        if p.get("status") != "unavailable":
            generated.append((p["page_url"], None))
    for col, items in cat.collections():
        d = OUT / "collections" / col["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(collection_page(col, items, cat, header, footer), encoding="utf-8")
        generated.append((f"/collections/{col['slug']}/", None))

    # ----- cartes produit et avis insérés dans les pages sources :
    #       <!-- wb:products ids="a,b,c" [show-category="false"] --> et <!-- wb:reviews [max="6"] [alt="false"] -->
    pattern = re.compile(r'<!-- wb:products ids="([0-9, ]+)"(?: show-category="(\w+)")? -->.*?<!-- /wb:products -->', re.S)
    reviews_pattern = re.compile(r'<!-- wb:reviews((?: max="\d+")?(?: alt="\w+")?) -->.*?<!-- /wb:reviews -->', re.S)
    by_id = cat.by_id
    for f in OUT.rglob("*.html"):
        txt = f.read_text(encoding="utf-8")
        if "wb:products" not in txt and "wb:reviews" not in txt:
            continue
        def render(m):
            ids = [i.strip() for i in m.group(1).split(",") if i.strip()]
            cards = "".join(product_card(by_id[i], cat, show_category=(m.group(2) != "false"), reveal=False) for i in ids if i in by_id)
            return f'<!-- wb:products ids="{m.group(1)}" -->{cards}<!-- /wb:products -->'
        def render_reviews(m):
            attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
            section = reviews_section(cat, int(attrs.get("max", 6)), alt=attrs.get("alt") != "false", lead=REVIEWS_LEAD)
            return f'<!-- wb:reviews{m.group(1)} -->{section}<!-- /wb:reviews -->'
        f.write_text(reviews_pattern.sub(render_reviews, pattern.sub(render, txt)), encoding="utf-8")

    # ----- photos Etsy encore référencées dans les pages sources (héros, tuiles…) -> versions locales si disponibles
    etsy_img_re = re.compile(r"https://i\.etsystatic\.com/\d+/r/il/[0-9a-f]+/(\d+)/il_([0-9a-zA-Z]+x[0-9a-zA-Z]+)\.\1_[0-9a-z]+\.jpg")
    def localize(m):
        entry = _manifest.get(m.group(1))
        return f"{entry['base']}-{SIZE_TO_WIDTH.get(m.group(2), 800)}.webp" if entry else m.group(0)

    # ----- Content-Security-Policy (balise meta : GitHub Pages ne permet pas d'en-têtes HTTP)
    def csp_meta(html_text: str) -> str:
        hashes = set()
        for m in re.finditer(r"<script>(.*?)</script>", html_text, re.S):
            digest = hashlib.sha256(m.group(1).encode("utf-8")).digest()
            hashes.add("'sha256-" + __import__("base64").b64encode(digest).decode() + "'")
        policy = ("default-src 'self'; script-src 'self' " + " ".join(sorted(hashes)) + "; style-src 'self'; "
                  "img-src 'self' data: https://i.etsystatic.com; font-src 'self'; connect-src 'self'; "
                  "object-src 'none'; base-uri 'self'; form-action 'self'; upgrade-insecure-requests")
        return html_text.replace('<meta charset="UTF-8">', f'<meta charset="UTF-8">\n<meta http-equiv="Content-Security-Policy" content="{policy}">', 1)

    # ----- empreinte de cache, CSP et photos locales sur toutes les pages produites
    for f in OUT.rglob("*.html"):
        txt = f.read_text(encoding="utf-8")
        if _manifest:
            txt = etsy_img_re.sub(localize, txt)
        f.write_text(csp_meta(fingerprint(txt)), encoding="utf-8")

    # ----- sitemap.xml (lastmod = date du dernier commit touchant la page ou le catalogue)
    catalogue_date = git_date(DATA, ROOT / "scripts" / "build.py") or (data.get("updated_at") or date.today().isoformat())[:10]
    today = date.today().isoformat()
    urls = []
    images_by_url = {p["page_url"]: [img_size(u, "1588xN") for u in p.get("images", [])[:3]] for p in cat.products}
    source_pages = html_pages(ROOT)
    index_date = max(d for _, d in source_pages if d) if source_pages else today
    for url, lastmod in source_pages + generated:
        if url in ("/", "/produits"):
            lastmod = max(lastmod or "", catalogue_date)       # ces pages embarquent le catalogue
        imgs = "".join(f"<image:image><image:loc>{esc(u if u.startswith('http') else SITE + u)}</image:loc></image:image>" for u in images_by_url.get(url, []))
        urls.append(f"  <url><loc>{SITE}{url}</loc><lastmod>{lastmod or catalogue_date}</lastmod>{imgs}</url>")
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n' + "\n".join(urls) + "\n</urlset>\n", encoding="utf-8")

    # ----- llms.txt (résumé lisible par les assistants IA)
    lines = [f"# {BRAND}", "",
             f"> Atelier français de gravure sur bois : dessous de plat en rondin de Paulownia (animaux, manga, Disney), cartes Pokémon en bois 3D (Pikachu, Évoli, Mewtwo… ou carte Pokémon sur mesure), horloges murales et créations personnalisées. Motifs dessinés par l'atelier, fabriqués en petites séries et expédiés depuis la France. Les ventes se font sur la boutique Etsy officielle ({ETSY_SHOP}).", "",
             f"Site : {SITE}/ · Contact : {cat.shop.get('email', '')} · Instagram : {cat.shop.get('instagram', '')}", "",
             *([f"Avis clients : {str(round(float(cat.shop['review_average']), 1)).replace('.', ',')}/5 sur Etsy ({cat.shop['review_count']} avis) – {_reviews['url']}", ""]
               if isinstance(cat.shop.get("review_average"), (int, float)) and isinstance(cat.shop.get("review_count"), int) and cat.shop["review_count"] > 0 else []),
             "## Collections", ""]
    for col, items in cat.collections():
        lines.append(f"- [{col['name']}]({SITE}/collections/{col['slug']}/) : {len(items)} création(s). {truncate(col.get('tagline') or '', 120)}")
    lines += ["", "## Créations (prix TTC indicatifs, achat sur Etsy)", ""]
    for p in cat.products:
        lines.append(f"- [{p.get('short_title') or p['title']}]({SITE}{p['page_url']}) : {price_fmt(p['price'])}. {truncate(p.get('description', ''), 160)}")
    lines += ["", "## Pages utiles", "", f"- [L'atelier]({SITE}/a-propos)", f"- [Contact]({SITE}/contact)", f"- [Questions fréquentes]({SITE}/#faq)"]
    for url, _ in html_pages(ROOT):
        if url.startswith("/journal/"):
            lines.append(f"- [{url.split('/')[-1].replace('-', ' ').capitalize()}]({SITE}{url})")
    (OUT / "llms.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ----- vérification des liens internes
    missing = set()
    for f in OUT.rglob("*.html"):
        for href in re.findall(r'(?:href|src)="(/[^"#?]*)"', f.read_text(encoding="utf-8")):
            target = OUT / href.lstrip("/")
            if href.endswith("/"):
                target = target / "index.html"
            if not target.exists() and not (target.with_suffix(".html")).exists():
                missing.add(href)
    if missing:
        print("ATTENTION liens internes introuvables :", ", ".join(sorted(missing)))

    print(f"✓ {len(cat.all_products)} pages création, {len(cat.collections())} pages collection, {len(_reviews['items'])} avis client(s), {len(urls)} URL dans le sitemap → {OUT}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
