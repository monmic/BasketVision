import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';
import {AdminDashboard} from './AdminDashboard';

import {API, apiFetch as fetch, Session, AccountPanel, errorMessage, type Me} from './auth';
type Game = {id:string,name:string,teams:{id:string,name:string,side:string}[],videoPath?:string};
type Report = {gameId:string,gameName:string,teams:{teamId:string,teamName:string,stats:Record<string,number>}[],events:{id:string,type:string,team?:string,videoTimestamp:number,confidence:number,status:string}[]};
type AnalysisStatus = 'Pending'|'Processing'|'Completed'|'Failed'|'Paused';
type AnalysisJob = {analysisId:string,gameId:string,status:AnalysisStatus,progress:number,error?:string|null,startSeconds?:number,endSeconds?:number|null};
type ActiveAnalysis = AnalysisJob & {gameName:string,createdAtUtc:string};
type BallPoint = {timestamp:number,trackId?:number|null,trackState?:'tentative'|'confirmed'|'lost',confidence:number,qualityScore?:number,acceptedScore?:number,acceptanceReason?:string,rejectionReason?:string,associationType?:string,source?:string,x1:number,y1:number,x2:number,y2:number,centerX:number,centerY:number,width?:number,height?:number};
type DebugFrame = {fileName:string,timestamp:number,rawCandidates:number,acceptedDetections:number,rejectedCandidates:number};
type PersonConfidenceBuckets = {belowTrackLow025:number,trackLow025To060:number,trackHigh060To070:number,newTrack070Plus:number};
type VisionResult = {
 analysisId:string;
 gameId:string;
 mode:string;
 model:string;
 ballModel?:string;
 config?:{personFrameStride?:number,personConfidence?:number,personImgsz?:number,personTracker?:string,personTrackerThresholds?:{trackLow:number,trackHigh:number,newTrack:number,gmcMethod:string},ballFrameStride?:number,ballConfidence?:number,ballImgsz?:number,ballUseTiles?:boolean,ballTileStride?:number,ballTileImgsz?:number,ballTrackMinHits?:number,ballAcceptedMinScore?:number,ballTrackUpdateMinScore?:number,ballTrackNewMinScore?:number,ballTrackNewMinConfidence?:number,ballDebugExport?:boolean};
 video:{fps:number,totalFrames:number,width:number,height:number,durationSeconds:number,analysisStartSeconds?:number,analysisEndSeconds?:number|null,analysisDurationSeconds?:number|null,frameStride:number,processedFrames:number,processedPersonFrames?:number,processedBallFrames?:number};
 summary:{personDetections:number,personTrackedDetections?:number,personUntrackedDetections?:number,personTrackCreations?:number,personTrackAssociations?:number,personFramesWithTracks?:number,personHighConfidenceWithId?:number,personHighConfidenceWithoutId?:number,averagePersonConfidence?:number,medianPersonConfidence?:number,personConfidenceBuckets?:PersonConfidenceBuckets,ballDetections:number,rawBallCandidates?:number,acceptedBallDetections?:number,rejectedBallCandidates?:number,ballAcceptanceReasons?:Record<string,number>,ballRejectionReasons?:Record<string,number>,ballTracksCreated?:number,ballWeakTrackUpdates?:number,fullBallDetections?:number,tiledBallDetections?:number,framesWithBall:number,maxPersonsInFrame:number,uniquePersonTracks:number,uniqueBallTracks:number,confirmedBallTracks?:number,validBallTracks?:number,averageBallConfidence?:number,medianBallConfidence?:number,ballDetectionsPerSecond?:number,storedBallPoints:number};
 ballTrack:BallPoint[];
 debugFrames?:DebugFrame[];
};

