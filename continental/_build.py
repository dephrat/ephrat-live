"""Generate the Continental concept's category and act pages.

Every act page is written at the same address as on continentalentertainment.ca
(e.g. /continental/tributes/metallica/) and carries over their SEO tags, with
the canonical pointing at their real page. Inputs, all in _data/:
  acts.json          every act page's content and SEO (from _extract.py)
  content.json       category intros, plus curated names/types/highlights for 12 acts
  category-seo.json  their category pages' SEO tags
  roster.json        category thumbnails, used when an act page has no photo
  photo-colors.json  each act photo's average colour, for the accent swatch
Run: python3 continental/_build.py
"""
import colorsys
import difflib
import hashlib
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = '/continental'
SITE = 'https://continentalentertainment.ca'
FALLBACK_PHOTO = SITE + '/wp-content/uploads/2022/07/continental-header-scaled.jpg'

# C2's accent swatches; each passes 5:1 contrast on the page and card backgrounds.
SWATCHES = {
    'tributes': ['#6A87FB', '#7BA7F4', '#8088F8', '#9DAEF1'],
    'top-40': ['#9F6AFB', '#937BF4', '#B264F7', '#BC9DF1'],
    'recording-acts': ['#6ABFFB', '#7BD6F4', '#64A1F7', '#9DCEF1'],
    'dj-services': ['#FB6AD7', '#F47BEA', '#F764BA', '#F19DDC'],
    'magicians-novelty-acts': ['#6AFBF6', '#7BF4DC', '#64E3F7', '#9DF1EE'],
    'jazz-artists': ['#8A80FB', '#7B85F4', '#9A7EF8', '#A49DF1'],
    'asian-entertainment': ['#FB876A', '#F47F7B', '#F79A64', '#F1AE9D'],
    'makeup': ['#FB6A9A', '#F47BB8', '#F7647C', '#F19DB9'],
    'models': ['#99AECC', '#A2BBCD', '#94A1C7', '#B8C4D6'],
}


def load(name):
    return json.loads((HERE / '_data' / name).read_text())


acts = load('acts.json')
content = load('content.json')
cat_seo = load('category-seo.json')
roster = load('roster.json')
colors = load('photo-colors.json')
cat_tpl = (HERE / '_templates/category.html').read_text()
act_tpl = (HERE / '_templates/act.html').read_text()
cats = {c['slug']: c for c in content['categories']}
curated = {a['source'].split(SITE, 1)[-1]: a for a in content['acts'] if a['source'].startswith(SITE)}
thumbs = {r['url']: r['photo'] for rows in roster.values() for r in rows}


def esc(s):
    return html.escape(s or '', quote=True)


def jsonld(s):
    # Their schema is raw JSON inside a <script>; never let it close the tag early.
    return (s or '{}').replace('</', '<\\/')


def fill(tpl, values):
    for k, v in values.items():
        tpl = tpl.replace('{{' + k + '}}', v)
    left = sorted(set(re.findall(r'\{\{\w+\}\}', tpl)))
    assert not left, f'unfilled slots: {left}'
    return tpl


def cut(tpl, block):
    return re.sub(r'<!--%s-->.*?<!--/%s-->' % (block, block), '', tpl, flags=re.S)


def card(href, photo, name, typ):
    img = f'<img loading="lazy" src="{esc(photo)}" alt="{esc(name)}">' if photo else ''
    return (f'<a class="act" href="{esc(href)}"><span class="img">{img}</span>'
            f'<span class="meta"><span><b>{esc(name)}</b><span>{esc(typ)}</span></span>'
            f'<span class="gold" aria-hidden="true">→</span></span></a>')


def photo_for(a):
    if a['photo'].get('url'):
        return a['photo']['url'], a['photo'].get('w', 0), a['photo'].get('h', 0)
    return (a['seo']['og_image'] or thumbs.get(a['source']) or ''), 0, 0


def variant(url, w, h):
    # C2's rule: stage for wide landscape, split for other landscape,
    # portrait for tall, small or unmeasured photos, type when there is none.
    if not url:
        return 'type'
    if w and h and w > h:
        return 'stage' if w >= 1400 else ('split' if w >= 600 else 'portrait')
    return 'portrait'


def accent(a):
    sw = SWATCHES[a['category']]
    rgb = colors.get(a['path'])
    if rgb:
        hh, ll, ss = colorsys.rgb_to_hls(*[c / 255 for c in rgb])
        if ss > 0.12 and 0.08 < ll < 0.92:
            def dist(hexc):
                r, g, b = (int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5))
                d = abs(colorsys.rgb_to_hls(r, g, b)[0] - hh)
                return min(d, 1 - d)
            return min(sw, key=dist)
    # Grey or missing photo: no usable hue, so spread acts across the swatches by address.
    return sw[int(hashlib.md5(a['path'].encode()).hexdigest(), 16) % len(sw)]


def split_intro(paras):
    """First sentence or two of the bio, up to about 230 characters."""
    sentences = re.split(r'(?<=[.!?])\s+', paras[0] if paras else '')
    intro = ''
    for s in sentences:
        if intro and len(intro) + len(s) > 230:
            break
        intro = (intro + ' ' + s).strip()
    return intro


