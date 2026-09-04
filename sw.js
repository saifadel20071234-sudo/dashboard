const CACHE_NAME = 'powerstep-cache-v2';

// عند التثبيت — امسح أي cache قديم
self.addEventListener('install', event => {
  self.skipWaiting();
});

// عند التفعيل — امسح الكاش القديم
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      );
    })
  );
  self.clients.claim();
});

// دايماً جيب النسخة الجديدة من السيرفر (Network First)
self.addEventListener('fetch', event => {
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
