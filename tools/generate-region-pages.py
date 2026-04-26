#!/usr/bin/env python3
"""
Generate per-region landing pages for SEO.

GitHub Pages does not support _redirects, so we create real folders:
  /skane/index.html
  /stockholm/index.html
  ...

Each is a copy of /index.html with pre-baked <title>, <meta description>,
og: tags, canonical, and hero H1 set to that region. The JS still picks up
the URL on load and applies the region filter.

Run after editing index.html:
    python3 tools/generate-region-pages.py

This regenerates all 28 region pages from the current index.html.
"""

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
INDEX = ROOT / 'index.html'

# Same map as in index.html (REGION_SLUGS).
REGIONS = [
    # (display name, ascii slug, is_country)
    ('Blekinge', 'blekinge', False),
    ('Dalarna', 'dalarna', False),
    ('Gotland', 'gotland', False),
    ('Gävleborg', 'gavleborg', False),
    ('Halland', 'halland', False),
    ('Jämtland', 'jamtland', False),
    ('Jönköping', 'jonkoping', False),
    ('Kalmar', 'kalmar', False),
    ('Kronoberg', 'kronoberg', False),
    ('Norrbotten', 'norrbotten', False),
    ('Skåne', 'skane', False),
    ('Stockholm', 'stockholm', False),
    ('Södermanland', 'sodermanland', False),
    ('Uppsala', 'uppsala', False),
    ('Värmland', 'varmland', False),
    ('Västerbotten', 'vasterbotten', False),
    ('Västernorrland', 'vasternorrland', False),
    ('Västmanland', 'vastmanland', False),
    ('Västra Götaland', 'vastra-gotaland', False),
    ('Örebro', 'orebro', False),
    ('Östergötland', 'ostergotland', False),
    ('Danmark', 'danmark', True),
    ('Finland', 'finland', True),
    ('Nederländerna', 'nederlanderna', True),
    ('Norge', 'norge', True),
    ('Spanien', 'spanien', True),
    ('Sverige', 'sverige', True),
    ('Tjeckien', 'tjeckien', True),
]


def make_meta(region: str, slug: str, is_country: bool):
    """Return (title, description, og_title, og_desc, url, h1_html, sub) for region."""
    if is_country:
        title = f'MC-träffar i {region} 2026 - MC Kalendern'
        desc = (f'MC-träffar i {region} 2026. Här samlar vi MC-evenemang som '
                f'svenska bikers reser till. Träffar, körningar och fester från 380+ arrangörer.')
    else:
        title = f'MC-träffar i {region} 2026 - MC-evenemang & körningar | MC Kalendern'
        desc = (f'MC-träffar och MC-evenemang i {region} 2026. Hitta din nästa träff, '
                f'körning eller mässa i {region}. Uppdateras dagligen från 380+ arrangörer.')
    url = f'https://druk.se/{slug}'
    h1_html = f'MC-träffar i <span>{region}</span>'
    sub = f'MC-evenemang och körningar i {region} 2026'
    return title, desc, title, desc, url, h1_html, sub


def patch_html(html: str, region: str, slug: str, is_country: bool) -> str:
    """Replace meta tags + hero H1 in the index.html content."""
    title, desc, og_title, og_desc, url, h1_html, sub = make_meta(region, slug, is_country)

    # Add <base href="/"> to <head> so ALL relative URLs in this region page
    # resolve from the site root, not from /dalarna/ etc. This catches:
    # - <img src="ads/foo.jpg"> set by JS at runtime
    # - background-image: url('hero.jpg') in CSS
    # - Card backgrounds applied via element.style.backgroundImage
    # - All club icons, ads, weather data fetches
    # Without this, every relative path on /dalarna/ tries /dalarna/ads/foo.jpg → 404.
    html = re.sub(r'(<head[^>]*>)', r'\1\n<base href="/">', html, count=1)

    # Belt-and-suspenders: also rewrite literal src=/href=/url() to absolute paths
    # for the static HTML (helps in browsers that have base href quirks).
    def absolutize(match):
        attr = match.group(1)
        path = match.group(2)
        if path.startswith(('http://', 'https://', '/', '#', 'data:', 'mailto:', 'tel:', 'javascript:')):
            return match.group(0)
        return f'{attr}="/{path}"'
    html = re.sub(r'(\bsrc|\bhref)="([^"]+)"', absolutize, html)

    def absolutize_css_url(match):
        quote = match.group(1) or ''
        path = match.group(2)
        if path.startswith(('http://', 'https://', '/', '#', 'data:')):
            return match.group(0)
        return f'url({quote}/{path}{quote})'
    html = re.sub(r'url\((["\']?)([^)"\']+)\1\)', absolutize_css_url, html)

    # <title>
    html = re.sub(r'<title>[^<]*</title>', f'<title>{title}</title>', html, count=1)
    # <meta name="description">
    html = re.sub(r'<meta\s+name="description"\s+content="[^"]*"\s*/?>',
                  f'<meta name="description" content="{desc}">', html, count=1)
    # <link rel="canonical">
    html = re.sub(r'<link\s+rel="canonical"\s+href="[^"]*"\s*/?>',
                  f'<link rel="canonical" href="{url}">', html, count=1)
    # og:url
    html = re.sub(r'<meta\s+property="og:url"\s+content="[^"]*"\s*/?>',
                  f'<meta property="og:url" content="{url}">', html, count=1)
    # og:title
    html = re.sub(r'<meta\s+property="og:title"\s+content="[^"]*"\s*/?>',
                  f'<meta property="og:title" content="{og_title}">', html, count=1)
    # og:description
    html = re.sub(r'<meta\s+property="og:description"\s+content="[^"]*"\s*/?>',
                  f'<meta property="og:description" content="{og_desc}">', html, count=1)
    # Hero H1 (class="hero-logo")
    html = re.sub(r'(<h1\s+class="hero-logo">)[^<]*(<span>[^<]*</span>)?[^<]*</h1>',
                  rf'\1{h1_html}</h1>', html, count=1)
    # Hero subtitle (class="hero-sub")
    html = re.sub(r'(<div\s+class="hero-sub">)[^<]*(</div>)',
                  rf'\g<1>{sub}\g<2>', html, count=1)
    return html


def main():
    if not INDEX.exists():
        print(f'ERROR: {INDEX} not found', file=sys.stderr)
        sys.exit(1)
    html = INDEX.read_text(encoding='utf-8')
    written = 0
    for region, slug, is_country in REGIONS:
        out_dir = ROOT / slug
        out_dir.mkdir(exist_ok=True)
        out_file = out_dir / 'index.html'
        out_html = patch_html(html, region, slug, is_country)
        out_file.write_text(out_html, encoding='utf-8')
        written += 1
        print(f'  wrote /{slug}/index.html')
    print(f'\nDone. Generated {written} region pages.')
    print('Remember: re-run this script after every change to index.html.')


if __name__ == '__main__':
    main()