def write(rel, text):
    out = HERE.parent / rel.strip('/') / 'index.html'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    return out


def redirect_page(target):
    t = esc(target)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Moved</title>'
            f'<meta name="robots" content="noindex"><link rel="canonical" href="{t}">'
            f'<meta http-equiv="refresh" content="0; url={t}"></head>'
            f'<body><p>This page moved to <a href="{t}">{t}</a>.</p></body></html>')


def display(a):
    c = curated.get(a['path'])
    if c:
        return c['name'], c['type']
    # A caption that only repeats the title (or misspells it) adds nothing; show the category instead.
    same = difflib.SequenceMatcher(None, a['name'].strip().lower(), a['page_title'].strip().lower()).ratio() > 0.85
    return a['page_title'], cats[a['category']]['name'] if same else a['name']


written = []
by_cat = {}
for a in acts:
    by_cat.setdefault(a['category'], []).append(a)

for a in acts:
    c = cats[a['category']]
    name, kicker = display(a)
    photo, w, h = photo_for(a)
    paras = a['bio'] or []
    intro = split_intro(paras)
    rest = list(paras)
    if rest and intro and rest[0].startswith(intro):
        rest[0] = rest[0][len(intro):].strip()
    rest = [p for p in rest if p]
    group = by_cat[a['category']]
    i = group.index(a)
    more = [group[(i + k) % len(group)] for k in range(1, min(4, len(group)))]
    credits = curated.get(a['path'], {}).get('credits', [])

    page = act_tpl
    if not a['videos']:
        page = cut(page, 'video')
    if not a['songs']:
        page = cut(page, 'songs')
    if not credits:
        page = cut(page, 'credits')
    if not rest:
        page = cut(page, 'bio')
    page = fill(page, {
        'name': esc(name), 'type': esc(kicker), 'intro': esc(intro),
        'bio': '\n'.join(f'<p>{esc(p)}</p>' for p in rest),
        'photo': esc(photo), 'video_id': esc(a['videos'][0] if a['videos'] else ''),
        'songs': '\n'.join(f'<li>{esc(s)}</li>' for s in a['songs']),
        'credits': '\n'.join(f'<li>{esc(s)}</li>' for s in credits),
        'source_url': esc(a['source']), 'category_name': esc(c['name']),
        'category_url': f'{ROOT}/{c["slug"]}/',
        'variant': variant(photo, w, h), 'accent': accent(a),
        'more_grid': '\n'.join(card(ROOT + m['path'], photo_for(m)[0], *display(m)) for m in more),
        'seo_title': esc(a['seo']['title']), 'meta_description': esc(a['seo']['description']),
        'canonical': esc(a['source']), 'og_image': esc(a['seo']['og_image'] or photo),
        'schema_jsonld': jsonld(a['seo']['schema_jsonld']),
    })
    written.append(write(ROOT + a['path'], page))

for c in content['categories']:
    seo = cat_seo[c['slug']]
    members = by_cat.get(c['slug'], [])
    cards = [card(ROOT + m['path'], photo_for(m)[0], *display(m)) for m in members]
    if not cards:
        cards = [f'<p style="grid-column:1/-1;margin:0;color:var(--mute)">Acts in this category aren\'t listed one by one. '
                 f'<a href="{esc(c["source"])}">See the line-up on their current site</a>.</p>']
    hero = next((photo_for(m)[0] for m in members if photo_for(m)[0]), FALLBACK_PHOTO)
    page = fill(cat_tpl, {
        'category_name': esc(c['name']), 'intro': esc(c['intro']), 'photo': esc(hero),
        'source_url': esc(c['source']), 'acts_grid': '\n'.join(cards),
        'accent': SWATCHES[c['slug']][0], 'seo_title': esc(seo['title']),
        'meta_description': esc(seo['description']), 'canonical': esc(seo['source']),
        'og_image': esc(seo['og_image'] or hero), 'schema_jsonld': jsonld(seo['schema_jsonld']),
    })
    written.append(write(f'{ROOT}/{c["slug"]}', page))

# Our first 12 act pages used our own slugs; send those addresses to the real ones.
for a in content['acts']:
    if not a['source'].startswith(SITE):
        continue
    new = ROOT + a['source'].split(SITE, 1)[1]
    old = f'{ROOT}/{a["category"]}/{a["slug"]}/'
    if old != new:
        written.append(write(old, redirect_page(new)))

# Search index for the site-wide "Find an act" box: one short record per act.
index = [{'n': display(a)[0], 'k': display(a)[1], 'c': cats[a['category']]['name'],
          'u': ROOT + a['path'], 'p': photo_for(a)[0],
          't': ' '.join([a['page_title'], a['name'], a['seo']['description']])}
         for a in acts]
(HERE / 'search.json').write_text(json.dumps(index, ensure_ascii=False, separators=(',', ':')))

print(f'{len(written)} pages written, {len(index)} acts in search.json')
