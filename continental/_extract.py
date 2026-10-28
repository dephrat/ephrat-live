"""Pull every act page's content and SEO data from a local snapshot of continentalentertainment.ca.

Inputs (snapshot taken 2026-10-27, kept in niagara-leads/continental/snapshot-2026-10-27):
  WP_PAGES   -- /wp-json/wp/v2/pages dump (rendered content of all pages)
  HTML_INDEX -- [url, file, status] for each page's full HTML (for <head> SEO tags)
Output: _data/acts.json, one record per act page, keyed by their own URL path.
"""
import hashlib
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
WP_PAGES = Path('/Users/danielephrat/Documents/Code/niagara-leads/continental/raw/allpages.json')
HTML_DIR = Path('/Users/danielephrat/Documents/Code/niagara-leads/continental/snapshot-2026-10-27/pages')
CATEGORY_IDS = {22: 'tributes', 112: 'top-40', 11: 'recording-acts', 3664: 'dj-services',
                43: 'magicians-novelty-acts', 25: 'jazz-artists', 30: 'makeup', 38: 'models'}


def text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()


def head_tag(h, pattern):
    m = re.search(pattern, h, re.S | re.I)
    return html.unescape(m.group(1)).strip() if m else ''


def parse_content(c):
    """Split WordPress content into photo, caption, bio paragraphs, songs and videos."""
    photo = {}
    m = re.search(r'<img[^>]*?data-src="(https://continentalentertainment\.ca/wp-content/uploads/[^"]+)"[^>]*>', c)
    if m:
        tag = m.group(0)
        ar = re.search(r'aspect-ratio:\s*(\d+)/(\d+)', tag)
        w = re.search(r'\bwidth="(\d+)"', tag)
        # Two of their pages have a stray &quot; typed into the image address; strip it.
        photo = {'url': re.sub(r'(&quot;|")+$', '', m.group(1)),
                 'w': int(ar.group(1)) if ar else (int(w.group(1)) if w else 0),
                 'h': int(ar.group(2)) if ar else 0,
                 'alt': html.unescape(re.search(r'alt="([^"]*)"', tag).group(1)) if 'alt="' in tag else ''}
    caption = text(re.search(r'<figcaption[^>]*>(.*?)</figcaption>', c, re.S).group(1)) if '<figcaption' in c else ''

    lower = c.lower()
    cut = lower.find('song list')
    body, tail = (c[:cut], c[cut:]) if cut >= 0 else (c, '')
    body = re.sub(r'<figure.*?</figure>|<iframe.*?</iframe>|<script.*?</script>', ' ', body, flags=re.S)
    paras = [text(p) for p in re.findall(r'<p\b[^>]*>(.*?)</p>', body, re.S)]
    paras = [p for p in paras if p and p.lower() not in ('song list', 'song list:')]
    if not paras:
        paras = [p for p in (text(x) for x in re.split(r'<h[1-6][^>]*>.*?</h[1-6]>', body)) if p]

    songs = []
    if tail:
        ul = re.search(r'<ul\b.*?</ul>', tail, re.S)
        if ul:
            songs = [text(li) for li in re.findall(r'<li\b[^>]*>(.*?)</li>', ul.group(0), re.S)]
        else:
            block = re.split(r'<h[1-6]|<figure', tail[9:], maxsplit=1)[0]
            songs = [text(x) for x in re.split(r'<br\s*/?>|</p>', block)]
        songs = [s for s in songs if s and len(s) < 90 and 'song list' not in s.lower()]

    videos = list(dict.fromkeys(re.findall(r'(?:youtube(?:-nocookie)?\.com/(?:embed/|watch\?v=)|youtu\.be/)([\w-]{11})', c)))
    vimeo = list(dict.fromkeys(re.findall(r'player\.vimeo\.com/video/(\d+)', c)))
    return photo, caption, paras, songs, videos, vimeo


def main():
    pages = json.loads(WP_PAGES.read_text())
    acts = []
    for p in pages:
        cat = CATEGORY_IDS.get(p['parent'])
        if not cat:
            continue
        url = p['link']
        f = HTML_DIR / (hashlib.md5(url.encode()).hexdigest() + '.html')
        h = f.read_text(errors='replace') if f.exists() else ''
        photo, caption, paras, songs, videos, vimeo = parse_content(p['content']['rendered'])
        page_title = html.unescape(p['title']['rendered']).strip()
        schema = re.search(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', h, re.S)
        acts.append({
            'path': url.split('continentalentertainment.ca', 1)[1],
            'category': cat,
            'page_title': page_title,
            'name': caption or page_title,
            'photo': photo,
            'bio': paras,
            'songs': songs,
            'videos': videos,
            'vimeo': vimeo,
            'source': url,
            'modified': p['modified'],
            'seo': {
                'title': head_tag(h, r'<title>(.*?)</title>'),
                'description': head_tag(h, r'<meta name="description" content="([^"]*)"'),
                'og_title': head_tag(h, r'<meta property="og:title" content="([^"]*)"'),
                'og_description': head_tag(h, r'<meta property="og:description" content="([^"]*)"'),
                'og_image': re.sub(r'"+$', '', head_tag(h, r'<meta property="og:image" content="([^"]*)"')),
                'schema_jsonld': schema.group(1).strip() if schema else '',
            },
        })
    acts.sort(key=lambda a: a['path'])
    (HERE / '_data/acts.json').write_text(json.dumps(acts, indent=1, ensure_ascii=False))
    print(len(acts), 'acts extracted')


if __name__ == '__main__':
    main()
