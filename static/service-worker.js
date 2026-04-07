/**
 * Service Worker for SHA2 Rehab Coach Mobile App
 * Handles offline support and caching
 */

const CACHE_NAME = 'sha2-rehab-v1';
const ASSETS_TO_CACHE = [
  '/static/styles.css',
  '/static/mobile.css',
  '/static/mobile-app.js',
  '/static/rehab-logo.png',
  '/static/index-mobile.html'
];

// Install event - cache resources
self.addEventListener('install', event => {
  console.log('[Service Worker] Installing...');
  
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log('[Service Worker] Caching assets');
      return cache.addAll(ASSETS_TO_CACHE).catch(err => {
        // Don't fail on individual file errors
        console.warn('[Service Worker] Some assets could not be cached:', err);
        return ASSETS_TO_CACHE.reduce((promise, url) => {
          return promise.then(() =>
            cache.add(url).catch(() => console.warn(`Could not cache ${url}`))
          );
        }, Promise.resolve());
      });
    })
  );
  
  self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  console.log('[Service Worker] Activating...');
  
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('[Service Worker] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  
  self.clients.claim();
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', event => {
  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }
  
  // Skip API calls (let them go through network)
  if (event.request.url.includes('/api/')) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          // Cache successful API responses
          if (response.status === 200) {
            const cache_response = response.clone();
            caches.open(CACHE_NAME).then(cache => {
              cache.put(event.request, cache_response);
            });
          }
          return response;
        })
        .catch(() => {
          // Return offline response for failed API calls
          return caches.match(event.request)
            .then(response => response || new Response('Offline', { status: 503 }));
        })
    );
    return;
  }
  
  // For static assets: cache first strategy
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Return cached version
        if (response) {
          return response;
        }
        
        // Try network
        return fetch(event.request).then(response => {
          // Don't cache non-successful responses
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }
          
          // Clone response to cache it
          const responseToCache = response.clone();
          caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, responseToCache);
          });
          
          return response;
        });
      })
      .catch(() => {
        // Offline fallback
        return caches.match(event.request)
          .then(response => response || new Response('Offline', { status: 503 }));
      })
  );
});

// Handle messages from clients
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

console.log('[Service Worker] Loaded');
