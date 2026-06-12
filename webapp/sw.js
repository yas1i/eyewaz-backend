/* EYEWAZ service worker — installable PWA + offline app shell.
   Bump CACHE when you ship new assets so clients update. */
const CACHE = "eyewaz-v2";
const SHELL = [
  "/app",
  "/app/",
  "/app/app.js",
  "/app/styles.css",
  "/app/manifest.webmanifest",
  "/app/assets/eyewaz-logo.png",
  "/app/assets/eyewaz-favicon.png",
  "/app/assets/icon-192.png",
  "/app/assets/icon-512.png",
  "/app/assets/icon-maskable-512.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;                       // never cache POST/PUT/etc.
  const url = new URL(req.url);

  // Live data must never be cached.
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/files/")) return;

  // App-shell assets: cache-first, then network (works offline).
  if (url.origin === location.origin && url.pathname.startsWith("/app")) {
    e.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      }).catch(() => caches.match("/app")))   // offline fallback to the app shell
    );
    return;
  }
  // Everything else (fonts, etc.): network, falling back to cache if present.
  e.respondWith(fetch(req).catch(() => caches.match(req)));
});
