import React from 'react';

export function Brand(){
  return <a className="bv-brand" href="/" aria-label="BasketVision, homepage"><svg viewBox="0 0 32 32" width="30" height="30" aria-hidden="true"><rect width="32" height="32" rx="9" fill="currentColor"/><circle cx="16" cy="16" r="10" fill="none" stroke="#fff" strokeWidth="1.4"/><path d="M6 16h20M16 6v20M9 9c9 4 9 10 14 14M23 9C14 13 14 19 9 23" fill="none" stroke="#fff" strokeWidth="1.2"/></svg><span>Basket<span className="bv-brand-light">Vision</span></span></a>;
}

function CourtVisual(){
  const players = [{x:210,y:155,a:true},{x:345,y:119,a:false},{x:416,y:240,a:true},{x:274,y:292,a:false},{x:528,y:175,a:false},{x:560,y:305,a:true}];
  return <figure className="bv-visual" aria-labelledby="visual-caption">
    <div className="bv-visual-top"><span><i/> VISION / ANALISI VIDEO</span><span>01 — CAMPO</span></div>
    <svg className="bv-court" viewBox="0 0 760 440" role="img" aria-label="Schema illustrativo di un campo da basket con posizioni dei giocatori, riquadri di rilevamento e traiettoria della palla">
      <defs><pattern id="court-grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="#273638" strokeWidth=".6"/></pattern></defs>
      <rect width="760" height="440" fill="url(#court-grid)"/>
      <g fill="none" stroke="#687777" strokeWidth="1.3"><rect x="65" y="60" width="630" height="320" rx="3"/><path d="M380 60v320"/><circle cx="380" cy="220" r="51"/><path d="M65 147h110v146H65M695 147H585v146h110M65 78h35a159 159 0 0 1 0 284H65M695 78h-35a159 159 0 0 0 0 284h35"/><circle cx="175" cy="220" r="42"/><circle cx="585" cy="220" r="42"/><path d="M89 197v46M671 197v46"/><circle cx="100" cy="220" r="8"/><circle cx="660" cy="220" r="8"/></g>
      <path d="M305 250Q336 200 375 185T480 180" fill="none" stroke="#efa16d" strokeWidth="2" strokeDasharray="5 7"/>
      {[305,329,356,387,418].map((x,i)=><circle key={x} cx={x} cy={250-i*17} r="3" fill="#efa16d" opacity={.25+i*.15}/>)}
      {players.map((p,i)=><g key={i} transform={`translate(${p.x} ${p.y})`}><rect x="-20" y="-26" width="40" height="53" rx="3" fill={p.a?'#bade8f10':'#9dcbd010'} stroke={p.a?'#c3e5a4':'#9dcbd0'} strokeWidth="1.3"/><circle cy="-7" r="6" fill={p.a?'#c3e5a4':'#9dcbd0'}/><path d="M-9 17v-7a9 9 0 0 1 18 0v7" fill={p.a?'#c3e5a4':'#9dcbd0'}/><text x="-19" y="-33" fill={p.a?'#c3e5a4':'#9dcbd0'} fontSize="10" fontFamily="monospace">ID {String(i+1).padStart(2,'0')}</text></g>)}
      <g transform="translate(480 180)"><rect x="-15" y="-15" width="30" height="30" rx="3" fill="none" stroke="#ff935e"/><circle r="7" fill="#ff935e"/><path d="M-6 0H6M0-6V6" stroke="#192628"/><path d="M16-8l35-25h55" fill="none" stroke="#ff935e"/><text x="57" y="-39" fill="#ffb991" fontSize="11" fontFamily="monospace">PALLA</text></g>
      <text x="65" y="413" fill="#a8b8b7" fontSize="10" fontFamily="monospace">TRACKING VIEW</text><text x="695" y="413" textAnchor="end" fill="#a8b8b7" fontSize="10" fontFamily="monospace">00:08 / 00:20</text>
    </svg>
    <div className="bv-timeline" aria-hidden="true"><span>00:00</span><div>{Array.from({length:38},(_,i)=><i key={i} style={{height:`${8+(i*17%23)}px`}}/>)}<b/></div><span>00:20</span></div>
    <div className="bv-visual-bottom"><span><b>01</b> Video caricato</span><span><b>02</b> Tracking</span><span><b>03</b> Report</span></div>
    <figcaption id="visual-caption">Visualizzazione illustrativa del tracking. Non è un risultato di analisi.</figcaption>
  </figure>;
}

const steps = [
  ['01','Carica il video','Parti dalla tua partita. Carica un file video e imposta Team A e Team B.','VIDEO →'],
  ['02','Scegli cosa analizzare','Seleziona un intervallo e avvia l’analisi automatica. Puoi metterla in pausa e riprenderla.','→ VISION →'],
  ['03','Esplora il report','Consulta tracking e statistiche di rilevamento. Seleziona una detection per tornare al punto del video.','→ INSIGHT'],
];

