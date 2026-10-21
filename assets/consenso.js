/* Kibo — banner cookie e caricamento condizionato di Google Analytics 4 e del Meta Pixel.
   GA4: proprietà «www.kibotours.com» (G-R4MME0PVZR), la stessa del sito, qui con host go.kibotours.com.
   Meta Pixel «Pixel Kibotours» 501692673520339, lo stesso del sito.
   Eventi browser: page_view/PageView, view_item/ViewContent sulla pagina viaggio, select_content/ClickPrenota
   sul bottone Prenota. Il modulo di prenotazione è su Tally: il lead vero non si conta qui.
   Tutto parte SOLO dopo «Accetta». La scelta vive in localStorage per 365 giorni e si cambia dalla pagina
   /cookie/ (window.kiboConsenso.reset()). Senza consenso la pagina funziona identica e non invia nulla. */
(function () {
  var GA4 = 'G-R4MME0PVZR';
  var PIXEL = '501692673520339';
  var KEY = 'kibo_consenso_tracciamento';
  var GIORNI = 365;
  var T = {
    testo: 'Usiamo Google Analytics e il pixel Meta per capire da dove arrivano le visite a questa pagina e per mostrarti annunci Kibo pertinenti. Nessun altro tracciamento.',
    info: 'Informativa cookie', ok: 'Accetta', no: 'Rifiuta', infoUrl: '/cookie/'
  };

  function leggi() {
    try {
      var v = JSON.parse(localStorage.getItem(KEY) || 'null');
      if (!v || !v.t || Date.now() - v.t > GIORNI * 864e5) return null;
      return v.scelta;
    } catch (e) { return null; }
  }
  function scrivi(scelta) {
    try { localStorage.setItem(KEY, JSON.stringify({ scelta: scelta, t: Date.now() })); } catch (e) {}
  }
  function slug() {
    var m = location.pathname.match(/\/(viaggi|anteprima)\/([^\/]+)/);
    return m ? m[2] : location.pathname;
  }
  function viaggio() { return /\/(viaggi|anteprima)\/[^\/]+/.test(location.pathname); }
  function titolo() { return (document.title || '').replace(/\s*·\s*Kibo\s*$/, ''); }

  function caricaGA4() {
    if (window.kiboGA4) return;
    window.kiboGA4 = true;
    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function () { window.dataLayer.push(arguments); };
    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA4;
    document.head.appendChild(s);
    gtag('js', new Date());
    gtag('config', GA4, { anonymize_ip: true });
    if (viaggio()) gtag('event', 'view_item', { items: [{ item_id: slug(), item_name: titolo() }] });
  }
  function caricaPixel() {
    if (window.fbq) return;
    !function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
    fbq('init', PIXEL);
    fbq('track', 'PageView');
    if (viaggio()) fbq('track', 'ViewContent', { content_name: slug(), content_type: 'product' });
  }
  function agganciaCta() {
    if (window.kiboCtaAgganciate) return;
    window.kiboCtaAgganciate = true;
    var nome = slug();
    document.querySelectorAll('a.cta').forEach(function (a) {
      a.addEventListener('click', function () {
        try { if (window.gtag) gtag('event', 'select_content', { content_type: 'cta_prenota', item_id: nome }); } catch (e) {}
        try { if (window.fbq) fbq('trackCustom', 'ClickPrenota', { content_name: nome }); } catch (e) {}
      });
    });
  }
  function carica() { caricaGA4(); caricaPixel(); agganciaCta(); }

  function stile() {
    if (document.getElementById('kibo-cookie-css')) return;
    var s = document.createElement('style');
    s.id = 'kibo-cookie-css';
    s.textContent =
      '#kibo-cookie{position:fixed;left:0.75rem;right:0.75rem;bottom:4.5rem;z-index:50;max-width:36rem;margin:0 auto;' +
      'background:#FDFDFC;color:#24404A;border:1px solid #DCE6EA;border-radius:12px;box-shadow:0 8px 28px rgba(0,0,0,.18);' +
      'padding:0.9rem 1rem;font:400 0.875rem/1.45 "Montserrat","Segoe UI",system-ui,sans-serif}' +
      '@media(min-width:940px){#kibo-cookie{bottom:1rem;left:1rem;right:auto}}' +
      '#kibo-cookie p{margin:0 0 0.7rem}' +
      '#kibo-cookie a{color:#265A63}' +
      '#kibo-cookie .azioni{display:flex;gap:0.5rem;align-items:center;flex-wrap:wrap}' +
      '#kibo-cookie button{font:inherit;font-weight:600;border-radius:8px;padding:0.5rem 1rem;cursor:pointer;border:1px solid #265A63;background:#fff;color:#265A63}' +
      '#kibo-cookie button.ok{background:#027ABB;border-color:#027ABB;color:#fff}' +
      '#kibo-cookie button:focus-visible{outline:3px solid #265A63;outline-offset:2px}';
    document.head.appendChild(s);
  }
  function mostraBanner() {
    if (document.getElementById('kibo-cookie')) return;
    stile();
    var d = document.createElement('div');
    d.id = 'kibo-cookie';
    d.setAttribute('role', 'dialog');
    d.setAttribute('aria-label', T.info);
    d.innerHTML = '<p>' + T.testo + ' <a href="' + T.infoUrl + '">' + T.info + '</a></p>' +
      '<div class="azioni"><button type="button" class="ok">' + T.ok + '</button>' +
      '<button type="button" class="no">' + T.no + '</button></div>';
    d.querySelector('.ok').addEventListener('click', function () { scrivi('si'); d.remove(); carica(); });
    d.querySelector('.no').addEventListener('click', function () { scrivi('no'); d.remove(); });
    document.body.appendChild(d);
  }
  function avvia() {
    var scelta = leggi();
    if (scelta === 'si') carica();
    else if (scelta !== 'no') mostraBanner();
  }
  window.kiboConsenso = {
    stato: leggi,
    reset: function () { try { localStorage.removeItem(KEY); } catch (e) {} mostraBanner(); }
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', avvia);
  else avvia();
})();
