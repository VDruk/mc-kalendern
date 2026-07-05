/*
 * MC Kalendern - per-event share links ("Dela") backend
 * Cloudflare Worker. Route: druk.se/e/*
 *
 * Goal: when someone shares druk.se/e/<event-id>, Facebook / WhatsApp / iMessage /
 * Discord etc. should show a rich preview (the event title, summary and its photo)
 * instead of the generic site preview. We do this by serving the normal index.html
 * with per-event Open Graph + Twitter meta tags injected on the edge via HTMLRewriter.
 *
 * A real human who clicks the link gets the full app: index.html loads, its JS sees
 * the /e/<id> path and opens that event (see openSharedEvent in index.html).
 *
 * Event facts come from og-data.json (built by tools/build-og-data.py), which is
 * small and edge-cached so we do not parse the 1.3 MB events.js per request.
 *
 * NOTE: this Worker only runs on /e/*. It fetches /index.html and /og-data.json,
 * neither of which match /e/*, so there is no loop.
 */

const SITE = 'https://druk.se';
const DEFAULT_IMG = SITE + '/ads/og-image-cover.jpg';
const DEFAULT_TITLE = 'MC Kalender 2026 | 1700+ MC-träffar och evenemang i Sverige';
const DEFAULT_DESC = 'Sveriges största MC-kalender. Hitta MC-träff idag, MC-kortege i helgen eller planera hela säsongen. 1700+ evenemang från hundratals arrangörer.';

// Sets the `content` attribute on a <meta> tag.
class MetaContent {
  constructor(value) { this.value = value; }
  element(el) { el.setAttribute('content', this.value); }
}

// Replaces the text inside <title>.
class TitleText {
  constructor(value) { this.value = value; }
  element(el) { el.setInnerContent(this.value); } // text mode = HTML-escaped
}

// Prepends <base href="/"> so the page works when served from /e/<id>.
class HeadBase {
  element(el) { el.prepend('<base href="/">', { html: true }); }
}

// Appends raw HTML (e.g. a JSON-LD script) at the end of <head>.
class HeadAppend {
  constructor(html) { this.html = html; }
  element(el) { el.append(this.html, { html: true }); }
}

// Sets the href attribute (canonical link).
class LinkHref {
  constructor(value) { this.value = value; }
  element(el) { el.setAttribute('href', this.value); }
}

// Builds schema.org Event JSON-LD from an og-data row.
// Row: [name, desc, backImage, date, dateEnd, time, location, region, organizer]
function eventJsonLd(ev, id) {
  const [name, desc, img, date, dateEnd, time, location, region, organizer] = ev;
  if (!date) return null;
  const ld = {
    '@context': 'https://schema.org',
    '@type': 'Event',
    name: name,
    startDate: time ? date + 'T' + time + ':00+02:00' : date,
    endDate: dateEnd || date,
    eventStatus: 'https://schema.org/EventScheduled',
    eventAttendanceMode: 'https://schema.org/OfflineEventAttendanceMode',
    description: desc || undefined,
    image: absImage(img),
    url: SITE + '/e/' + encodeURIComponent(id),
    location: {
      '@type': 'Place',
      name: location || region || 'Sverige',
      address: { '@type': 'PostalAddress', addressRegion: region || undefined, addressCountry: 'SE' }
    },
    organizer: organizer ? { '@type': 'Organization', name: organizer } : undefined
  };
  return '<script type="application/ld+json">' +
    JSON.stringify(ld).replace(/</g, '\\u003c') + '</scr' + 'ipt>';
}

async function getOgData(ctx) {
  const cacheKey = new Request(SITE + '/og-data.json');
  const cached = await caches.default.match(cacheKey);
  if (cached) {
    try { return await cached.json(); } catch (e) { /* fall through */ }
  }
  const resp = await fetch(SITE + '/og-data.json', { cf: { cacheTtl: 300, cacheEverything: true } });
  if (!resp.ok) return null;
  // store a copy in the edge cache for 5 min
  ctx.waitUntil(caches.default.put(cacheKey, new Response(resp.clone().body, {
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=300' }
  })));
  try { return await resp.json(); } catch (e) { return null; }
}

function absImage(img) {
  if (!img) return DEFAULT_IMG;
  if (/^https?:\/\//i.test(img)) return img;
  return SITE + '/' + img.replace(/^\/+/, '');
}

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    const m = url.pathname.match(/^\/e\/(.+?)\/?$/);

    // Not an event link -> send to the homepage.
    if (!m) return Response.redirect(SITE + '/', 302);

    const id = decodeURIComponent(m[1]).toLowerCase();

    // Fetch the live page (path is /index.html, so this Worker does not re-trigger).
    const pageResp = await fetch(SITE + '/index.html', {
      headers: { 'User-Agent': req.headers.get('User-Agent') || 'mc-og-worker' }
    });
    if (!pageResp.ok) return Response.redirect(SITE + '/', 302);

    const data = await getOgData(ctx);
    const ev = data && data[id]; // [name, desc, backImage, date, dateEnd, time, location, region, organizer]

    const rewriter = new HTMLRewriter().on('head', new HeadBase());

    if (ev) {
      const title = ev[0] + ' | MC Kalendern';
      const desc = (ev[1] && ev[1].trim()) || DEFAULT_DESC;
      const image = absImage(ev[2]);
      const pageUrl = SITE + '/e/' + encodeURIComponent(id);

      rewriter
        .on('title', new TitleText(title))
        .on('meta[name="description"]', new MetaContent(desc))
        .on('meta[property="og:title"]', new MetaContent(title))
        .on('meta[property="og:description"]', new MetaContent(desc))
        .on('meta[property="og:image"]', new MetaContent(image))
        .on('meta[property="og:url"]', new MetaContent(pageUrl))
        .on('meta[property="og:type"]', new MetaContent('article'))
        .on('meta[name="twitter:title"]', new MetaContent(title))
        .on('meta[name="twitter:description"]', new MetaContent(desc))
        .on('meta[name="twitter:image"]', new MetaContent(image))
        .on('link[rel="canonical"]', new LinkHref(pageUrl));

      // Server-side schema.org Event so non-JS crawlers (AI assistants, search
      // bots) get full event facts on this page. og-data rows built before
      // 2026-07-05 have only 3 fields; eventJsonLd returns null for those.
      const ld = eventJsonLd(ev, id);
      if (ld) rewriter.on('head', new HeadAppend(ld));
    }
    // If the id is unknown we still serve the page (with <base> injected) so the
    // human gets a working site; the default site OG tags stay in place.

    const out = rewriter.transform(pageResp);
    return new Response(out.body, {
      status: 200,
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        // preview content changes rarely; safe to cache the assembled page briefly
        'Cache-Control': 'public, max-age=600',
        // Known events are real landing pages (listed in sitemap-events.xml,
        // canonical to themselves, own title/desc/JSON-LD) -> indexable.
        // Unknown ids keep noindex so junk URLs never enter the index.
        'X-Robots-Tag': ev ? 'index, follow' : 'noindex'
      }
    });
  }
};
