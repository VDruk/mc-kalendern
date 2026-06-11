/*
 * MC Kalendern - anonymous likes ("Intresserad") backend
 * Cloudflare Worker + D1. Route: druk.se/api/*
 *
 * GET  /api/counts -> {"event-id": n, ...}  (edge-cached 60s)
 * POST /api/like   {"id": "...", "action": "like"|"unlike"} -> {"n": newCount}
 *
 * Anti-abuse: per-IP daily limits (hashed IPs only, GDPR-friendly).
 * Counts are a soft social signal, not an exact tally.
 */

const ALLOWED_ORIGINS = ['https://druk.se', 'https://www.druk.se', 'http://localhost', 'http://127.0.0.1'];
const ID_RE = /^[a-z0-9åäöé.\-]{3,90}$/;
const MAX_PER_EVENT_PER_DAY = 6;   // like/unlike toggles on one event per IP per day
const MAX_TOTAL_PER_DAY = 80;      // total actions per IP per day

function corsHeaders(req) {
  const origin = req.headers.get('Origin') || '';
  const ok = ALLOWED_ORIGINS.some(o => origin === o || origin.startsWith(o + ':'));
  return {
    'Access-Control-Allow-Origin': ok ? origin : 'https://druk.se',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Vary': 'Origin'
  };
}

function json(data, status, extra, req) {
  return new Response(JSON.stringify(data), {
    status: status || 200,
    headers: { 'Content-Type': 'application/json; charset=utf-8', ...corsHeaders(req), ...(extra || {}) }
  });
}

async function sha256hex(s) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
}

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    const path = url.pathname.replace(/^\/api/, '');

    if (req.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders(req) });
    }

    if (path === '/counts' && req.method === 'GET') {
      // edge cache 60s so 10k visitors do not mean 10k D1 reads
      const cacheKey = new Request(url.origin + '/api/counts');
      const cached = await caches.default.match(cacheKey);
      if (cached) {
        const r = new Response(cached.body, cached);
        Object.entries(corsHeaders(req)).forEach(([k, v]) => r.headers.set(k, v));
        return r;
      }
      const { results } = await env.DB.prepare('SELECT event_id, n FROM counts WHERE n > 0').all();
      const out = {};
      for (const row of results) out[row.event_id] = row.n;
      const resp = json(out, 200, { 'Cache-Control': 'public, max-age=60' }, req);
      ctx.waitUntil(caches.default.put(cacheKey, resp.clone()));
      return resp;
    }

    if (path === '/like' && req.method === 'POST') {
      let body;
      try { body = await req.json(); } catch { return json({ error: 'bad json' }, 400, null, req); }
      const id = String(body.id || '').toLowerCase();
      const action = body.action === 'unlike' ? 'unlike' : 'like';
      if (!ID_RE.test(id)) return json({ error: 'bad id' }, 400, null, req);

      const ip = req.headers.get('CF-Connecting-IP') || '0.0.0.0';
      const day = new Date().toISOString().slice(0, 10);
      const ipHash = (await sha256hex((env.LIKE_SALT || 'mc-salt') + ip)).slice(0, 32);

      // rate limits: increment-and-check, per event and total ('*')
      const rlEvent = await env.DB.prepare(
        `INSERT INTO rl(ip_hash, event_id, day, c) VALUES(?, ?, ?, 1)
         ON CONFLICT(ip_hash, event_id, day) DO UPDATE SET c = c + 1
         RETURNING c`).bind(ipHash, id, day).first();
      const rlTotal = await env.DB.prepare(
        `INSERT INTO rl(ip_hash, event_id, day, c) VALUES(?, '*', ?, 1)
         ON CONFLICT(ip_hash, event_id, day) DO UPDATE SET c = c + 1
         RETURNING c`).bind(ipHash, day).first();
      if ((rlEvent && rlEvent.c > MAX_PER_EVENT_PER_DAY) || (rlTotal && rlTotal.c > MAX_TOTAL_PER_DAY)) {
        return json({ error: 'rate limited' }, 429, null, req);
      }

      let row;
      if (action === 'like') {
        row = await env.DB.prepare(
          `INSERT INTO counts(event_id, n) VALUES(?, 1)
           ON CONFLICT(event_id) DO UPDATE SET n = n + 1
           RETURNING n`).bind(id).first();
      } else {
        await env.DB.prepare(
          `UPDATE counts SET n = MAX(n - 1, 0) WHERE event_id = ?`).bind(id).run();
        row = await env.DB.prepare(`SELECT n FROM counts WHERE event_id = ?`).bind(id).first();
      }

      // occasional cleanup of old rate-limit rows (about 1% of requests)
      if (Math.random() < 0.01) {
        ctx.waitUntil(env.DB.prepare(`DELETE FROM rl WHERE day < date('now', '-2 day')`).run());
      }

      return json({ n: (row && row.n) || 0 }, 200, null, req);
    }

    return json({ error: 'not found' }, 404, null, req);
  }
};
