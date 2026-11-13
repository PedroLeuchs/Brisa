const CACHE = 'brisa-shell-v2';
const SHELL = ['/', '/assets/style.css', '/assets/app.js', '/assets/icon.svg', '/assets/manifest.webmanifest'];
self.addEventListener('install', event => { event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL))); self.skipWaiting(); });
self.addEventListener('activate', event => event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim())));
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
  if (SHELL.includes(url.pathname)) event.respondWith(fetch(event.request).catch(() => caches.match(event.request)));
});