export function LandingPage(){
  return <div className="bv-landing">
    <a className="bv-skip" href="#contenuto">Vai al contenuto</a>
    <header className="bv-header"><Brand/><nav aria-label="Navigazione principale"><a className="bv-nav-section" href="#come-funziona">Come funziona</a><a className="bv-nav-section" href="#funzionalita">Il prodotto</a><a href="/login">Accedi</a><a className="bv-button bv-button-dark" href="/login">Prova BasketVision <span aria-hidden="true">↗</span></a></nav></header>
    <main id="contenuto" className="bv-main">
      <section className="bv-hero" aria-labelledby="hero-title">
        <div className="bv-hero-copy"><p className="bv-eyebrow"><span/> COMPUTER VISION, DENTRO IL GIOCO</p><h1 id="hero-title">La tua partita.<br/>Una nuova<br/><em>visione.</em></h1><p className="bv-intro">Trasforma il video di basket in dati da esplorare. BasketVision rileva persone e palla con l’AI e ti riporta ai momenti da rivedere.</p><div className="bv-hero-actions"><a className="bv-button bv-button-orange" href="/login">Prova BasketVision <span aria-hidden="true">↗</span></a><a className="bv-text-link" href="#come-funziona">Scopri come funziona <span aria-hidden="true">↓</span></a></div><p className="bv-access-note">Accesso con account · Analisi da file video</p></div>
        <div className="bv-hero-media"><div className="bv-media-label"><span>DAL VIDEO AL DATO</span><span>COMPUTER VISION / BASKETBALL</span></div><CourtVisual/><div className="bv-media-note"><span className="bv-note-mark" aria-hidden="true">⌁</span><p>Segui l’azione.<br/><strong>Rivedi quello che conta.</strong></p><span className="bv-pill">Tracking in sviluppo</span></div></div>
      </section>
      <div className="bv-strip" aria-label="Percorso di analisi"><span>IL CAMPO È IL PUNTO DI PARTENZA.</span><p>Video <b aria-hidden="true">↗</b> Analisi automatica <b aria-hidden="true">↗</b> Report di tracking</p></div>
      <section id="come-funziona" className="bv-section" aria-labelledby="steps-title"><div className="bv-section-heading"><p className="bv-eyebrow">SEMPLICE, DAL PRIMO FRAME</p><h2 id="steps-title">Tu porta la partita.<br/>Al video pensiamo noi.</h2><p>Un percorso unico, dal caricamento alla revisione dell’analisi.</p></div><div className="bv-steps">{steps.map(([n,title,description,graphic])=><article key={n}><div className="bv-step-top"><span>{n}</span><span aria-hidden="true">{graphic}</span></div><h3>{title}</h3><p>{description}</p></article>)}</div></section>
      <section id="funzionalita" className="bv-section bv-features" aria-labelledby="features-title"><div className="bv-section-heading"><p className="bv-eyebrow">GUARDA OLTRE IL PUNTEGGIO</p><h2 id="features-title">Più contesto.<br/>Frame dopo frame.</h2><p>Strumenti concreti per esplorare l’analisi video basket. Con una distinzione chiara tra ciò che puoi usare oggi e quello che arriverà.</p></div><div className="bv-feature-grid">
        <article className="bv-feature-primary"><div className="bv-feature-icon" aria-hidden="true">[ · ]</div><span className="bv-label">COMPUTER VISION</span><h3>Persone e palla,<br/>nel contesto del gioco.</h3><p>Rilevamento e tracking automatici, con campioni annotati e livelli di confidenza per verificare i risultati.</p><div className="bv-feature-foot"><span className="bv-status-dot"/> Disponibile · Rilevamento palla in affinamento</div></article>
        <article><span className="bv-feature-number">01 / CONTROLLO</span><h3>Il tuo intervallo.<br/>Il tuo ritmo.</h3><p>Analizza una porzione del video. Segui l’avanzamento e gestisci pausa e ripresa dell’elaborazione.</p></article>
        <article><span className="bv-feature-number">02 / REVISIONE</span><h3>Dal dato<br/>al video.</h3><p>Esplora il report video, le statistiche di rilevamento e i campioni di tracking. Clicca una detection per rivederla.</p></article>
        <article className="bv-roadmap"><span className="bv-pill">Prossimamente</span><h3>Eventi e statistiche<br/>di squadra.</h3><p>Il prossimo passo: rilevare automaticamente gli eventi basket e alimentare le statistiche Team A / Team B. Questa analisi non è ancora disponibile.</p></article>
      </div></section>
      <section className="bv-final" aria-labelledby="final-title"><div><p className="bv-eyebrow">LA PROSSIMA PARTITA, DA UN’ALTRA PROSPETTIVA</p><h2 id="final-title">Il video è solo l’inizio.</h2><p>Accedi a BasketVision e inizia a esplorare la tua partita.</p></div><div><a className="bv-button bv-button-orange" href="/login">Prova BasketVision <span aria-hidden="true">↗</span></a><span>Hai già un account? <a href="/login">Accedi</a></span></div></section>
    </main>
    <footer className="bv-footer"><Brand/><p>Computer vision per il basket.</p><a href="/login">Accedi alla tua area <span aria-hidden="true">↗</span></a></footer>
  </div>;
}
