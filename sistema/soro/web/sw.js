// Service worker da tela do cidadão. Guarda a página e as últimas respostas da API para
// a tela abrir mesmo sem conexão. Sempre tenta a rede primeiro, porque o estoque muda.
const CACHE = "soro-cidadao-v2";
const PAGINA = ["usuario.html", "perfil.html", "app.css", "app.js", "icone.svg", "manifest.webmanifest"];
const API = ["/api/info", "/api/localidades", "/api/onde-tem-soro"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(PAGINA)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(nomes => Promise.all(nomes.filter(n => n !== CACHE).map(n => caches.delete(n))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  const guardar = PAGINA.some(p => url.pathname.endsWith("/" + p)) || API.some(p => url.pathname === p);
  if (!guardar) return;
  e.respondWith(fetch(e.request).then(r => {
    if (r.ok) {
      const copia = r.clone();
      caches.open(CACHE).then(c => c.put(e.request, copia));
    }
    return r;
  }).catch(() => caches.match(e.request).then(r => r || Response.error())));
});
