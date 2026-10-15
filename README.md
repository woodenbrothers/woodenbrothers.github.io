# Wooden Brothers – site vitrine

Site vitrine de la boutique Etsy **[WoodenBrothersArt](https://www.etsy.com/fr/shop/WoodenBrothersArt)**, en ligne sur
[www.woodenbrothers.fr](https://www.woodenbrothers.fr). Site statique (HTML, CSS, JavaScript) construit par un petit
script Python et hébergé sur GitHub Pages, sans cookie ni outil de mesure d'audience.

## Comment le site est publié

À chaque push sur `main`, le workflow « Deploy static content to Pages » :

1. récupère les photos des créations et les convertit en WebP (`scripts/images.py`, résultat mis en cache) ;
2. construit le site dans `_site/` (`scripts/build.py`) : copie des pages sources, grilles de produits pré-rendues,
   **une page par création** (`/creations/<slug>/`) et **une page par collection** (`/collections/<slug>/`),
   `sitemap.xml`, `llms.txt`, données structurées schema.org ;
3. publie `_site/` sur GitHub Pages et prévient les moteurs compatibles IndexNow (Bing…).

Aperçu en local :

```bash
python3 scripts/build.py && npx serve _site     # puis http://localhost:3000
```

(Sans Pillow ni accès réseau, les photos sont servies depuis le CDN Etsy, c'est normal.)

## Organisation des fichiers

| Fichier / dossier | Rôle |
| --- | --- |
| `index.html` | Accueil. Contient aussi l'en-tête et le pied de page **de référence** (marqueurs `wb:header` / `wb:footer`) repris par les pages générées |
| `produits.html` | Catalogue complet (grille injectée au build entre les marqueurs `wb:catalogue`) |
| `journal.html`, `journal/*.html` | Le journal de l'atelier : guides et idées cadeaux |
| `a-propos.html`, `contact.html`, `mentions-legales.html`, `politique-confidentialite.html`, `404.html` | Pages fixes |
| `data/products.json` | **Le catalogue** : boutique, catégories (textes SEO), collections virtuelles, créations |
| `assets/css/style.css` | Charte graphique (couleurs, typographies, composants) |
| `assets/css/fonts.css` + `assets/fonts/` | Polices Fraunces et DM Sans auto-hébergées |
| `assets/js/site.js`, `assets/js/catalogue.js` | Menu, aperçu rapide, galerie, filtres et tri (amélioration progressive : tout fonctionne sans JS) |
| `scripts/build.py` | Construction du site dans `_site/` (textes par type de pièce dans `KINDS`) |
| `scripts/images.py` | Ré-hébergement des photos (WebP 400/800/1200 px, noms descriptifs) |
| `scripts/sync_etsy.py` | Synchronisation du catalogue avec l'API Etsy |
| `scripts/indexnow.py` + `<clé>.txt` | Notification IndexNow après déploiement |
| `.github/workflows/static.yml` | Build + déploiement GitHub Pages |
| `.github/workflows/sync-etsy.yml` | Synchronisation Etsy quotidienne (si la clé API est configurée) |
| `robots.txt`, `CNAME`, `google*.html`, `og-image.jpg`, `Images/` | Fichiers techniques, logo et icônes |

## Mettre à jour les articles

### Option A – automatiquement depuis Etsy (recommandé)

Le workflow « Synchronisation Etsy » interroge chaque jour l'API publique d'Etsy et met à jour `data/products.json`
(articles actifs, titres, prix, photos, sections, note de la boutique), puis redéploie le site. Il ne fait rien tant que
la clé API n'est pas configurée.

1. Connectez-vous sur Etsy, ouvrez <https://www.etsy.com/developers/your-apps> et créez une application
   (nom libre, ex. « Site vitrine woodenbrothers.fr »). Etsy fournit une clé **Keystring**.
2. Sur GitHub : **Settings → Secrets and variables → Actions → New repository secret**, nom `ETSY_API_KEY`,
   valeur = la Keystring.
3. Onglet **Actions → Synchronisation Etsy → Run workflow** pour lancer une première synchronisation.

À chaque synchronisation, les champs venant d'Etsy (`title`, `price`, `url`, `images`, `quantity`, `etsy_section_id`,
`created_timestamp`, `featured`) sont mis à jour ; les champs rédactionnels (`short_title`, `slug`, `seo_title`,
`seo_description`, `description`, `description_long`, `details`, `kind`, `free_shipping`, `share_url`, `hidden`)
sont conservés. Un nouvel article reçoit un slug, un texte dérivé de sa fiche Etsy et une page : relisez-le et
rédigez sa `description_long`. Un article qui disparaît d'Etsy (vendu, désactivé) passe en `"status": "unavailable"` :
sa page reste en ligne avec un bandeau et il sort des grilles ; mettez `"hidden": true` pour le retirer tout à fait.

Test en local : `ETSY_API_KEY=... python3 scripts/sync_etsy.py --dry-run`

### Option B – à la main

Modifiez la liste `products` de `data/products.json`. Champs d'un article :

| Champ | Rôle |
| --- | --- |
| `listing_id`, `title`, `price`, `currency`, `url`, `images`, `quantity` | Données Etsy (`images` = URL des photos Etsy, taille adaptée automatiquement) |
| `short_title` | Nom affiché sur le site |
| `slug` | Adresse de la page : `/creations/<slug>/` (ne plus changer une fois en ligne) |
| `category` | Slug d'une entrée de `categories` (`animaux`, `manga-anime`, `cartes-pokemon`, `disney`, `horloges`, `personnalise`) |
| `kind` | `dessous-de-plat`, `carte`, `horloge` ou `autre` : choisit les textes « bois / entretien / cadeau / FAQ » de la page |
| `description` | Texte court (aperçu rapide, catalogue) |
| `description_long` | Liste de paragraphes propres à la création, affichés sur sa page (150 mots minimum conseillés) |
| `details` | Liste à puces (dimensions, finition…) |
| `seo_title`, `seo_description` | Balises title / description de la page (facultatif, sinon générées) |
| `featured`, `free_shipping`, `hidden`, `status` | Mise en avant sur l'accueil, badge « Livraison offerte », masquage, `"unavailable"` |
| `share_url` | Lien **Share & Save** Etsy de l'article (voir ci-dessous) : utilisé à la place de `url` s'il est présent |

Les catégories portent `name`, `h1`, `tagline`, `intro` (deux paragraphes séparés par une ligne vide), `seo_title`,
`seo_description` et `image`. `collections_virtuelles` regroupe des créations par `kind` (ex. tous les dessous de plat).

### Liens Etsy « Share & Save »

Le programme Share & Save d'Etsy rembourse une partie des frais sur les commandes venant de vos propres liens.
Dans votre tableau de bord Etsy, générez le lien de partage de chaque article et collez-le dans son champ
`share_url` ; le lien de la boutique peut aller dans `shop.share_url`. Le site utilisera ces liens partout.

## Écrire un guide dans le journal

Copiez un fichier de `journal/`, changez le titre, la description, les textes et l'image, puis ajoutez-le à la liste
de `journal.html`. Pour insérer des cartes produit dans un guide (ou n'importe quelle page), placez :

```html
<div class="product-grid"><!-- wb:products ids="1838716908,1836879420" --><!-- /wb:products --></div>
```

Le build remplit automatiquement les cartes. L'en-tête et le pied de page des pages générées sont copiés depuis
`index.html` : modifiez-les là.

## Modifier le site

- **Textes** : directement dans les fichiers HTML ; textes des pages création par type de pièce dans `KINDS`
  (`scripts/build.py`).
- **Couleurs et polices** : variables en haut de `assets/css/style.css` (`--forest`, `--wood`, `--bg`…).
- **Photos du héros de l'accueil** et tuiles « collections » : URL dans `index.html`.
- **FAQ** : section `#faq` de `index.html`.

## Déploiement et sauvegarde

- Tout push sur `main` déploie le site en quelques minutes.
- L'ancienne version du site (avant la refonte d'octobre 2026) est conservée sur la branche
  **`sauvegarde-ancien-site`**. Pour y revenir : `git checkout main && git reset --hard sauvegarde-ancien-site &&
  git push --force origin main` (ou, sur GitHub, une pull request de `sauvegarde-ancien-site` vers `main`).
