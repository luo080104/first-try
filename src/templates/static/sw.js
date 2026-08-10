// Go购 Service Worker：离线缓存核心资源（PWA）
const CACHE = 'gobuy-v1';
const CORE = ['/', '/static/style.css', '/static/icon-192.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET' || !e.request.url.startsWith('http')) return;
  e.respondWith(
    fetch(e.request).then(resp => {
      const copy = resp.clone();
      if (e.request.url.includes('/static/') || e.request.url.endsWith('/')) {
        caches.open(CACHE).then(c => c.put(e.request, copy));
      }
      return resp;
    }).catch(() => caches.match(e.request).then(m => m || caches.match('/')))
  );
});
