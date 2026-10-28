"""Generate the Continental concept's category and act pages.

Fills _templates/category.html and _templates/act.html from _data/content.json
(our paraphrased copy) and _data/roster.json (act names, links and photos pulled
from continentalentertainment.ca). Run from anywhere: python3 continental/_build.py
"""
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = '/continental/'
FALLBACK_PHOTO = 'https://continentalentertainment.ca/wp-content/uploads/2022/07/continental-header-scaled.jpg'

content = json.loads((HERE / '_data/content.json').read_text())
roster = json.loads((HERE / '_data/roster.json').read_text())
cat_tpl = (HERE / '_templates/category.html').read_text()
act_tpl = (HERE / '_templates/act.html').read_text()
IMG = content['img_base']
cats = {c['slug']: c for c in content['categories']}


def esc(s):
    return html.escape(s, quote=True)


def fill(tpl, values):
    for k, v in values.items():
        tpl = tpl.replace('{{' + k + '}}', v)
    left = re.findall(r'\{\{\w+\}\}', tpl)
    assert not left, f'unfilled slots: {left}'
    return tpl


def cut(tpl, block):
    return re.sub(r'<!--%s-->.*?<!--/%s-->' % (block, block), '', tpl, flags=re.S)


def card(href, photo, name, typ):
    img = f'<img loading="lazy" src="{esc(photo)}" alt="{esc(name)}">' if photo else ''
    return (f'<a class="act" href="{esc(href)}"><span class="img">{img}</span>'
            f'<span class="meta"><span><b>{esc(name)}</b><span>{esc(typ)}</span></span>'
            f'<span class="gold" aria-hidden="true">→</span></span></a>')


def write(path, text):
    out = HERE / path / 'index.html'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    return out


written = []

for a in content['acts']:
    c = cats[a['category']]
    page = act_tpl
    if not a['video_id']:
        page = cut(page, 'video')
    if not a['songs']:
        page = cut(page, 'songs')
    if not a['credits']:
        page = cut(page, 'credits')
    page = fill(page, {
        'name': esc(a['name']), 'type': esc(a['type']), 'intro': esc(a['bio']),
        'photo': esc(IMG + a['photo']), 'video_id': esc(a['video_id']),
        'songs': '\n'.join(f'<li>{esc(s)}</li>' for s in a['songs']),
        'credits': '\n'.join(f'<li>{esc(s)}</li>' for s in a['credits']),
        'source_url': esc(a['source']), 'category_name': esc(c['name']),
        'category_url': ROOT + c['slug'] + '/',
    })
    written.append(write(f"{c['slug']}/{a['slug']}", page))

for c in content['categories']:
    ours = [a for a in content['acts'] if a['category'] == c['slug']]
    own_sources = {a['source'] for a in ours}
    cards = [card(f"{ROOT}{c['slug']}/{a['slug']}/", IMG + a['photo'], a['name'], a['type']) for a in ours]
    cards += [card(r['url'], r['photo'], r['title'], c['name'])
              for r in roster.get(c['slug'], []) if r['url'] not in own_sources]
    if not cards:
        cards = [f'<p style="grid-column:1/-1;margin:0;color:var(--mute)">Acts in this category aren\'t listed one by one. '
                 f'<a href="{esc(c["source"])}">See the line-up on their current site</a>.</p>']
    hero = IMG + ours[0]['photo'] if ours else next((r['photo'] for r in roster.get(c['slug'], []) if r['photo']), FALLBACK_PHOTO)
    page = fill(cat_tpl, {
        'category_name': esc(c['name']), 'intro': esc(c['intro']), 'photo': esc(hero),
        'source_url': esc(c['source']), 'acts_grid': '\n'.join(cards),
    })
    written.append(write(c['slug'], page))

print(f'{len(written)} pages written')
