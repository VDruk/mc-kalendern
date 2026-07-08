#!/usr/bin/env python3
"""
Generate per-region landing pages (and the /moped/ landing page) for SEO.

GitHub Pages does not support _redirects, so we create real folders:
  /skane/index.html
  /stockholm/index.html
  /moped/index.html
  ...

Each is a copy of /index.html with pre-baked <title>, <meta description>,
og: tags, canonical, and hero H1 set to that region (or to moped). The JS still
picks up the URL on load and applies the matching filter.

Run after editing index.html:
    python3 tools/generate-region-pages.py

This regenerates all region pages AND the moped page from the current index.html.
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
    # Countries: ALL countries that ever had an event (past-only ones included).
    # Never remove a country here because it lacks upcoming events - the pages
    # keep their SEO value and show past events via "Visa passerade".
    ('Danmark', 'danmark', True),
    ('Estland', 'estland', True),
    ('Finland', 'finland', True),
    ('Italien', 'italien', True),
    ('Litauen', 'litauen', True),
    ('Nederländerna', 'nederlanderna', True),
    ('Norge', 'norge', True),
    ('Portugal', 'portugal', True),
    ('Spanien', 'spanien', True),
    ('Sverige', 'sverige', True),
    ('Tjeckien', 'tjeckien', True),
]


def make_meta(region: str, slug: str, is_country: bool):
    """Return (title, description, og_title, og_desc, url, h1_html, sub) for region."""
    if is_country:
        title = f'MC-träffar i {region} 2026 - MC Kalendern'
        desc = (f'MC-träffar i {region} 2026. Här samlar vi MC-evenemang som '
                f'svenska bikers reser till. Träffar, körningar och fester från hundratals arrangörer.')
    else:
        title = f'MC-träffar i {region} 2026 - MC-evenemang & körningar | MC Kalendern'
        desc = (f'MC-träffar och MC-evenemang i {region} 2026. Hitta din nästa träff, '
                f'körning eller mässa i {region}. Uppdateras dagligen från hundratals arrangörer.')
    # Trailing slash so canonical matches the indexed URL. Without it, GSC flags
    # /orebro/ as "Alternate page with proper canonical tag" of /orebro.
    url = f'https://druk.se/{slug}/'
    h1_html = f'MC-träffar i <span>{region}</span>'
    sub = f'MC-evenemang och körningar i {region} 2026'
    return title, desc, title, desc, url, h1_html, sub


def make_moped_meta():
    """Return meta tuple for the /moped/ landing page (vehicle = moped)."""
    title = 'Mopedträffar & mopedrally 2026 - MC Kalendern'
    desc = ('Mopedträffar, mopedrally och mopedevenemang i Sverige 2026. Hitta nästa '
            'mopedträff och mopedrally nära dig. Uppdateras dagligen.')
    url = 'https://druk.se/moped/'
    h1_html = 'Moped<span>kalendern</span>'
    sub = 'Mopedträffar och mopedrally i Sverige 2026'
    return title, desc, title, desc, url, h1_html, sub


def absolutize_html(html: str) -> str:
    """Add <base href="/"> and rewrite relative src/href/url() to absolute paths,
    so a page served from a subfolder (/dalarna/, /moped/) still loads root assets."""
    html = re.sub(r'(<head[^>]*>)', r'\1\n<base href="/">', html, count=1)

    def absolutize(match):
        attr = match.group(1)
        path = match.group(2)
        if path.startswith(('http://', 'https://', '/', '#', 'data:', 'mailto:', 'tel:', 'javascript:')):
            return match.group(0)
        # Skip JS template-literal placeholders (e.g. href="${event.link}").
        if path.startswith('${') or '${' in path:
            return match.group(0)
        return f'{attr}="/{path}"'
    html = re.sub(r'(\bsrc|\bhref)="([^"]+)"', absolutize, html)

    def absolutize_css_url(match):
        quote = match.group(1) or ''
        path = match.group(2)
        if path.startswith(('http://', 'https://', '/', '#', 'data:')):
            return match.group(0)
        if path.startswith('${') or '${' in path:
            return match.group(0)
        return f'url({quote}/{path}{quote})'
    html = re.sub(r'url\((["\']?)([^)"\']+)\1\)', absolutize_css_url, html)
    return html


def apply_meta(html: str, title, desc, og_title, og_desc, url, h1_html, sub) -> str:
    """Replace title / description / canonical / og tags / hero H1 / hero subtitle."""
    html = re.sub(r'<title>[^<]*</title>', f'<title>{title}</title>', html, count=1)
    html = re.sub(r'<meta\s+name="description"\s+content="[^"]*"\s*/?>',
                  f'<meta name="description" content="{desc}">', html, count=1)
    html = re.sub(r'<link\s+rel="canonical"\s+href="[^"]*"\s*/?>',
                  f'<link rel="canonical" href="{url}">', html, count=1)
    html = re.sub(r'<meta\s+property="og:url"\s+content="[^"]*"\s*/?>',
                  f'<meta property="og:url" content="{url}">', html, count=1)
    html = re.sub(r'<meta\s+property="og:title"\s+content="[^"]*"\s*/?>',
                  f'<meta property="og:title" content="{og_title}">', html, count=1)
    html = re.sub(r'<meta\s+property="og:description"\s+content="[^"]*"\s*/?>',
                  f'<meta property="og:description" content="{og_desc}">', html, count=1)
    html = re.sub(r'(<h1\s+class="hero-logo">)[^<]*(<span>[^<]*</span>)?[^<]*</h1>',
                  rf'\1{h1_html}</h1>', html, count=1)
    html = re.sub(r'(<div\s+class="hero-sub">)[^<]*(</div>)',
                  rf'\g<1>{sub}\g<2>', html, count=1)
    return html


def patch_html(html: str, meta) -> str:
    return apply_meta(absolutize_html(html), *meta)


def main():
    if not INDEX.exists():
        print(f'ERROR: {INDEX} not found', file=sys.stderr)
        sys.exit(1)
    html = INDEX.read_text(encoding='utf-8')
    written = 0
    for region, slug, is_country in REGIONS:
        out_dir = ROOT / slug
        out_dir.mkdir(exist_ok=True)
        (out_dir / 'index.html').write_text(patch_html(html, make_meta(region, slug, is_country)), encoding='utf-8')
        written += 1
        print(f'  wrote /{slug}/index.html')
    # Vehicle landing page: /moped/
    moped_dir = ROOT / 'moped'
    moped_dir.mkdir(exist_ok=True)
    (moped_dir / 'index.html').write_text(patch_html(html, make_moped_meta()), encoding='utf-8')
    print('  wrote /moped/index.html')
    print(f'\nDone. Generated {written} region pages + 1 moped page.')
    print('Remember: re-run this script after every change to index.html.')


if __name__ == '__main__':
    main()
