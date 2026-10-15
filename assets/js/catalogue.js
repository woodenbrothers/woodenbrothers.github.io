/* =====================================================================
   Wooden Brothers — page « Nos créations » (catalogue)
   Filtres par collection (?filter=slug), tri, rendu des cartes.
   ===================================================================== */
(function () {
  'use strict';
  var WB = window.WB;
  var $ = WB.$, $$ = WB.$$, esc = WB.esc;

  var grid = $('#catalogue-grid');
  var chips = $('#chips');
  var sortSel = $('#sort');
  var count = $('#results-count');
  var empty = $('#empty-state');
  var heading = $('#catalogue-title');
  if (!grid) return;

  // Anciens filtres (liens déjà indexés) -> nouveaux
  var LEGACY = { 'dessous-plats': 'kind:dessous-de-plat', 'dessous-verre': 'all', 'all': 'all' };

  var params = new URLSearchParams(location.search);
  var filter = params.get('filter') || 'all';
  if (LEGACY[filter]) filter = LEGACY[filter];
  var sort = 'recent';

  WB.catalogue().then(function (data) {
    var cats = data.categories.filter(function (c) { return data.countBySlug[c.slug]; });
    if (filter !== 'all' && filter.indexOf('kind:') !== 0 && !data.catBySlug[filter]) filter = 'all';

    chips.innerHTML = '<button type="button" class="chip" data-filter="all">Tout <span class="chip__count">' + data.products.length + '</span></button>' +
      cats.map(function (c) {
        return '<button type="button" class="chip" data-filter="' + esc(c.slug) + '">' + esc(c.name) + ' <span class="chip__count">' + data.countBySlug[c.slug] + '</span></button>';
      }).join('');

    chips.addEventListener('click', function (e) {
      var b = e.target.closest('[data-filter]');
      if (!b) return;
      filter = b.getAttribute('data-filter');
      apply(true);
    });
    if (sortSel) sortSel.addEventListener('change', function () { sort = sortSel.value; apply(false); });
    window.addEventListener('popstate', function () {
      var p = new URLSearchParams(location.search).get('filter') || 'all';
      filter = LEGACY[p] || p;
      apply(false, true);
    });

    function apply(scroll, silent) {
      var list = data.products.filter(function (p) {
        if (filter === 'all') return true;
        if (filter.indexOf('kind:') === 0) return p.kind === filter.slice(5);
        return p.category === filter;
      });
      if (sort === 'price-asc') list.sort(function (a, b) { return a.price - b.price; });
      else if (sort === 'price-desc') list.sort(function (a, b) { return b.price - a.price; });
      else if (sort === 'name') list.sort(function (a, b) { return (a.short_title || a.title).localeCompare(b.short_title || b.title, 'fr'); });
      // « recent » : ordre du catalogue (déjà du plus récent au plus ancien)

      grid.innerHTML = list.map(function (p, i) { return WB.productCard(p, data, { reveal: true, eager: i < 6 }); }).join('');
      WB.observe(grid);
      if (empty) empty.hidden = list.length > 0;
      if (count) count.textContent = WB.plural(list.length, 'création', 'créations');

      $$('[data-filter]', chips).forEach(function (c) {
        var active = c.getAttribute('data-filter') === filter;
        c.classList.toggle('is-active', active);
        c.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
      var cat = data.catBySlug[filter];
      if (heading) heading.textContent = cat ? cat.name : (filter.indexOf('kind:') === 0 ? 'Dessous de plat' : 'Toutes nos créations');
      document.title = (cat ? cat.name + ' – ' : '') + 'Nos créations en bois | Wooden Brothers';

      if (!silent) {
        var url = location.pathname + (filter === 'all' ? '' : '?filter=' + encodeURIComponent(filter));
        history.replaceState(null, '', url);
      }
      if (scroll) {
        var top = grid.getBoundingClientRect().top + window.scrollY - 150;
        if (window.scrollY > top) window.scrollTo({ top: top, behavior: 'smooth' });
      }
    }
    apply(false, true);
  }).catch(function (err) {
    console.error(err);
    grid.innerHTML = '<div class="empty-state"><h3>Le catalogue est momentanément indisponible</h3><p>Retrouvez toutes nos créations sur <a href="https://www.etsy.com/fr/shop/WoodenBrothersArt" target="_blank" rel="noopener">notre boutique Etsy</a>.</p></div>';
  });
})();
