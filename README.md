# Wooden Brothers – site vitrine

Site vitrine de la boutique Etsy **[WoodenBrothersArt](https://www.etsy.com/fr/shop/WoodenBrothersArt)**, en ligne sur
[woodenbrothers.fr](https://www.woodenbrothers.fr). Site 100 % statique (HTML, CSS, JavaScript), hébergé sur GitHub Pages,
sans cookie ni outil de mesure d'audience.

## Organisation des fichiers

| Fichier / dossier | Rôle |
| --- | --- |
| `index.html` | Accueil (héros, collections, sélection, savoir-faire, Paulownia, sur mesure, Instagram, FAQ) |
| `produits.html` | Catalogue complet avec filtres par collection, tri et aperçu rapide |
| `a-propos.html`, `contact.html` | Pages « L'atelier » et « Contact » |
| `mentions-legales.html`, `politique-confidentialite.html` | Pages légales |
| `404.html` | Page « introuvable » |
| `data/products.json` | **Le catalogue** : boutique, catégories et articles (voir ci-dessous) |
| `assets/css/style.css` | Charte graphique (couleurs, typographies, composants) |
| `assets/css/fonts.css` + `assets/fonts/` | Polices Fraunces et DM Sans auto-hébergées |
| `assets/js/site.js` | En-tête, menu mobile, chargement du catalogue, cartes produit, aperçu rapide |
| `assets/js/catalogue.js` | Filtres et tri de la page catalogue |
| `scripts/sync_etsy.py` | Synchronisation du catalogue avec l'API Etsy |
| `.github/workflows/static.yml` | Déploiement GitHub Pages à chaque push sur `main` |
| `.github/workflows/sync-etsy.yml` | Synchronisation Etsy quotidienne (si la clé API est configurée) |
| `Images/` | Logo et icônes |

Les photos des articles sont chargées directement depuis Etsy (`i.etsystatic.com`) : rien à héberger.

## Mettre à jour les articles

### Option A – automatiquement depuis Etsy (recommandé)

Le workflow « Synchronisation Etsy » interroge chaque jour l'API publique d'Etsy et met à jour `data/products.json`
(articles actifs, titres, prix, photos, sections, note de la boutique), puis redéploie le site. Il ne fait rien tant que
la clé API n'est pas configurée.

1. Connectez-vous sur Etsy, puis ouvrez <https://www.etsy.com/developers/your-apps> et créez une application
   (nom libre, ex. « Site vitrine woodenbrothers.fr »). Etsy fournit une clé **Keystring**.
   L'accès « provisoire » accordé immédiatement suffit pour lire le catalogue public d'une boutique.
2. Sur GitHub : **Settings → Secrets and variables → Actions → New repository secret**, nom `ETSY_API_KEY`,
   valeur = la Keystring.
3. Onglet **Actions → Synchronisation Etsy → Run workflow** pour lancer une première synchronisation sans attendre.

À chaque synchronisation, les champs venant d'Etsy (`title`, `price`, `url`, `images`, `quantity`, `etsy_section_id`,
`created_timestamp`, `featured` d'après les « articles à la une ») sont écrasés ; les champs rédactionnels du site
(`short_title`, `description`, `details`, `kind`, `free_shipping`, `hidden`) sont conservés, et les nouveaux
articles sont ajoutés automatiquement avec un texte dérivé de leur fiche Etsy (à relire au besoin). Les articles qui ne
sont plus actifs sur Etsy sont retirés du site. La catégorie d'un article suit sa section Etsy, sauf si vous ajoutez
`"category_locked": true` à l'article.

Test en local : `ETSY_API_KEY=... python3 scripts/sync_etsy.py --dry-run`

### Option B – à la main

Ouvrez `data/products.json` et modifiez la liste `products`. Un article ressemble à ceci :

```json
{
  "listing_id": 1838716908,
  "title": "Titre complet de la fiche Etsy",
  "short_title": "Dessous de plat Chat",
  "category": "animaux",
  "kind": "dessous-de-plat",
  "price": 12.99,
  "currency": "EUR",
  "url": "https://www.etsy.com/fr/listing/1838716908/dessous-de-plat-chat-en-bois-massif",
  "images": ["https://i.etsystatic.com/56732046/r/il/5e0bc6/6588924415/il_794xN.6588924415_lsd8.jpg"],
  "description": "Texte court affiché dans l'aperçu rapide.",
  "details": ["Dimensions : environ 20 cm de diamètre, épaisseur 2 cm"],
  "featured": false,
  "free_shipping": false,
  "quantity": null
}
```

- `category` doit correspondre au `slug` d'une entrée de `categories` (`animaux`, `manga-anime`, `cartes-pokemon`,
  `disney`, `horloges`, `personnalise`). Ajoutez une entrée dans `categories` pour créer une nouvelle collection.
- `images` : URL des photos Etsy (clic droit → copier l'adresse de l'image sur la fiche). La taille dans l'URL
  (`il_794xN`, `il_600x600`…) est adaptée automatiquement par le site.
- `featured: true` met l'article en avant dans le bandeau « Sur mesure » de l'accueil ;
  `quantity: 1` affiche « Dernier exemplaire » ; `hidden: true` masque l'article sans le supprimer.
- L'ordre de la liste = ordre « Plus récents » du catalogue.

## Modifier le site

- **Textes** : directement dans les fichiers HTML (chaque page contient son propre en-tête et pied de page).
- **Couleurs et polices** : variables en haut de `assets/css/style.css` (`--forest`, `--wood`, `--bg`…).
- **Photos du héros de l'accueil** et des tuiles « collections » : URL dans `index.html` (section `hero` et
  `collections`).
- **Questions fréquentes** : section `#faq` de `index.html`.

Aperçu en local : `npx serve .` puis <http://localhost:3000> (les URL sans extension comme `/produits`
fonctionnent comme sur GitHub Pages).

## Déploiement et sauvegarde

- Tout push sur `main` déploie le site en quelques minutes (workflow « Deploy static content to Pages »).
- La version précédente du site est conservée sur la branche **`sauvegarde-ancien-site`**. Pour y revenir :
  `git checkout main && git reset --hard sauvegarde-ancien-site && git push --force origin main`
  (ou, sur GitHub, ouvrir une pull request de `sauvegarde-ancien-site` vers `main`).
