/* Service worker do Contatos Fin.
   Guarda so a pagina de "sem conexao". Nada de dados de contato fica no
   aparelho: todas as paginas continuam vindo do servidor. */
var CACHE = "contatos-offline-v1";
var OFFLINE = "/static/offline.html";

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.add(OFFLINE); }));
  self.skipWaiting();
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (nomes) {
      return Promise.all(nomes.filter(function (n) { return n !== CACHE; }).map(function (n) { return caches.delete(n); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (e) {
  if (e.request.mode !== "navigate") return;
  e.respondWith(
    fetch(e.request).catch(function () { return caches.match(OFFLINE); })
  );
});
