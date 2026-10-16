const CACHE_NAME = 'cacao-accounting-v5';
const STATIC_ASSETS = [
  '/static/css/cacaoaccounting.css',
  '/static/manifest.json',
  '/static/media/brand.svg',
  '/static/media/brand-dark.svg',
  '/static/media/brand-mark.svg'
];

async function precacheStaticAssets() {
  const cache = await caches.open(CACHE_NAME);
  await cache.addAll(STATIC_ASSETS).catch(() => {
    // Suppress failure for non-critical assets during install
  });
}

self.addEventListener('install', (event) => {
  event.waitUntil(precacheStaticAssets());
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') {
    return;
  }
  const url = new URL(event.request.url);

  // Network-first for html/dynamic requests, cache-first for static assets
  if (url.origin === self.location.origin && url.pathname.startsWith('/static/')) {
    event.respondWith(cacheFirstWithRefresh(event.request));
  } else {
    event.respondWith(networkFirstWithCacheFallback(event.request));
  }
});

async function cacheFirstWithRefresh(request) {
  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    void refreshCachedAsset(request);
    return cachedResponse;
  }
  return fetch(request);
}

async function refreshCachedAsset(request) {
  try {
    const networkResponse = await fetch(request);
    if (networkResponse?.status === 200) {
      const cache = await caches.open(CACHE_NAME);
      await cache.put(request, networkResponse);
    }
  } catch (_) {
    // Best-effort background refresh; the cached response is already served.
  }
}

async function networkFirstWithCacheFallback(request) {
  try {
    return await fetch(request);
  } catch (_) {
    return caches.match(request);
  }
}
