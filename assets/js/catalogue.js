/* =====================================================================
   Wooden Brothers — catalogue (page « Nos créations » et pages collection)
   Les grilles et les filtres sont pré-rendus par scripts/build.py ; ce script
   ajoute le filtrage instantané, le tri et la navigation sans rechargement.
   ===================================================================== */
(function () {
  'use strict';
  var WB = window.WB;
  var $ = WB.$, $$ = WB.$$;

  var grid = $('#catalogue-grid');
  var chips = $('#chips');
  var sortSel = $('#sort');
  var count = $('#results-count');
  var empty = $('#empty-state');
  var heading = $('#catalogue-title');
  if (!grid || !chips) return;

  // Anciens liens ?filter=… (encore indexés) -> collections actuelles
  var LEGACY = { 'dessous-plats': 'dessous-de-plat', 'dessous-verre': 'all' };

  function filterFromLocation() {
    var m = /^\/collections\/([a-z0-9-]+)\/?$/.exec(location.pathname);
    if (m) return m[1];
    var q = new URLSearchParams(location.search).get('filter');
    if (q) return LEGACY[q] || q;
    return 'all';
  }

  var filter = filterFromLocation();
  var sort = 'recent';

  WB.catalogue().then(function (data) {
    var virtual = {};
    (data.collections_virtuelles || []).forEach(function (c) { virtual[c.slug] = c; });
    var known = {};
    $$('[data-filter]', chips).forEach(function (c) { known[c.getAttribute('data-filter')] = c; });
    if (!known[filter]) filter = 'all';

    function matches(p) {
      if (filter === 'all') return true;
      if (virtual[filter]) return p.kind === virtual[filter].kind;
      return p.category === filter;
    }

    function apply(push, scroll) {
      var list = data.products.filter(matches);
      if (sort === 'price-asc') list.sort(function (a, b) { return a.price - b.price; });
      else if (sort === 'price-desc') list.sort(function (a, b) { return b.price - a.price; });
      else if (sort === 'name') list.sort(function (a, b) { return (a.short_title || a.title).localeCompare(b.short_title || b.title, 'fr'); });

      var prerendered = grid.getAttribute('data-prerendered');
      if (!(prerendered === filter && sort === 'recent' && grid.querySelector('.product-card'))) {
        grid.innerHTML = list.map(function (p, i) { return WB.productCard(p, data, { reveal: true, eager: i < 6 }); }).join('');
        grid.setAttribute('data-prerendered', sort === 'recent' ? filter : '');
        WB.observe(grid);
      }
      if (empty) empty.hidden = list.length > 0;
      if (count) count.textContent = WB.plural(list.length, 'création', 'créations');

      var chip = known[filter];
      $$('[data-filter]', chips).forEach(function (c) {
        var active = c === chip;
        c.classList.toggle('is-active', active);
        c.setAttribute('aria-current', active ? 'page' : 'false');
      });
      var name = filter === 'all' ? 'Toutes nos créations' : (chip ? chip.firstChild.textContent.trim() : filter);
      if (heading) heading.textContent = name;
      if (push) {
        var href = chip ? chip.getAttribute('href') : '/produits';
        history.pushState({ filter: filter }, '', href);
        document.title = (filter === 'all' ? 'Nos créations en bois' : name + ' – Créations en bois') + ' | Wooden Brothers';
      }
      if (scroll) {
        var top = grid.getBoundingClientRect().top + window.scrollY - 150;
        if (window.scrollY > top) window.scrollTo({ top: top, behavior: 'smooth' });
      }
    }

    chips.addEventListener('click', function (e) {
      var b = e.target.closest('[data-filter]');
      if (!b || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
      e.preventDefault();
      filter = b.getAttribute('data-filter');
      apply(true, true);
    });
    if (sortSel) sortSel.addEventListener('change', function () { sort = sortSel.value; apply(false, false); });
    window.addEventListener('popstate', function () { filter = filterFromLocation(); if (!known[filter]) filter = 'all'; apply(false, false); });

    // Ancien lien ?filter=… : on affiche la collection et on remplace l'URL par la page de collection
    if (/[?&]filter=/.test(location.search)) {
      var chip0 = known[filter];
      history.replaceState({ filter: filter }, '', chip0 ? chip0.getAttribute('href') : '/produits');
    }
    apply(false, false);
  }).catch(function (err) {
    console.error(err);
  });
})();
