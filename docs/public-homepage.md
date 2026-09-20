# Homepage pubblica e SEO

## Comportamento

- `/` senza query, utente anonimo: landing pubblica. Con sessione attiva resta
  disponibile la precedente area applicativa, senza cambiare endpoint o ruoli.
- `/login`: form di accesso esistente, con nuova presentazione; nessun nuovo
  flusso di registrazione. Tutte le CTA «Prova BasketVision» portano qui.
- `/?game=…`: accesso e selezione della partita esistenti, conservati anche dopo
  login e ricaricamento. Le altre URL applicative mantengono il gate di sessione.
- Copy: tracking, report di rilevamento e revisione video disponibili; eventi
  automatici e statistiche di squadra chiaramente indicati come futuri.
- Visual SVG illustrativo, senza dati utente, numeri di accuratezza o promesse
  di rilevamento perfetto. Nessuna libreria UI, font remoto o immagine stock.

## Build e server frontend

`npm run build` esegue TypeScript, Vite e `scripts/prerender.mjs`.
Il prerender usa lo stesso componente React della pagina pubblica e genera:

- `dist/index.html`: contenuto completo della landing, title, description,
  canonical `https://basketvision.it/`, Open Graph, Twitter summary e JSON-LD
  WebSite/SoftwareApplication. Nessun rating, prezzo o recensione inventati.
- `dist/private.html`: shell applicativa senza contenuti pubblici e con
  `noindex, nofollow`, priva di canonical e JSON-LD pubblico.

Nginx del frontend serve la shell privata per percorsi non statici e querystring,
inclusi login, admin, dashboard, profilo e link alle partite. Aggiunge anche
`X-Robots-Tag: noindex, nofollow`. `/` senza query resta indicizzabile. La sessione
autenticata aggiorna inoltre i metadata a noindex anche sulla root.
Il server statico non conosce l'identità dell'utente: non incorpora mai dati
privati nell'HTML. I dati restano protetti dalle API e dall'autenticazione esistenti.

Le route HTML private sono volutamente accessibili al crawler: bloccarle anche
in robots.txt impedirebbe la lettura del noindex. Gli endpoint API/auth sono
esclusi dal crawling. JS/CSS non sono bloccati.
Riferimento: [Google, noindex e robots.txt](https://developers.google.com/search/docs/crawling-indexing/block-indexing).

Caddy è invariato: continua a gestire HTTPS e i due hostname. Il canonical e la
sitemap preferiscono il dominio non-www; non viene aggiunto un redirect tra
hostname. `/index.html` normalizza alla root preservando la querystring.

## Verifiche locali

La build Docker esegue la build frontend completa. Per una preview isolata
con il backend locale già avviato:

```powershell
docker build -t basketvision-homepage-check ./frontend
docker run -d --name basketvision-homepage-check --network basketvision_default `
  -p 127.0.0.1:5174:80 basketvision-homepage-check
```

Aprire `http://localhost:5174/` in una finestra privata per vedere la landing
senza riutilizzare la sessione locale. Il container è solo una preview locale.

Gli script `scripts/smoke_landing.py` e `scripts/smoke_auth.py` usano Playwright
con Edge. Impostare `BASKETVISION_SMOKE_URL=http://localhost:5174`.
Il primo controlla HTML prerenderizzato, metadata, robots/sitemap, noindex
server/client, tastiera, login fallito, responsive e assenza di errori JavaScript.
Il secondo usa gli account seed locali, senza stampare credenziali: login admin
e Free, sessione sulla root, selezione partita, video, debug, rinnovo e logout.
Non crea né modifica partite o analisi.

Immagini della preview: `storage/diagnostics/homepage/` (ignorate da Git).
Il test responsive copre 360, 390, 768 e 1440 px. Le misure Core Web Vitals
di produzione richiedono una successiva verifica sul deployment e dati reali;
non sono deducibili da una build locale. Il visual ha proporzioni riservate,
il contenuto è statico e non ci sono animazioni o risorse grafiche remote.

## Pubblicazione e Search Console — attività manuali

1. Pubblicare il frontend aggiornato ricostruendo solo il servizio `web`.
   Non occorrono migrazioni DB, nuove API o modifiche ad auth/worker/Caddy.
2. Verificare HTTPS, `/robots.txt`, `/sitemap.xml`, canonical e header noindex
   dei percorsi privati nell'ambiente pubblico.
3. Creare una proprietà Dominio `basketvision.it` in Google Search Console e
   aggiungere al DNS il TXT fornito da Google (nessun token va inventato).
4. Inviare `https://basketvision.it/sitemap.xml` e ispezionare la homepage.
   Non inviare partite, report o URL privati.

Non è stata effettuata alcuna integrazione esterna né pubblicazione automatica.
TODO social: creare un'immagine raster dedicata e aggiungere `og:image`,
`og:image:alt`, dimensioni e `twitter:image`; passare a `summary_large_image`
solo dopo aver pubblicato quell'asset. Attualmente è prevista una card testuale
senza URL immagine inesistente o placeholder.
