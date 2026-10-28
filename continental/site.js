// Shared behaviour for every Continental concept page: the "Find an act" search
// box and click-to-play videos. Pages include it with
// <script src="/continental/site.js" defer></script>.
// Markup is C2's: .find > #find-q (combobox) + ul#find-results (listbox), and
// a.video.embed[data-embed] thumbnails.
(function () {
  // --- Photos -------------------------------------------------------------
  // Act photos load from continentalentertainment.ca. If one fails (their
  // server is down, or blocks other sites), hide it so the card's own
  // background shows instead of a broken-image icon. Images that already
  // failed before this script ran are caught by the sweep below.
  function hideBroken(img) {
    img.style.visibility = 'hidden';
    img.setAttribute('data-failed', '');
  }
  document.addEventListener('error', function (e) {
    if (e.target.tagName === 'IMG') hideBroken(e.target);
  }, true);
  document.querySelectorAll('img').forEach(function (img) {
    // Lazy images that haven't started loading can also report complete with no size.
    if (img.loading !== 'lazy' && img.complete && img.getAttribute('src') && img.naturalWidth === 0) hideBroken(img);
  });

  // --- Search -------------------------------------------------------------
  var index = null;

  function load() {
    if (!index) {
      index = fetch('/continental/search.json')
        .then(function (r) { return r.json(); })
        .catch(function () { return []; });
    }
    return index;
  }

  function norm(s) {
    return (s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9 ]/g, ' ');
  }

  // Every typed word must appear in the act's name, label or category. Only when
  // nothing matches that way do descriptions count, so "abba" doesn't also list
  // every act whose blurb happens to mention ABBA.
  function rank(acts, q) {
    var words = norm(q).split(/\s+/).filter(Boolean);
    if (!words.length) return [];
    function hits(field) {
      return acts.filter(function (a) {
        var text = norm(field(a));
        return words.every(function (w) { return text.indexOf(w) >= 0; });
      });
    }
    var found = hits(function (a) { return [a.n, a.k, a.c].join(' '); });
    if (!found.length) found = hits(function (a) { return [a.n, a.k, a.c, a.t].join(' '); });
    return found.map(function (a) {
      var at = norm(a.n).indexOf(words[0]);
      return { a: a, score: at === 0 ? 0 : (at > 0 ? 1 : 2) };
    }).sort(function (x, y) {
      return x.score - y.score || x.a.n.localeCompare(y.a.n);
    }).slice(0, 8).map(function (x) { return x.a; });
  }

  function row(a, i) {
    var li = document.createElement('li');
    li.setAttribute('role', 'option');
    li.id = 'find-opt-' + i;
    var link = document.createElement('a');
    link.href = a.u;
    var img = document.createElement('img');
    img.alt = '';
    img.loading = 'lazy';
    if (a.p) img.src = a.p;
    var text = document.createElement('span');
    var name = document.createElement('b');
    name.textContent = a.n;
    var label = document.createElement('small');
    label.textContent = a.k === a.c ? a.c : a.k + ' · ' + a.c;
    text.appendChild(name);
    text.appendChild(label);
    link.appendChild(img);
    link.appendChild(text);
    li.appendChild(link);
    return li;
  }

  var input = document.getElementById('find-q');
  var list = document.getElementById('find-results');
  if (input && list) {
    var box = input.closest('.find') || input.parentElement;
    var active = -1;

    var show = function (open) {
      list.hidden = !open;
      input.setAttribute('aria-expanded', String(open));
      if (!open) input.removeAttribute('aria-activedescendant');
    };

    var render = function (results, q) {
      list.innerHTML = '';
      active = -1;
      if (!q) { show(false); return; }
      if (!results.length) {
        var li = document.createElement('li');
        li.className = 'find-empty';
        li.textContent = 'No acts match “' + q + '”';
        list.appendChild(li);
      } else {
        results.forEach(function (a, i) { list.appendChild(row(a, i)); });
      }
      show(true);
    };

    var highlight = function (i) {
      var opts = list.querySelectorAll('[role=option]');
      if (!opts.length) return;
      active = (i + opts.length) % opts.length;
      opts.forEach(function (o, j) { o.setAttribute('aria-selected', String(j === active)); });
      input.setAttribute('aria-activedescendant', opts[active].id);
      opts[active].scrollIntoView({ block: 'nearest' });
    };

    input.addEventListener('focus', load);
    input.addEventListener('input', function () {
      var q = input.value.trim();
      load().then(function (acts) { if (input.value.trim() === q) render(rank(acts, q), q); });
    });
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') { e.preventDefault(); highlight(active + 1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); highlight(active - 1); }
      else if (e.key === 'Escape') { show(false); }
      else if (e.key === 'Enter') {
        var opts = list.querySelectorAll('[role=option] a');
        var pick = opts[active >= 0 ? active : 0];
        if (pick) { e.preventDefault(); location.href = pick.href; }
      }
    });
    document.addEventListener('click', function (e) {
      if (!box.contains(e.target)) show(false);
    });
  }

  // --- Videos -------------------------------------------------------------
  // Thumbnails keep a plain watch link (works without JavaScript); with it,
  // a click swaps the thumbnail for the player.
  document.addEventListener('click', function (e) {
    var link = e.target.closest('.video.embed[data-embed]');
    if (!link) return;
    e.preventDefault();
    var src = link.getAttribute('data-embed');
    var frame = document.createElement('iframe');
    frame.src = src + (src.indexOf('?') < 0 ? '?' : '&') + 'autoplay=1';
    frame.title = link.getAttribute('aria-label') || 'Video';
    frame.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
    frame.allowFullscreen = true;
    // YouTube refuses to play (error 153) when the embed doesn't say which site it's on.
    frame.referrerPolicy = 'strict-origin-when-cross-origin';
    link.replaceChildren(frame);
    link.removeAttribute('href');
    link.removeAttribute('data-embed');
  });
})();
