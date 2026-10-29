import React,{useState} from 'react';
import {API,apiFetch,errorMessage} from './auth';

export type ReviewEvent={id:string,type:string,team?:string,teamId?:string|null,analysisJobId:string,videoTimestamp:number,confidence:number,status:string,shotValue?:number|null};
export const eventLabels:Record<string,string>={ShotCandidate:'Candidato di tiro',ShotMade:'Tiro segnato',ShotMissed:'Tiro sbagliato',FreeThrowMade:'Libero segnato',FreeThrowMissed:'Libero sbagliato',OffensiveRebound:'Rimbalzo offensivo',DefensiveRebound:'Rimbalzo difensivo',Turnover:'Palla persa',Steal:'Palla recuperata',Assist:'Assist',Block:'Stoppata',Foul:'Fallo',TechnicalFoul:'Fallo tecnico',Violation:'Violazione',JumpBall:'Palla a due',PeriodStart:'Inizio periodo',PeriodEnd:'Fine periodo',Timeout:'Timeout'};
type ReviewFilter='all'|'pending'|'confirmed'|'rejected';
function reviewGroup(ev:ReviewEvent):ReviewFilter{return ev.status==='Rejected'?'rejected':ev.status==='Confirmed'||ev.status==='Corrected'?'confirmed':'pending'}
const filterLabels:Record<ReviewFilter,string>={all:'Tutti',pending:'Da revisionare',confirmed:'Confermati',rejected:'Scartati'};
export function ShotReview({gameId,teams,events,analysisId,currentTime,seek,reload}:{gameId:string,teams:{id:string,name:string}[],events:ReviewEvent[],analysisId?:string,currentTime:()=>number,seek:(t:number)=>void,reload:()=>Promise<void>}){
 const [editing,setEditing]=useState<ReviewEvent|null>(null);
 const [open,setOpen]=useState(false);
 const [timestamp,setTimestamp]=useState(0);
 const [team,setTeam]=useState('');
 const [outcome,setOutcome]=useState('ShotMade');
 const [shotValue,setShotValue]=useState('');
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 const [filter,setFilter]=useState<ReviewFilter>('all');
 const [notice,setNotice]=useState('');
 const [refreshFailed,setRefreshFailed]=useState(false);
 const shots=events.filter(e=>['ShotCandidate','ShotMade','ShotMissed'].includes(e.type));
 const visibleShots=shots.filter(ev=>filter==='all'||reviewGroup(ev)===filter).sort((a,b)=>a.videoTimestamp-b.videoTimestamp);
 function edit(ev?:ReviewEvent){if(ev)seek(ev.videoTimestamp);setShotValue(ev?ev.shotValue==null?'':String(ev.shotValue):shotValue||'2');setEditing(ev??null);setTimestamp(ev?.videoTimestamp??Math.round(currentTime()*100)/100);setTeam(ev?.teamId??team);setOutcome(ev?.type==='ShotMissed'?'ShotMissed':'ShotMade');setError('');setNotice('');setOpen(true)}
 async function refresh(){try{await reload();setRefreshFailed(false)}catch{setRefreshFailed(true)}}
 async function save(reject=false){
   const jobId=editing?.analysisJobId??analysisId;
   if(!jobId||busy)return;
   setBusy(true);setError('');
   try{
     const r=await apiFetch(`${API}/api/games/${gameId}/shots${editing?`/${editing.id}`:''}`,{method:editing?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({analysisJobId:jobId,teamId:team||null,videoTimestamp:timestamp,shotValue:shotValue?Number(shotValue):null,type:reject?(editing?.type??outcome):outcome,status:reject?'Rejected':editing?'Corrected':'Confirmed'})});
     if(!r.ok){setError(await errorMessage(r));return}
     setOpen(false);setNotice(reject?'Tiro scartato.':editing?'Tiro aggiornato.':'Tiro registrato.');
     await refresh();
   }catch{setError('Salvataggio non riuscito. Riprova.')}finally{setBusy(false)}
 }
 return <section className="card shot-review"><h2>Registra e rivedi i tiri</h2><p>Porta il video sul tiro, poi indica squadra, valore ed esito. Solo i tiri confermati contribuiscono alle statistiche.</p><button className="primary" disabled={!analysisId||busy||open||refreshFailed} onClick={()=>edit()}>Aggiungi tiro dalla posizione del video</button>{!analysisId&&<p>Apri la revisione assistita oppure attendi il completamento dell’analisi selezionata.</p>}
 {notice&&<p role="status">{notice}</p>}{refreshFailed&&<p role="alert">Il tiro è salvato, ma il report non è aggiornato. <button disabled={busy} onClick={refresh}>Ricarica report</button></p>}
 {open&&<form onSubmit={e=>{e.preventDefault();if(!busy)save()}}><fieldset disabled={busy}><label>Secondi video<input type="number" min="0" step="0.01" required value={timestamp} onChange={e=>setTimestamp(Number(e.target.value))}/></label><button type="button" onClick={()=>setTimestamp(Math.round(currentTime()*100)/100)}>Usa posizione video</button><label>Squadra<select value={team} required onChange={e=>setTeam(e.target.value)}><option value="">Seleziona squadra</option>{teams.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}</select></label><label>Tipo di tiro<select value={shotValue} onChange={e=>setShotValue(e.target.value)}><option value="">Da specificare</option><option value="2">Da 2 punti</option><option value="3">Da 3 punti</option><option value="1">Libero</option></select></label><label>Esito<select value={outcome} onChange={e=>setOutcome(e.target.value)}><option value="ShotMade">Segnato</option><option value="ShotMissed">Sbagliato</option></select></label><button disabled={busy}>Salva tiro</button>{editing&&<button type="button" disabled={busy} onClick={()=>save(true)}>Scarta tiro</button>}<button type="button" disabled={busy} onClick={()=>setOpen(false)}>Annulla</button>{error&&<p role="alert">{error}</p>}</fieldset></form>}
 <div className="actions" role="group" aria-label="Filtra tiri per stato">{(Object.keys(filterLabels) as ReviewFilter[]).map(value=><button type="button" key={value} aria-pressed={filter===value} onClick={()=>setFilter(value)}>{filterLabels[value]} ({value==='all'?shots.length:shots.filter(ev=>reviewGroup(ev)===value).length})</button>)}</div>
 <div className="events">{visibleShots.length===0&&<p role="status">{shots.length===0?'Nessun tiro presente. Aggiungi un tiro dal video per iniziare.':'Nessun tiro in questo filtro.'}</p>}{visibleShots.map(ev=><div key={ev.id}><button onClick={()=>seek(ev.videoTimestamp)}>{ev.videoTimestamp.toFixed(2)}s · {ev.team??'Da attribuire'} · {eventLabels[ev.type]??ev.type} · {ev.shotValue==null?'Valore da specificare':ev.shotValue===1?'Libero':`Da ${ev.shotValue} punti`} · {ev.status==='Rejected'?'Scartato':ev.status==='Corrected'?'Confermato e corretto':ev.status==='Confirmed'?'Confermato':'Da revisionare'}</button> <button disabled={busy||refreshFailed||open} onClick={()=>edit(ev)}>Rivedi</button></div>)}</div></section>
}