function App({me,reloadMe,logout}:{me:Me,reloadMe:()=>Promise<void>,logout:()=>Promise<void>}){
 const [games,setGames]=useState<Game[]>([]);
 const [game,setGame]=useState<Game|null>(null);
 const [report,setReport]=useState<Report|null>(null);
 const [job,setJob]=useState<AnalysisJob|null>(null);
 const [activeAnalyses,setActiveAnalyses]=useState<ActiveAnalysis[]>([]);
 const [vision,setVision]=useState<VisionResult|null>(null);
 const [selectedFile,setSelectedFile]=useState<File|null>(null);
 const [uploading,setUploading]=useState(false);
 const [rangeStart,setRangeStart]=useState('00:00:00');
 const [rangeEnd,setRangeEnd]=useState('');
 const video=useRef<HTMLVideoElement>(null);

 const loadGames=async()=>{
   const list:Game[]=await fetch(`${API}/api/games`).then(r=>r.json());
   setGames(list);
   return list;
 };

 const loadActiveAnalyses=async()=>{
   try{
     const r=await fetch(`${API}/api/analysis/active`);
     if(r.ok) setActiveAnalyses(await r.json());
   }catch{
     // Keep the last known state if the API is temporarily unavailable.
   }
 };

 async function selectGame(id:string, updateUrl=true){
   if(!id){
     setGame(null); setReport(null); setJob(null); setVision(null);
     if(updateUrl) history.replaceState(null,'',location.pathname);
     return;
   }
   const r=await fetch(`${API}/api/games/${id}`);
   if(!r.ok) return;
   const g:Game=await r.json();
   setGame(g);
   setVision(null);
   if(updateUrl) history.replaceState(null,'',`${location.pathname}?game=${g.id}`);

   const jr=await fetch(`${API}/api/games/${g.id}/analysis/latest`);
   setJob(jr.ok ? await jr.json() : null);
 }

 useEffect(()=>{
   (async()=>{
     await loadGames();
     await loadActiveAnalyses();
     const gameId=new URLSearchParams(location.search).get('game');
     if(gameId) await selectGame(gameId,false);
   })();
 },[]);

 useEffect(()=>{
   const t=setInterval(loadActiveAnalyses,3000);
   return()=>clearInterval(t);
 },[]);

 useEffect(()=>{
   if(!game) return;
   fetch(`${API}/api/games/${game.id}/report`)
     .then(r=>r.ok?r.json():null)
     .then(setReport);
 },[game?.id,job?.progress,job?.status]);

 useEffect(()=>{
   if(!job?.analysisId || job.status==='Completed' || job.status==='Failed') return;
   const t=setInterval(async()=>{
     const r=await fetch(`${API}/api/analysis/${job.analysisId}`);
     if(r.ok){
       const updated:AnalysisJob=await r.json();
       setJob(updated);
       if(updated.status==='Completed'||updated.status==='Failed') loadActiveAnalyses();
     }
   },1000);
   return()=>clearInterval(t);
 },[job?.analysisId,job?.status]);

 useEffect(()=>{
   if(!job?.analysisId || job.status!=='Completed') return;
   reloadMe().catch(()=>{});
   fetch(`${API}/api/analysis/${job.analysisId}/vision`)
     .then(r=>r.ok?r.json():null)
     .then(setVision)
     .catch(()=>setVision(null));
 },[job?.analysisId,job?.status]);

 async function createGame(e:React.FormEvent<HTMLFormElement>){
   e.preventDefault();
   const f=new FormData(e.currentTarget);
   const body={name:f.get('name'),teamAName:f.get('a'),teamBName:f.get('b')};
   const r=await fetch(`${API}/api/games`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
   if(!r.ok){alert(await errorMessage(r));return;}
   const x=await r.json();
   await loadGames();
   await selectGame(x.id);
 }

 async function upload(){
   if(!game || !selectedFile)return;
   setUploading(true);
   try{
     const f=new FormData(); f.append('file',selectedFile);
     const r=await fetch(`${API}/api/games/${game.id}/video`,{method:'POST',body:f});
     if(!r.ok){alert(`Upload fallito: ${await errorMessage(r)}`);return;}
     await selectGame(game.id,false);
     setSelectedFile(null);
     await reloadMe();
     setVision(null);
   }finally{
     setUploading(false);
   }
 }

 function parseVideoTime(value:string):number|null{
   const v=value.trim();
   if(!v) return null;
   const parts=v.split(':').map(Number);
   if(parts.some(Number.isNaN) || parts.length>3) return NaN;
   let seconds=0;
   for(const part of parts) seconds=seconds*60+part;
   return seconds;
 }

 function formatVideoTime(seconds:number){
   const total=Math.max(0,Math.floor(seconds));
   const h=Math.floor(total/3600);
   const m=Math.floor((total%3600)/60);
   const sec=total%60;
   return [h,m,sec].map(x=>String(x).padStart(2,'0')).join(':');
 }

 async function analyze(){
   if(!game)return;
   const start=parseVideoTime(rangeStart) ?? 0;
   const end=parseVideoTime(rangeEnd);
   if(Number.isNaN(start)||Number.isNaN(end)){alert('Usa il formato HH:MM:SS, ad esempio 00:12:30.');return;}
   if(end!==null && end<=start){alert('Il valore A deve essere maggiore di DA.');return;}
   setVision(null);
   const r=await fetch(`${API}/api/games/${game.id}/analysis`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({startSeconds:start,endSeconds:end})});
   if(!r.ok){alert(await errorMessage(r));return;}
   const created:AnalysisJob=await r.json();
   if(!created.analysisId){console.error('Analysis response has no analysisId',created);return;}
   setJob(created);
   await loadActiveAnalyses();
   await reloadMe();
 }

 async function pauseAnalysis(id:string){
   const r=await fetch(`${API}/api/analysis/${id}/pause`,{method:'POST'});
   if(!r.ok){alert(await errorMessage(r));return;}
   const updated:AnalysisJob=await r.json();
   if(job?.analysisId===id) setJob(updated);
   await loadActiveAnalyses();
   await reloadMe();
 }

 async function resumeAnalysis(id:string){
   const r=await fetch(`${API}/api/analysis/${id}/resume`,{method:'POST'});
   if(!r.ok){alert(await errorMessage(r));return;}
   const updated:AnalysisJob=await r.json();
   if(job?.analysisId===id) setJob(updated);
   await loadActiveAnalyses();
   await reloadMe();
 }

 async function deleteAnalysis(id:string){
   if(!confirm('Eliminare questa elaborazione? Il video e la partita resteranno invariati.')) return;
   const r=await fetch(`${API}/api/analysis/${id}`,{method:'DELETE'});
   if(!r.ok && r.status!==404){alert(await errorMessage(r));return;}
   if(job?.analysisId===id){setJob(null);setVision(null);}
   await loadActiveAnalyses();
   if(game) {
     const jr=await fetch(`${API}/api/games/${game.id}/analysis/latest`);
     setJob(jr.ok ? await jr.json() : null);
   }
 }

 function seek(ts:number){
   if(video.current){video.current.currentTime=Math.max(0,ts-4);video.current.play()}
 }

 const isRunning=job?.status==='Pending'||job?.status==='Processing';
 const isPaused=job?.status==='Paused';

 return <main>
   <AccountPanel me={me} reload={reloadMe} logout={logout}/>
   {me.roles.includes('Admin')&&<AdminDashboard/>}
   <div className="page-title"><div><h1>BasketVision</h1><p>Analisi automatica eventi basket da video</p></div>{activeAnalyses.length>0&&<span className="running-badge">{activeAnalyses.length} analisi in background</span>}</div>

   {activeAnalyses.length>0&&<section className="card background-jobs"><div className="section-heading"><div><h2>Analisi in background</h2><p>I job continuano nel worker anche se cambi partita, ricarichi la pagina o chiudi il browser.</p></div></div><div className="job-list">{activeAnalyses.map(a=><div key={a.analysisId} className="job-row"><button className="job-open" onClick={()=>selectGame(a.gameId)}><div className="job-main"><b>{a.gameName}</b><span>{a.status==='Pending'?'In coda':a.status==='Paused'?'In pausa':'Elaborazione CV'}</span></div><div className="job-progress"><div className="progress-track"><div className="progress-fill" style={{width:`${Math.max(1,a.progress)}%`}}/></div><strong>{a.progress}%</strong></div></button><div className="job-actions">{a.status==='Paused'?<button onClick={()=>resumeAnalysis(a.analysisId)}>Riprendi</button>:<button onClick={()=>pauseAnalysis(a.analysisId)}>Pausa</button>}<button className="danger" onClick={()=>deleteAnalysis(a.analysisId)}>Elimina</button></div></div>)}</div></section>}

   <section className="card"><h2>Nuova partita</h2><form onSubmit={createGame}><input name="name" placeholder="Lecco vs Milano" required/><input name="a" placeholder="Squadra A" required/><input name="b" placeholder="Squadra B" required/><button>Crea</button></form><select onChange={e=>selectGame(e.target.value)} value={game?.id??''}><option value="">Seleziona partita</option>{games.map(g=><option key={g.id} value={g.id}>{g.name}</option>)}</select></section>

   {game&&<><section className="card"><h2>{game.name}</h2><div className="actions"><input type="file" accept="video/*" onChange={e=>setSelectedFile(e.target.files?.[0]??null)}/><button onClick={upload} disabled={!selectedFile||uploading}>{uploading?'Caricamento...':'Carica video'}</button><button onClick={analyze} disabled={!game.videoPath || isRunning || isPaused || (!me.bypass && me.entitlements.VideoAnalysis?.enabled!==true)}>Avvia analisi CV</button>{game.videoPath?<span>Video caricato ✓</span>:<span>Nessun video caricato</span>}</div>{selectedFile&&<p>File selezionato: <b>{selectedFile.name}</b> ({(selectedFile.size/1024/1024).toFixed(1)} MB)</p>}

   {game.videoPath&&<div className="analysis-range"><div><b>Intervallo da analizzare</b><span>Lascia “A” vuoto per arrivare fino alla fine del video.</span></div><label>DA<input value={rangeStart} onChange={e=>setRangeStart(e.target.value)} placeholder="00:00:00"/></label><button type="button" onClick={()=>setRangeStart(formatVideoTime(video.current?.currentTime??0))}>Usa posizione</button><label>A<input value={rangeEnd} onChange={e=>setRangeEnd(e.target.value)} placeholder="fine video"/></label><button type="button" onClick={()=>setRangeEnd(formatVideoTime(video.current?.currentTime??0))}>Usa posizione</button></div>}

   {job&&<div className={`analysis-status ${job.status.toLowerCase()}`}><div className="analysis-status-head"><div><b>{job.status==='Completed'?'Analisi completata':job.status==='Failed'?'Analisi fallita':job.status==='Paused'?'Analisi in pausa':job.status==='Pending'?'Analisi in coda':'Analisi CV in corso'}</b>{isRunning&&<span>Puoi lasciare questa pagina: il worker continuerà in background.</span>}{isPaused&&<span>Il checkpoint è stato salvato. Riprendi per continuare dal punto raggiunto.</span>}{job.status==='Failed'&&<span>{job.error??'Errore durante l’analisi'}</span>}</div><strong>{job.status==='Completed'?'100%':`${job.progress}%`}</strong></div>{(isRunning||isPaused)&&<div className="progress-track large"><div className="progress-fill" style={{width:`${Math.max(1,job.progress)}%`}}/></div>}<div className="analysis-controls">{isRunning&&<button onClick={()=>pauseAnalysis(job.analysisId)}>Pausa</button>}{isPaused&&<button onClick={()=>resumeAnalysis(job.analysisId)}>Riprendi</button>}<button className="danger" onClick={()=>deleteAnalysis(job.analysisId)}>Elimina elaborazione</button></div></div>}

   {game.videoPath&&<video ref={video} controls src={`${API}/api/games/${game.id}/video`}/>}</section>

   {vision&&<section className="card">
     <h2>Vision debug — {vision.mode==='vision-cv02.4'?'CV-02.4':vision.mode==='vision-cv02.3'?'CV-02.3':vision.mode==='vision-cv02.2'?'CV-02.2':vision.mode==='vision-cv02.1'?'CV-02.1':'CV-02'}</h2>
     <p><b>Person model:</b> {vision.model} · <b>Ball model:</b> {vision.ballModel??vision.model} · <b>Video:</b> {vision.video.width}×{vision.video.height} @ {vision.video.fps.toFixed(1)} fps · <b>Durata:</b> {vision.video.durationSeconds.toFixed(1)}s · <b>Intervallo:</b> {formatVideoTime(vision.video.analysisStartSeconds??0)} → {vision.video.analysisEndSeconds==null?'fine':formatVideoTime(vision.video.analysisEndSeconds)}</p>
     {vision.config&&<p><b>Person stride:</b> {vision.config.personFrameStride??vision.video.frameStride} · <b>Tracker:</b> {vision.config.personTracker??'legacy'} · <b>GMC:</b> {vision.config.personTrackerThresholds?.gmcMethod??'-'} · <b>Ball stride:</b> {vision.config.ballFrameStride??'-'} · <b>Ball conf:</b> {vision.config.ballConfidence??'-'} · <b>Nuova track conf/score:</b> {vision.config.ballTrackNewMinConfidence??'-'} / {vision.config.ballTrackNewMinScore??'-'} · <b>Update score:</b> {vision.config.ballTrackUpdateMinScore??'-'} · <b>Hit per conferma:</b> {vision.config.ballTrackMinHits??'-'}</p>}
     <div className="vision-stats"><div><b>{vision.summary.personDetections}</b><span>Person detection</span></div><div><b>{vision.summary.personTrackedDetections??'-'}</b><span>Person detection con ID</span></div><div><b>{vision.summary.personUntrackedDetections??'-'}</b><span>Person detection senza ID</span></div><div><b>{vision.summary.uniquePersonTracks}</b><span>Track persone</span></div><div><b>{vision.summary.rawBallCandidates??vision.summary.ballDetections}</b><span>Raw candidates</span></div><div><b>{vision.summary.acceptedBallDetections??vision.summary.ballDetections}</b><span>Accepted detections</span></div><div><b>{vision.summary.rejectedBallCandidates??0}</b><span>Rejected candidates</span></div><div><b>{vision.summary.confirmedBallTracks??vision.summary.validBallTracks??0}</b><span>Confirmed ball tracks</span></div><div><b>{((vision.summary.averageBallConfidence??0)*100).toFixed(1)}%</b><span>Confidence media</span></div><div><b>{((vision.summary.medianBallConfidence??0)*100).toFixed(1)}%</b><span>Confidence mediana</span></div><div><b>{(vision.summary.ballDetectionsPerSecond??0).toFixed(2)}</b><span>Detection/sec</span></div><div><b>{vision.summary.fullBallDetections??0}</b><span>Raw full-frame</span></div><div><b>{vision.summary.tiledBallDetections??0}</b><span>Raw tiled</span></div><div><b>{vision.summary.framesWithBall}</b><span>Frame con palla accettata</span></div></div>
     {vision.summary.personConfidenceBuckets&&<div className="diagnostic-note"><b>Diagnostica person tracker:</b> conf media {((vision.summary.averagePersonConfidence??0)*100).toFixed(1)}%, mediana {((vision.summary.medianPersonConfidence??0)*100).toFixed(1)}%. Sotto 0.25: {vision.summary.personConfidenceBuckets.belowTrackLow025}; 0.25–0.60: {vision.summary.personConfidenceBuckets.trackLow025To060}; 0.60–0.70: {vision.summary.personConfidenceBuckets.trackHigh060To070}; ≥0.70: {vision.summary.personConfidenceBuckets.newTrack070Plus}. Creazioni: {vision.summary.personTrackCreations??'-'}; associazioni: {vision.summary.personTrackAssociations??'-'}; frame con ID: {vision.summary.personFramesWithTracks??'-'}; detection ≥0.70 con ID: {vision.summary.personHighConfidenceWithId??'-'}, senza ID: {vision.summary.personHighConfidenceWithoutId??'-'}.</div>}
     {(vision.summary.ballAcceptanceReasons||vision.summary.ballRejectionReasons)&&<div className="diagnostic-note"><b>Decisioni ball:</b> track create {vision.summary.ballTracksCreated??0}, update deboli {vision.summary.ballWeakTrackUpdates??0}. Accepted: {Object.entries(vision.summary.ballAcceptanceReasons??{}).map(([reason,count])=>`${reason}=${count}`).join(', ')||'-'}. Rejected: {Object.entries(vision.summary.ballRejectionReasons??{}).map(([reason,count])=>`${reason}=${count}`).join(', ')||'-'}.</div>}
     {(vision.debugFrames?.length??0)>0&&<><h3>Campioni debug annotati</h3><div className="debug-gallery">{vision.debugFrames!.slice(0,6).map(sample=><a key={sample.fileName} href={`${API}/api/analysis/${vision.analysisId}/debug/${encodeURIComponent(sample.fileName)}`} target="_blank" rel="noreferrer"><img src={`${API}/api/analysis/${vision.analysisId}/debug/${encodeURIComponent(sample.fileName)}`} alt={`Detection accettata a ${sample.timestamp.toFixed(2)} secondi`}/><b>{sample.timestamp.toFixed(2)}s</b><span>raw {sample.rawCandidates} · accepted {sample.acceptedDetections} · rejected {sample.rejectedCandidates}</span></a>)}</div></>}
     <h3>Prime detection accettate</h3>{vision.ballTrack.length===0?<p>Nessuna detection accettata: verificare soglie soft o usare un detector basket-specifico.</p>:<div className="events">{vision.ballTrack.slice(0,150).map((p,i)=><button className="event" title={p.acceptanceReason??p.rejectionReason} key={`${p.timestamp}-${i}`} onClick={()=>seek(p.timestamp)}><b>{p.timestamp.toFixed(2)}s</b><span>{p.source??'ball'}</span><span>track {p.trackId??'-'} · {p.trackState??'legacy'}</span><small>{Math.round(p.confidence*100)}%</small></button>)}</div>}
   </section>}

   {report&&<section className="grid"><div className="card"><h2>Statistiche eventi</h2><p>CV-02 migliora la detection/traiettoria della palla; gli eventi basket verranno alimentati dal successivo ShotDetector.</p><table><thead><tr><th>Stat</th>{report.teams.map(t=><th key={t.teamId}>{t.teamName}</th>)}</tr></thead><tbody>{Object.keys(report.teams[0]?.stats??{}).map(k=><tr key={k}><td>{k}</td>{report.teams.map(t=><td key={t.teamId}>{t.stats[k]??0}</td>)}</tr>)}</tbody></table></div><div className="card"><h2>Eventi</h2><div className="events">{report.events.map(ev=><button className="event" key={ev.id} onClick={()=>seek(ev.videoTimestamp)}><b>{ev.videoTimestamp.toFixed(1)}s</b><span>{ev.team??'-'}</span><span>{ev.type}</span><small>{Math.round(ev.confidence*100)}%</small></button>)}</div></div></section>}</>}
 </main>
}
createRoot(document.getElementById('root')!).render(<Session>{(me,reloadMe,logout)=><App key={me.id} me={me} reloadMe={reloadMe} logout={logout}/>}</Session>);
