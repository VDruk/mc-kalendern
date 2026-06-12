/*
 * MC Kalendern service worker (PWA, 2026-06-12)
 * Strategy:
 *  - Images (/ads/, /clubs/, icons): cache-first. Immutable by naming convention
 *    (a new image always gets a new filename), so serving from cache is safe.
 *  - HTML + JS + data (index.html, events.js, places.js, ...): NETWORK-FIRST.
 *    Online users always get fresh content; the cache is only an offline fallback.
 *  - /api/ (likes worker) and cross-origin (CDN, SMHI, GA): untouched, network only.
 * Bump VERSION to invalidate all old caches on deploy of a new strategy.
 */
const VERSION = 'mck-v1';
const STATIC_CACHE = VERSION + '-static';
const IMG_CACHE = VERSION + '-img';

self.addEventListener('install', function () {
  self.skipWaiting();
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (k) { return k.indexOf(VERSION) !== 0; })
            .map(function (k) { return caches.delete(k); })
      );
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (e) {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  if (url.pathname.indexOf('/api/') === 0) return;

  const isImage = url.pathname.indexOf('/ads/') === 0
    || url.pathname.indexOf('/clubs/') === 0
    || /\.(png|jpg|jpeg|webp|gif|ico|svg)$/i.test(url.pathname);

  if (isImage) {
    e.respondWith(
      caches.open(IMG_CACHE).then(function (cache) {
        return cache.match(req).then(function (hit) {
          if (hit) return hit;
          return fetch(req).then(function (resp) {
            if (resp && resp.ok) cache.put(req, resp.clone());
            return resp;
          });
        });
      })
    );
    return;
  }

  e.respondWith(
    fetch(req).then(function (resp) {
      if (resp && resp.ok) {
        const copy = resp.clone();
        caches.open(STATIC_CACHE).then(function (cache) { cache.put(req, copy); });
      }
      return resp;
    }).catch(function () {
      return caches.match(req).then(function (hit) {
        if (hit) return hit;
        if (req.mode === 'navigate') return caches.match('/index.html');
        return Response.error();
      });
    })
  );
});
