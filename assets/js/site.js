/* =====================================================================
   Wooden Brothers — scripts communs
   - en-tête (menu mobile, ombre au défilement)
   - apparition des blocs au défilement
   - catalogue : chargement de /data/products.json, cartes produit,
     aperçu rapide (modale) partagé par toutes les pages
   - accueil : collections, sélection, articles à la une
   ===================================================================== */
(function () {
  'use strict';

  var WB = (window.WB = window.WB || {});
  var DATA_URL = '/data/products.json';
  var ETSY_SHOP_URL = 'https://www.etsy.com/fr/shop/WoodenBrothersArt';

  /* ---------- utilitaires ---------- */
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  WB.$ = $; WB.$$ = $$; WB.esc = esc;

  /* Change la taille d'une image Etsy : il_794xN. -> il_600x600. etc. */
  WB.imgSize = function (url, size) {
    return String(url || '').replace(/il_[0-9a-zA-Z]+x[0-9a-zA-Z]+\./, 'il_' + size + '.');
  };
  WB.price = function (n, cur) {
    if (n == null || isNaN(n)) return '';
    try { return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: cur || 'EUR' }).format(n); }
    catch (e) { return String(n).replace('.', ',') + ' €'; }
  };
  WB.plural = function (n, one, many) { return n + ' ' + (n > 1 ? many : one); };

  var ICON_EXT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17 17 7M8 7h9v9"/></svg>';
  var ICON_CLOSE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>';
  var ICON_PREV = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 5-7 7 7 7"/></svg>';
  var ICON_NEXT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 5 7 7-7 7"/></svg>';
  WB.ICON_EXT = ICON_EXT;

  /* ---------- en-tête ---------- */
  function initHeader() {
    var header = $('.site-header');
    var toggle = $('.nav-toggle');
    var nav = $('#nav');
    if (header) {
      var onScroll = function () { header.classList.toggle('is-scrolled', window.scrollY > 8); };
      onScroll();
      window.addEventListener('scroll', onScroll, { passive: true });
    }
    if (!toggle || !nav) return;
    var backdrop = document.createElement('div');
    backdrop.className = 'nav-backdrop';
    document.body.appendChild(backdrop);
    function setOpen(open) {
      nav.classList.toggle('is-open', open);
      document.body.classList.toggle('nav-open', open);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      toggle.setAttribute('aria-label', open ? 'Fermer le menu' : 'Ouvrir le menu');
    }
    toggle.addEventListener('click', function () { setOpen(!nav.classList.contains('is-open')); });
    backdrop.addEventListener('click', function () { setOpen(false); });
    nav.addEventListener('click', function (e) { if (e.target.closest('a')) setOpen(false); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && nav.classList.contains('is-open')) setOpen(false); });
    window.matchMedia('(min-width: 961px)').addEventListener('change', function (e) { if (e.matches) setOpen(false); });
  }

  /* ---------- apparition au défilement ---------- */
  var observer = null;
  WB.observe = function (root) {
    var nodes = $$('[data-reveal]:not(.is-visible)', root || document);
    if (!('IntersectionObserver' in window)) { nodes.forEach(function (n) { n.classList.add('is-visible'); }); return; }
    if (!observer) {
      observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); }
        });
      }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
    }
    nodes.forEach(function (n) { observer.observe(n); });
  };

  /* ---------- toast ---------- */
  var toastTimer = null;
  WB.toast = function (msg) {
    var el = $('.toast');
    if (!el) { el = document.createElement('div'); el.className = 'toast'; el.setAttribute('role', 'status'); document.body.appendChild(el); }
    el.textContent = msg;
    el.classList.add('is-visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.classList.remove('is-visible'); }, 2400);
  };

  /* ---------- catalogue ---------- */
  var cataloguePromise = null;
  WB.catalogue = function () {
    if (!cataloguePromise) {
      cataloguePromise = fetch(DATA_URL).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }).then(function (data) {
        data.products = (data.products || []).filter(function (p) { return !p.hidden && p.price != null; });
        data.categories = data.categories || [];
        data.shop = data.shop || {};
        data.byId = {};
        data.products.forEach(function (p) { data.byId[String(p.listing_id)] = p; });
        data.catBySlug = {};
        data.categories.forEach(function (c) { data.catBySlug[c.slug] = c; });
        data.countBySlug = {};
        data.products.forEach(function (p) { data.countBySlug[p.category] = (data.countBySlug[p.category] || 0) + 1; });
        return data;
      });
    }
    return cataloguePromise;
  };

  WB.badges = function (p) {
    var b = [];
    if (p.quantity === 1) b.push(['Dernier exemplaire', 'badge--alert']);
    if (p.free_shipping) b.push(['Livraison offerte', 'badge--wood']);
    if (p.category === 'personnalise' || p.customizable) b.push(['Sur mesure', '']);
    return b;
  };

  function srcset(u) {
    return WB.imgSize(u, '300x300') + ' 300w, ' + WB.imgSize(u, '600x600') + ' 600w, ' + WB.imgSize(u, '800x800') + ' 800w';
  }

  WB.productCard = function (p, data, opts) {
    opts = opts || {};
    var cat = data.catBySlug[p.category];
    var img0 = p.images && p.images[0];
    var img1 = p.images && p.images[1];
    var sizes = opts.sizes || '(max-width: 640px) 50vw, (max-width: 1100px) 33vw, 300px';
    var badges = WB.badges(p).map(function (b) { return '<span class="badge ' + b[1] + '">' + esc(b[0]) + '</span>'; }).join('');
    var title = esc(p.short_title || p.title);
    return '' +
      '<article class="product-card" data-id="' + p.listing_id + '" data-category="' + esc(p.category) + '"' + (opts.reveal ? ' data-reveal' : '') + '>' +
        '<button type="button" class="product-card__media" data-quickview="' + p.listing_id + '" aria-label="Aperçu rapide : ' + title + '">' +
          (img0 ? '<img class="product-card__img" src="' + esc(WB.imgSize(img0, '600x600')) + '" srcset="' + esc(srcset(img0)) + '" sizes="' + esc(sizes) + '" alt="' + title + '" width="600" height="600" loading="' + (opts.eager ? 'eager' : 'lazy') + '" decoding="async">' : '') +
          (img1 ? '<img class="product-card__img product-card__img--alt" src="' + esc(WB.imgSize(img1, '600x600')) + '" alt="" width="600" height="600" loading="lazy" decoding="async" aria-hidden="true">' : '') +
          (badges ? '<span class="product-card__badges">' + badges + '</span>' : '') +
          '<span class="product-card__quick btn btn--light btn--sm" aria-hidden="true">Aperçu rapide</span>' +
        '</button>' +
        '<div class="product-card__body">' +
          (cat && opts.showCategory !== false ? '<span class="product-card__cat">' + esc(cat.name) + '</span>' : '') +
          '<h3 class="product-card__title">' + title + '</h3>' +
          '<p class="product-card__price">' + esc(WB.price(p.price, p.currency)) + '</p>' +
        '</div>' +
        '<div class="product-card__actions">' +
          '<button type="button" class="btn btn--secondary btn--sm" data-quickview="' + p.listing_id + '">Détails</button>' +
          '<a class="btn btn--primary btn--sm" href="' + esc(p.url) + '" target="_blank" rel="noopener">Commander sur Etsy</a>' +
        '</div>' +
      '</article>';
  };

  /* ---------- aperçu rapide ---------- */
  var dialog = null, current = null, currentIndex = 0;

  function ensureDialog() {
    if (dialog) return dialog;
    dialog = document.createElement('dialog');
    dialog.className = 'modal';
    dialog.setAttribute('aria-label', 'Aperçu du produit');
    document.body.appendChild(dialog);
    dialog.addEventListener('click', function (e) {
      if (e.target === dialog) closeQuickview();           // clic sur le fond
      var t = e.target.closest('[data-modal-close]'); if (t) closeQuickview();
      var th = e.target.closest('[data-thumb]'); if (th) showImage(parseInt(th.getAttribute('data-thumb'), 10));
      var nav = e.target.closest('[data-dir]'); if (nav) showImage(currentIndex + parseInt(nav.getAttribute('data-dir'), 10));
    });
    dialog.addEventListener('close', function () {
      document.body.style.overflow = '';
      if (/^#p=/.test(location.hash)) history.replaceState(null, '', location.pathname + location.search);
    });
    dialog.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') showImage(currentIndex - 1);
      if (e.key === 'ArrowRight') showImage(currentIndex + 1);
    });
    return dialog;
  }

  function showImage(i) {
    if (!current || !current.images || !current.images.length) return;
    var n = current.images.length;
    currentIndex = ((i % n) + n) % n;
    var main = $('.modal__main img', dialog);
    var u = current.images[currentIndex];
    if (main) {
      main.src = WB.imgSize(u, '794xN');
      main.srcset = WB.imgSize(u, '794xN') + ' 794w, ' + WB.imgSize(u, '1588xN') + ' 1588w';
    }
    $$('[data-thumb]', dialog).forEach(function (t, k) { t.classList.toggle('is-active', k === currentIndex); });
  }

  WB.openProduct = function (p, data) {
    var d = ensureDialog();
    current = p; currentIndex = 0;
    var cat = data.catBySlug[p.category];
    var images = p.images || [];
    var badges = WB.badges(p);
    var thumbs = images.length > 1 ? '<div class="modal__thumbs">' + images.map(function (u, k) {
      return '<button type="button" class="modal__thumb' + (k === 0 ? ' is-active' : '') + '" data-thumb="' + k + '" aria-label="Photo ' + (k + 1) + '"><img src="' + esc(WB.imgSize(u, '300x300')) + '" alt="" loading="lazy"></button>';
    }).join('') + '</div>' : '';
    d.innerHTML =
      '<div class="modal__panel">' +
        '<button type="button" class="modal__close" data-modal-close aria-label="Fermer">' + ICON_CLOSE + '</button>' +
        '<div class="modal__gallery">' +
          '<div class="modal__main">' +
            (images[0] ? '<img src="' + esc(WB.imgSize(images[0], '794xN')) + '" srcset="' + esc(WB.imgSize(images[0], '794xN')) + ' 794w, ' + esc(WB.imgSize(images[0], '1588xN')) + ' 1588w" sizes="(max-width: 860px) 100vw, 560px" alt="' + esc(p.short_title || p.title) + '">' : '') +
            (badges.length ? '<span class="badge ' + badges[0][1] + '">' + esc(badges[0][0]) + '</span>' : '') +
            (images.length > 1 ? '<button type="button" class="modal__nav modal__nav--prev" data-dir="-1" aria-label="Photo précédente">' + ICON_PREV + '</button><button type="button" class="modal__nav modal__nav--next" data-dir="1" aria-label="Photo suivante">' + ICON_NEXT + '</button>' : '') +
          '</div>' + thumbs +
        '</div>' +
        '<div class="modal__info">' +
          (cat ? '<span class="modal__cat">' + esc(cat.name) + '</span>' : '') +
          '<h2 class="modal__title">' + esc(p.short_title || p.title) + '</h2>' +
          '<p class="modal__price">' + esc(WB.price(p.price, p.currency)) + (p.free_shipping ? '<small>Livraison offerte</small>' : '') + '</p>' +
          (p.description ? '<p class="modal__desc">' + esc(p.description) + '</p>' : '') +
          (p.details && p.details.length ? '<ul class="modal__details">' + p.details.map(function (x) { return '<li>' + esc(x) + '</li>'; }).join('') + '</ul>' : '') +
          '<div class="modal__actions">' +
            '<a class="btn btn--primary btn--lg" href="' + esc(p.url) + '" target="_blank" rel="noopener">Commander sur Etsy ' + ICON_EXT + '</a>' +
          '</div>' +
          '<p class="modal__note">Paiement sécurisé, suivi de commande et protection des achats gérés par Etsy. Une question ? <a href="/contact">Contactez-nous</a>.</p>' +
        '</div>' +
      '</div>';
    if (typeof d.showModal !== 'function') { window.open(p.url, '_blank', 'noopener'); return; }
    if (!d.open) d.showModal();
    document.body.style.overflow = 'hidden';
    history.replaceState(null, '', location.pathname + location.search + '#p=' + p.listing_id);
    var closeBtn = $('.modal__close', d); if (closeBtn) closeBtn.focus();
  };

  function closeQuickview() { if (dialog && dialog.open) dialog.close(); }
  WB.closeQuickview = closeQuickview;

  function initQuickview() {
    document.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-quickview]');
      if (!btn) return;
      e.preventDefault();
      var id = btn.getAttribute('data-quickview');
      WB.catalogue().then(function (data) {
        var p = data.byId[id];
        if (p) WB.openProduct(p, data);
      }).catch(function () { window.open(ETSY_SHOP_URL, '_blank', 'noopener'); });
    });
    // Lien profond : /produits#p=123456
    var m = /^#p=(\d+)$/.exec(location.hash);
    if (m) {
      WB.catalogue().then(function (data) {
        var p = data.byId[m[1]];
        if (p) WB.openProduct(p, data);
      }).catch(function () {});
    }
  }

  /* ---------- accueil ---------- */
  function renderHome(data) {
    // Compteurs des collections
    $$('[data-collection-count]').forEach(function (el) {
      var n = data.countBySlug[el.getAttribute('data-collection-count')] || 0;
      el.textContent = n ? WB.plural(n, 'création', 'créations') : 'Bientôt de retour';
    });

    // Sélection de l'atelier : une pièce par collection, à tour de rôle
    var sel = $('#selection-grid');
    if (sel) {
      var max = parseInt(sel.getAttribute('data-max') || '8', 10);
      var buckets = data.categories.map(function (c) {
        return data.products.filter(function (p) { return p.category === c.slug; });
      }).filter(function (b) { return b.length; });
      var picked = [], round = 0;
      while (picked.length < max && buckets.some(function (b) { return b.length > round; })) {
        buckets.forEach(function (b) { if (b[round] && picked.length < max) picked.push(b[round]); });
        round++;
      }
      sel.innerHTML = picked.map(function (p, i) { return WB.productCard(p, data, { reveal: true, eager: i < 4 }); }).join('');
      WB.observe(sel);
    }

    // Articles à la une (sur mesure)
    var feat = $('#featured-grid');
    if (feat) {
      var list = data.products.filter(function (p) { return p.featured; }).slice(0, 2);
      if (!list.length) list = data.products.filter(function (p) { return p.category === 'personnalise'; }).slice(0, 2);
      if (list.length) {
        feat.innerHTML = list.map(function (p) { return WB.productCard(p, data, { showCategory: false, sizes: '(max-width: 480px) 90vw, 260px' }); }).join('');
      } else {
        feat.remove();
      }
    }

    // Avis Etsy (si la synchronisation les a récupérés)
    var rv = $('[data-shop-reviews]');
    if (rv && data.shop.review_count && data.shop.review_average) {
      rv.innerHTML = '<strong>' + esc(String(Math.round(data.shop.review_average * 10) / 10).replace('.', ',')) + '/5</strong> · ' + WB.plural(data.shop.review_count, 'avis client', 'avis clients') + ' sur Etsy';
      rv.hidden = false;
    }
  }

  /* ---------- copier dans le presse-papiers ---------- */
  function initCopy() {
    document.addEventListener('click', function (e) {
      var b = e.target.closest('[data-copy]');
      if (!b) return;
      var value = b.getAttribute('data-copy');
      var done = function () { WB.toast('Adresse copiée !'); };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(value).then(done, function () { window.prompt('Copiez l\'adresse :', value); });
      else window.prompt('Copiez l\'adresse :', value);
    });
  }

  /* ---------- démarrage ---------- */
  document.addEventListener('DOMContentLoaded', function () {
    initHeader();
    initQuickview();
    initCopy();
    WB.observe();
    $$('[data-year]').forEach(function (el) { el.textContent = String(new Date().getFullYear()); });

    if (document.body.hasAttribute('data-page-home')) {
      WB.catalogue().then(renderHome).catch(function (err) {
        console.error('Catalogue indisponible :', err);
        var sel = $('#selection-grid');
        if (sel) sel.innerHTML = '<p class="empty-state">Le catalogue est momentanément indisponible. <a href="' + ETSY_SHOP_URL + '" target="_blank" rel="noopener">Voir la boutique sur Etsy</a>.</p>';
      });
    }
  });
})();
