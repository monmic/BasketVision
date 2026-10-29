import React, {useEffect, useRef, useState} from 'react';
import {createRoot, hydrateRoot} from 'react-dom/client';
import './style.css';
import './landing.css';
import {AdminDashboard} from './AdminDashboard';
import {ExportReport} from './ExportReport';
import {ShotReview,eventLabels,type ReviewEvent} from './ShotReview';

import {API, apiFetch as fetch, Session, AccountPanel, errorMessage, type Me} from './auth';
type Game = {id:string,name:string,teams:{id:string,name:string,side:string}[],videoPath?:string};
type Report = {gameId:string,gameName:string,teams:{teamId:string,teamName:string,stats:Record<string,number>,shooting?:{points:number,unspecified:number,categories:{value:number,made:number,attempted:number,percentage:number|null}[]}}[],events:ReviewEvent[]};
type AnalysisStatus = 'Pending'|'Processing'|'Completed'|'Failed'|'Paused';
type AnalysisJob = {analysisId:string,gameId:string,isManualReview?:boolean,status:AnalysisStatus,progress:number,error?:string|null,startSeconds?:number,endSeconds?:number|null};
type ActiveAnalysis = AnalysisJob & {gameName:string,createdAtUtc:string};
type BallPoint = {shotMotionEligible?:boolean,sceneMotionState?:string,sceneResidualPx?:number,sceneCameraShiftPx?:number,timestamp:number,trackId?:number|null,trackState?:'tentative'|'confirmed'|'lost',confidence:number,qualityScore?:number,acceptedScore?:number,acceptanceReason?:string,rejectionReason?:string,associationType?:string,source?:string,x1:number,y1:number,x2:number,y2:number,centerX:number,centerY:number,width?:number,height?:number};
type DebugFrame = {fileName:string,timestamp:number,rawCandidates:number,acceptedDetections:number,rejectedCandidates:number};
type ShotCandidate = {timestamp:number,startSeconds:number,endSeconds:number,trackId:number,type:'ShotCandidate',status:'NeedsReview',teamId:null,outcome:null,confidence:number,reason:string,evidence:{timestamp:number,x:number,y:number}[]};
type RimCalibration = {x:number,y:number,width:number,startSeconds:number,endSeconds:number};
type PersonConfidenceBuckets = {belowTrackLow025:number,trackLow025To060:number,trackHigh060To070:number,newTrack070Plus:number};
type VisionResult = {
 analysisId:string;
 gameId:string;
 mode:string;
 model:string;
 ballModel?:string;
 config?:{personFrameStride?:number,personConfidence?:number,personImgsz?:number,personTracker?:string,personTrackerThresholds?:{trackLow:number,trackHigh:number,newTrack:number,gmcMethod:string},ballFrameStride?:number,ballConfidence?:number,ballImgsz?:number,ballUseTiles?:boolean,ballTileStride?:number,ballTileImgsz?:number,ballTrackMinHits?:number,ballTrackTemporalWindow?:boolean,ballCameraMotionFilter?:boolean,ballTrackConfirmWindowSeconds?:number,ballTrackRecoverySeconds?:number,ballAcceptedMinScore?:number,ballTrackUpdateMinScore?:number,ballTrackNewMinScore?:number,ballTrackNewMinConfidence?:number,ballDebugExport?:boolean};
 video:{fps:number,totalFrames:number,width:number,height:number,durationSeconds:number,analysisStartSeconds?:number,analysisEndSeconds?:number|null,analysisDurationSeconds?:number|null,frameStride:number,processedFrames:number,processedPersonFrames?:number,processedBallFrames?:number};
 summary:{personDetections:number,personTrackedDetections?:number,personUntrackedDetections?:number,personTrackCreations?:number,personTrackAssociations?:number,personFramesWithTracks?:number,personHighConfidenceWithId?:number,personHighConfidenceWithoutId?:number,averagePersonConfidence?:number,medianPersonConfidence?:number,personConfidenceBuckets?:PersonConfidenceBuckets,ballDetections:number,rawBallCandidates?:number,acceptedBallDetections?:number,rejectedBallCandidates?:number,ballAcceptanceReasons?:Record<string,number>,ballRejectionReasons?:Record<string,number>,ballTracksCreated?:number,ballWeakTrackUpdates?:number,fullBallDetections?:number,tiledBallDetections?:number,framesWithBall:number,maxPersonsInFrame:number,uniquePersonTracks:number,uniqueBallTracks:number,confirmedBallTracks?:number,validBallTracks?:number,averageBallConfidence?:number,medianBallConfidence?:number,ballDetectionsPerSecond?:number,storedBallPoints:number,shotCandidates?:number};
 ballTrack:BallPoint[];
 shotCandidates?:ShotCandidate[];
 shotCandidateCalibration?:RimCalibration|null;
 debugFrames?:DebugFrame[];
};

function App({me,reloadMe,logout}:{me:Me,reloadMe:()=>Promise<void>,logout:()=>Promise<void>}){
 const [games,setGames]=useState<Game[]>([]);
 const [game,setGame]=useState<Game|null>(null);
 const [report,setReport]=useState<Report|null>(null);
 const [job,setJob]=useState<AnalysisJob|null>(null);
 const [analyses,setAnalyses]=useState<(AnalysisJob&{createdAtUtc:string})[]>([]);
 const [activeAnalyses,setActiveAnalyses]=useState<ActiveAnalysis[]>([]);
 const [vision,setVision]=useState<VisionResult|null>(null);
 const [selectedFile,setSelectedFile]=useState<File|null>(null);
 const [uploading,setUploading]=useState(false);
 const [starting,setStarting]=useState(false);
 const [operationError,setOperationError]=useState('');
 const [pollError,setPollError]=useState('');
 const [visionLoading,setVisionLoading]=useState(false);
 const [visionError,setVisionError]=useState('');
 const [visionReload,setVisionReload]=useState(0);
 const [openingReview,setOpeningReview]=useState(false);
 const [rangeStart,setRangeStart]=useState('00:00:00');
 const [rangeEnd,setRangeEnd]=useState('');
 const [shotCandidatesEnabled,setShotCandidatesEnabled]=useState(false);
 const [calibratingRim,setCalibratingRim]=useState(false);
 const [rimWidth,setRimWidth]=useState(40);
 const [rimCalibration,setRimCalibration]=useState<RimCalibration|null>(null);
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

 async function selectGame(id:string, updateUrl=true, analysisId?:string){
   setReport(null);setVision(null);setJob(null);setAnalyses([]);
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
   setShotCandidatesEnabled(false);
   setCalibratingRim(false);
   setRimCalibration(null);
   if(updateUrl) history.replaceState(null,'',`${location.pathname}?game=${g.id}`);

   const jr=await fetch(`${API}/api/games/${g.id}/analyses`);
   const jobHistory=jr.ok?await jr.json():[];
   const selectedId=analysisId??new URLSearchParams(location.search).get('analysis');
   setAnalyses(jobHistory);setJob(jobHistory.find((a:AnalysisJob)=>a.analysisId===selectedId)??jobHistory.find((a:AnalysisJob)=>!a.isManualReview)??jobHistory[0]??null);
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
   if(!game||!job||job.gameId!==game.id)return;
   history.replaceState(null,'',`${location.pathname}?game=${game.id}&analysis=${job.analysisId}`);
 },[game?.id,job?.analysisId]);

 useEffect(()=>{
   const t=setInterval(loadActiveAnalyses,3000);
   return()=>clearInterval(t);
 },[]);

 useEffect(()=>{
   setReport(null);
   if(!game||!job||job.gameId!==game.id) return;
   let cancelled=false;
   fetch(`${API}/api/games/${game.id}/report?analysisId=${job.analysisId}`)
     .then(r=>r.ok?r.json():null)
     .then(value=>{if(!cancelled)setReport(value)})
     .catch(()=>{if(!cancelled)setReport(null)});
   return()=>{cancelled=true};
 },[game?.id,job?.analysisId,job?.progress,job?.status]);

 useEffect(()=>{
   setPollError('');
   if(!job?.analysisId || job.status==='Completed' || job.status==='Failed') return;
   let cancelled=false;
   const t=setInterval(async()=>{
     try{
       const r=await fetch(`${API}/api/analysis/${job.analysisId}`);
       if(!r.ok) throw new Error();
       const updated:AnalysisJob=await r.json();
       if(cancelled)return;
       setPollError('');
       setJob(updated);
       setAnalyses(items=>items.map(item=>item.analysisId===updated.analysisId?{...item,...updated}:item));
       if(updated.status==='Completed'||updated.status==='Failed') loadActiveAnalyses();
     }catch{if(!cancelled)setPollError('Aggiornamento temporaneamente non disponibile. Riprovo automaticamente; l’analisi continua in background.')}
   },1000);
   return()=>{cancelled=true;clearInterval(t)};
 },[job?.analysisId,job?.status]);

 useEffect(()=>{
   if(!job||job.isManualReview)return;
   setRangeStart(formatVideoTime(job.startSeconds??0));
   setRangeEnd(job.endSeconds==null?'':formatVideoTime(job.endSeconds));
 },[job?.analysisId]);

 useEffect(()=>{
   setVision(null);setVisionError('');setVisionLoading(false);
   if(!job?.analysisId || job.status!=='Completed' || job.isManualReview) return;
   let cancelled=false;
   setVisionLoading(true);
   reloadMe().catch(()=>{});
   (async()=>{
     try{
       const r=await fetch(`${API}/api/analysis/${job.analysisId}/vision`);
       if(!r.ok)throw new Error();
       const value:VisionResult=await r.json();
       if(!cancelled)setVision(value);
     }catch{if(!cancelled)setVisionError('L’analisi è completata, ma il risultato non è disponibile. Puoi riprovare senza avviare una nuova analisi.')}
     finally{if(!cancelled)setVisionLoading(false)}
   })();
   return()=>{cancelled=true};
 },[job?.analysisId,job?.status,visionReload]);

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
   setUploading(true);setOperationError('');
   let uploaded=false;
   try{
     const f=new FormData(); f.append('file',selectedFile);
     const r=await fetch(`${API}/api/games/${game.id}/video`,{method:'POST',body:f});
     if(!r.ok){setOperationError(`Upload fallito: ${await errorMessage(r)}`);return;}
     uploaded=true;
     await selectGame(game.id,false);
     setSelectedFile(null);
     await reloadMe();
     setVision(null);
     setShotCandidatesEnabled(false);
     setCalibratingRim(false);
     setRimCalibration(null);
   }catch{setOperationError(uploaded?'Video caricato, ma la pagina non è aggiornata. Ricarica la partita.':'Caricamento non riuscito. Il file selezionato è conservato: riprova.')}finally{
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
   if(!game||starting)return;
   const start=parseVideoTime(rangeStart) ?? 0;
   const end=parseVideoTime(rangeEnd);
   if(Number.isNaN(start)||Number.isNaN(end)){alert('Usa il formato HH:MM:SS, ad esempio 00:12:30.');return;}
   if(end!==null && end<=start){alert('Il valore A deve essere maggiore di DA.');return;}
   if(shotCandidatesEnabled&&!rimCalibration){alert('Seleziona il centro del ferro sul video prima di avviare i candidati di tiro.');return;}
   const calibration=shotCandidatesEnabled&&rimCalibration?{...rimCalibration,startSeconds:start,endSeconds:end??video.current?.duration??rimCalibration.endSeconds}:null;
   setStarting(true);setOperationError('');
   let started=false;
   try{
   const r=await fetch(`${API}/api/games/${game.id}/analysis`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({startSeconds:start,endSeconds:end,shotCandidates:calibration?{enabled:true,rim:calibration}:null})});
   if(!r.ok){setOperationError(await errorMessage(r));return;}
   const created:AnalysisJob=await r.json();
   if(!created.analysisId){setOperationError('La risposta non contiene l’analisi. Ricarica la partita prima di riprovare.');return;}
   started=true;
   setJob(created);
   const historyResponse=await fetch(`${API}/api/games/${game.id}/analyses`);
   if(historyResponse.ok)setAnalyses(await historyResponse.json());
   await loadActiveAnalyses();
   await reloadMe();
   }catch{setOperationError(started?'L’analisi è stata avviata. Ricarica la partita per aggiornare i dati.':'Avvio non confermato. Ricarica la partita per verificare se l’analisi è stata creata prima di riprovare.')}finally{setStarting(false)}
 }

 async function openReview(){
   if(!game||openingReview)return;
   setOpeningReview(true);
   try{
     const r=await fetch(`${API}/api/games/${game.id}/review`,{method:'POST'});
     if(!r.ok){alert(await errorMessage(r));return;}
     const opened=await r.json();
     setJob(opened);setVision(null);
     setAnalyses(items=>[opened,...items.filter(item=>item.analysisId!==opened.analysisId)]);
   }catch{alert('Impossibile aprire la revisione. Riprova.')}finally{setOpeningReview(false)}
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
   if(!confirm('Eliminare questa sessione e tutti i suoi eventi, inclusi i tiri confermati? Il video e la partita resteranno invariati.')) return;
   const r=await fetch(`${API}/api/analysis/${id}`,{method:'DELETE'});
   if(!r.ok && r.status!==404){alert(await errorMessage(r));return;}
   if(job?.analysisId===id){setJob(null);setVision(null);}
   await loadActiveAnalyses();
   if(game) {
     const jr=await fetch(`${API}/api/games/${game.id}/analyses`);
     const history=jr.ok?await jr.json():[];
     setAnalyses(history);setJob(history[0]??null);setReport(null);setVision(null);
   }
 }

 function seek(ts:number){
   if(video.current){video.current.pause();video.current.currentTime=Math.max(0,ts)}
 }

 function selectRim(e:React.MouseEvent<HTMLVideoElement>){
   if(!calibratingRim||!video.current) return;
   const rect=video.current.getBoundingClientRect();
   const videoRatio=video.current.videoWidth/video.current.videoHeight;
   const elementRatio=rect.width/rect.height;
   const contentWidth=elementRatio>videoRatio?rect.height*videoRatio:rect.width;
   const contentHeight=elementRatio>videoRatio?rect.height:rect.width/videoRatio;
   const offsetX=rect.left+(rect.width-contentWidth)/2;
   const offsetY=rect.top+(rect.height-contentHeight)/2;
   if(e.clientX<offsetX||e.clientX>offsetX+contentWidth||e.clientY<offsetY||e.clientY>offsetY+contentHeight) return;
   const scaleX=video.current.videoWidth/contentWidth;
   const scaleY=video.current.videoHeight/contentHeight;
   const start=parseVideoTime(rangeStart)??0;
   const parsedEnd=parseVideoTime(rangeEnd);
   const end=parsedEnd??video.current.duration;
   setRimCalibration({x:(e.clientX-offsetX)*scaleX,y:(e.clientY-offsetY)*scaleY,width:rimWidth,startSeconds:start,endSeconds:end});
   setCalibratingRim(false);
 }

 const hasConfirmedEvents=report?.events.some(e=>e.status==='Confirmed'||e.status==='Corrected')??false;
 const showStatistics=job?.isManualReview||hasConfirmedEvents;
 const isRunning=job?.status==='Pending'||job?.status==='Processing';
 const isPaused=job?.status==='Paused';

 return <main>
   <AccountPanel me={me} reload={reloadMe} logout={logout}/>
   {me.roles.includes('Admin')&&<AdminDashboard/>}
   <div className="page-title"><div><h1>BasketVision</h1><p>Analisi video basket. Tracking e riconoscimento degli eventi in sviluppo.</p></div>{activeAnalyses.length>0&&<span className="running-badge">{activeAnalyses.length} analisi in background</span>}</div>

   {operationError&&<p role="alert">{operationError}</p>}
   {activeAnalyses.length>0&&<section className="card background-jobs"><div className="section-heading"><div><h2>Analisi in background</h2><p>I job continuano nel worker anche se cambi partita, ricarichi la pagina o chiudi il browser.</p></div></div><div className="job-list">{activeAnalyses.map(a=><div key={a.analysisId} className="job-row"><button className="job-open" disabled={uploading||starting} onClick={()=>selectGame(a.gameId,true,a.analysisId)}><div className="job-main"><b>{a.gameName}</b><span>{a.status==='Pending'?'In coda':a.status==='Paused'?'In pausa':'Elaborazione CV'}</span></div><div className="job-progress"><div className="progress-track"><div className="progress-fill" style={{width:`${Math.max(1,a.progress)}%`}}/></div><strong>{a.progress}%</strong></div></button><div className="job-actions">{a.status==='Paused'?<button onClick={()=>resumeAnalysis(a.analysisId)}>Riprendi</button>:<button onClick={()=>pauseAnalysis(a.analysisId)}>Pausa</button>}<button className="danger" onClick={()=>deleteAnalysis(a.analysisId)}>Elimina</button></div></div>)}</div></section>}

   <section className="card"><h2>Nuova partita</h2><form onSubmit={createGame}><input name="name" placeholder="Lecco vs Milano" required/><input name="a" placeholder="Squadra A" required/><input name="b" placeholder="Squadra B" required/><button disabled={uploading||starting}>Crea</button></form><select disabled={uploading||starting} onChange={e=>selectGame(e.target.value)} value={game?.id??''}><option value="">Seleziona partita</option>{games.map(g=><option key={g.id} value={g.id}>{g.name}</option>)}</select></section>

   {game&&<><section className="card"><h2>{game.name}</h2><div className="actions"><input type="file" disabled={uploading} accept="video/*" onChange={e=>setSelectedFile(e.target.files?.[0]??null)}/><button onClick={upload} disabled={!selectedFile||uploading||isRunning||isPaused}>{uploading?'Caricamento...':'Carica video'}</button>{game.videoPath?<span>Video caricato ✓</span>:<span>Nessun video caricato</span>}</div>{uploading&&<p role="status">Attendi la fine del caricamento prima di chiudere questa pagina. Dopo l’avvio, l’analisi continuerà in background.</p>}{selectedFile&&<p>File selezionato: <b>{selectedFile.name}</b> ({(selectedFile.size/1024/1024).toFixed(1)} MB)</p>}

   {game.videoPath&&<details className="review-start"><summary>Strumenti di verifica manuale</summary><p>Guarda il video e registra squadra, valore ed esito di ogni tiro. I dati vengono salvati e puoi riprendere in seguito.</p><button onClick={openReview} disabled={openingReview||uploading||(!me.bypass&&me.entitlements.AdvancedEvents?.enabled!==true)}>{openingReview?'Apertura...':analyses.some(a=>a.isManualReview)?'Riprendi revisione assistita':'Inizia revisione assistita'}</button>{!me.bypass&&me.entitlements.AdvancedEvents?.enabled!==true&&<p>La revisione richiede la funzionalita eventi avanzati del tuo abbonamento.</p>}</details>}
   {game.videoPath&&<details open><summary>Analisi CV sperimentale</summary><p>Analizza il video per ottenere tracking e diagnostica. Il riconoscimento affidabile di tiri ed esiti automatici non e ancora disponibile.</p><button className="primary" onClick={analyze} disabled={starting||uploading||isRunning||isPaused||(!me.bypass&&me.entitlements.VideoAnalysis?.enabled!==true)}>Avvia analisi CV</button>
   <div className="analysis-range"><div><b>Intervallo da analizzare</b><span>Lascia “A” vuoto per arrivare fino alla fine del video.</span></div><label>DA<input value={rangeStart} onChange={e=>setRangeStart(e.target.value)} placeholder="00:00:00"/></label><button type="button" onClick={()=>setRangeStart(formatVideoTime(video.current?.currentTime??0))}>Usa posizione</button><label>A<input value={rangeEnd} onChange={e=>setRangeEnd(e.target.value)} placeholder="fine video"/></label><button type="button" onClick={()=>setRangeEnd(formatVideoTime(video.current?.currentTime??0))}>Usa posizione</button></div>

   <div className="shot-candidate-setup"><label><input type="checkbox" checked={shotCandidatesEnabled} onChange={e=>{setShotCandidatesEnabled(e.target.checked);setCalibratingRim(false)}}/> Candidati di tiro sperimentali</label>{shotCandidatesEnabled&&<><p>Valido per una ripresa fissa: porta il video su un fotogramma nitido, poi indica il centro del ferro.</p><label>Larghezza ferro (pixel video)<input type="number" min="4" step="1" value={rimWidth} onChange={e=>setRimWidth(Math.max(4,Number(e.target.value)||4))}/></label><button type="button" onClick={()=>setCalibratingRim(true)}>{calibratingRim?'Clicca ora sul ferro':'Seleziona ferro sul video'}</button>{rimCalibration&&<span>Ferro: x {rimCalibration.x.toFixed(0)}, y {rimCalibration.y.toFixed(0)}, larghezza {rimCalibration.width}px</span>}</>}</div></details>}

   {job&&<div className={`analysis-status ${job.status.toLowerCase()}`}><div className="analysis-status-head"><div><b>{job.isManualReview?'Revisione assistita':job.status==='Completed'?'Analisi completata':job.status==='Failed'?'Analisi fallita':job.status==='Paused'?'Analisi in pausa':job.status==='Pending'?'Analisi in coda':'Analisi CV in corso'}</b>{isRunning&&<span>Puoi lasciare questa pagina: il worker continuerà in background.</span>}{isPaused&&<span>Il checkpoint è stato salvato. Riprendi per continuare dal punto raggiunto.</span>}{job.status==='Failed'&&<span>{job.error??'Errore durante l’analisi'}</span>}</div><strong>{job.isManualReview?'Pronta':job.status==='Completed'?'100%':`${job.progress}%`}</strong></div>{(isRunning||isPaused)&&<div className="progress-track large"><div className="progress-fill" style={{width:`${Math.max(1,job.progress)}%`}}/></div>}<div className="analysis-controls">{isRunning&&<button onClick={()=>pauseAnalysis(job.analysisId)}>Pausa</button>}{isPaused&&<button onClick={()=>resumeAnalysis(job.analysisId)}>Riprendi</button>}<button className="danger" onClick={()=>deleteAnalysis(job.analysisId)}>Elimina sessione</button></div></div>}

   {pollError&&<p role="status">{pollError}</p>}
   {analyses.length>0&&<label>Sessione visualizzata<select value={job?.analysisId??''} onChange={e=>{setReport(null);setVision(null);setJob(analyses.find(a=>a.analysisId===e.target.value)??null)}}>{analyses.map(a=><option key={a.analysisId} value={a.analysisId}>{a.isManualReview?'Revisione assistita':'Analisi CV'} - {new Date(a.createdAtUtc).toLocaleString('it-IT')} · {a.analysisId.slice(0,8)}</option>)}</select></label>}
   {game.videoPath&&<video ref={video} controls={!calibratingRim} className={calibratingRim?'rim-calibration-active':''} onClick={selectRim} src={`${API}/api/games/${game.id}/video`}/>}</section>

   {report&&game&&job&&<>{(me.bypass||me.entitlements.ExportCsv?.enabled===true)&&<ExportReport key={`export-${job.analysisId}`} gameId={game.id} analysisId={job.analysisId}/>}<details className="card"><summary>Verifica e correzione manuale dei tiri</summary><ShotReview key={job.analysisId} gameId={game.id} teams={game.teams} events={report.events} analysisId={job?.status==='Completed'?job.analysisId:undefined} currentTime={()=>{video.current?.pause();return video.current?.currentTime??0}} seek={seek} reload={async()=>{const r=await fetch(`${API}/api/games/${game.id}/report?analysisId=${job.analysisId}`);if(!r.ok)throw new Error();setReport(await r.json())}}/></details></>}
   {report&&showStatistics&&<section className="card"><h2>Punti e percentuali</h2><p>Conteggi dei tiri confermati e classificati. I tiri da specificare sono esclusi dai punti e dalle percentuali per categoria.</p>{report.teams.map(t=><div key={t.teamId}><h3>{t.teamName}: {t.shooting?.points??0} punti</h3><p>Tiri con valore da specificare: {t.shooting?.unspecified??0}</p><table><thead><tr><th>Tipo</th><th>Segnati / Tentati</th><th>Percentuale</th></tr></thead><tbody>{t.shooting?.categories.map(c=><tr key={c.value}><td>{c.value===1?'Liberi':`Da ${c.value} punti`}</td><td>{c.made} / {c.attempted}</td><td>{c.percentage==null?'—':`${c.percentage.toFixed(1)}%`}</td></tr>)}</tbody></table></div>)}</section>}
   {job?.status==='Completed'&&!job.isManualReview&&<section className="card" aria-busy={visionLoading}>
     <h2>Risultato dell’analisi</h2>
     {visionLoading&&<p role="status">Caricamento del risultato…</p>}
     {visionError&&<div role="alert"><p>{visionError}</p><button onClick={()=>setVisionReload(value=>value+1)}>Riprova risultato</button></div>}
     {vision&&<><p><b>Rilevazioni sperimentali di persone e palla.</b> Non certificano tiri, canestri, esiti o attribuzione alle squadre.</p><p>{vision.video.processedFrames} fotogrammi elaborati</p><p>Intervallo: {formatVideoTime(vision.video.analysisStartSeconds??job.startSeconds??0)} → {formatVideoTime(vision.video.analysisEndSeconds??job.endSeconds??vision.video.durationSeconds)}</p><p>Puoi consultare i campioni e le rilevazioni nella diagnostica qui sotto; i timestamp delle rilevazioni aprono il punto corrispondente del video.</p>{!showStatistics&&<p>Punti e percentuali non disponibili: questa sessione non contiene eventi confermati.</p>}</>}
   </section>}
   {vision&&<details className="card"><summary>Diagnostica CV sperimentale</summary>
     <h2>Vision debug — {vision.mode==='vision-cv02.4'?'CV-02.4':vision.mode==='vision-cv02.3'?'CV-02.3':vision.mode==='vision-cv02.2'?'CV-02.2':vision.mode==='vision-cv02.1'?'CV-02.1':'CV-02'}</h2>
     <p><b>Person model:</b> {vision.model} · <b>Ball model:</b> {vision.ballModel??vision.model} · <b>Video:</b> {vision.video.width}×{vision.video.height} @ {vision.video.fps.toFixed(1)} fps · <b>Durata:</b> {vision.video.durationSeconds.toFixed(1)}s · <b>Intervallo:</b> {formatVideoTime(vision.video.analysisStartSeconds??0)} → {vision.video.analysisEndSeconds==null?'fine':formatVideoTime(vision.video.analysisEndSeconds)}</p>
     {vision.config&&<p><b>Person stride:</b> {vision.config.personFrameStride??vision.video.frameStride} · <b>Tracker:</b> {vision.config.personTracker??'legacy'} · <b>GMC:</b> {vision.config.personTrackerThresholds?.gmcMethod??'-'} · <b>Ball stride:</b> {vision.config.ballFrameStride??'-'} · <b>Ball conf:</b> {vision.config.ballConfidence??'-'} · <b>Nuova track conf/score:</b> {vision.config.ballTrackNewMinConfidence??'-'} / {vision.config.ballTrackNewMinScore??'-'} · <b>Update score:</b> {vision.config.ballTrackUpdateMinScore??'-'} · <b>Hit per conferma:</b> {vision.config.ballTrackMinHits??'-'}</p>}
     <div className="vision-stats"><div><b>{vision.summary.personDetections}</b><span>Person detection</span></div><div><b>{vision.summary.personTrackedDetections??'-'}</b><span>Person detection con ID</span></div><div><b>{vision.summary.personUntrackedDetections??'-'}</b><span>Person detection senza ID</span></div><div><b>{vision.summary.uniquePersonTracks}</b><span>Track persone</span></div><div><b>{vision.summary.rawBallCandidates??vision.summary.ballDetections}</b><span>Raw candidates</span></div><div><b>{vision.summary.acceptedBallDetections??vision.summary.ballDetections}</b><span>Accepted detections</span></div><div><b>{vision.summary.rejectedBallCandidates??0}</b><span>Rejected candidates</span></div><div><b>{vision.summary.confirmedBallTracks??vision.summary.validBallTracks??0}</b><span>Confirmed ball tracks</span></div><div><b>{((vision.summary.averageBallConfidence??0)*100).toFixed(1)}%</b><span>Confidence media</span></div><div><b>{((vision.summary.medianBallConfidence??0)*100).toFixed(1)}%</b><span>Confidence mediana</span></div><div><b>{(vision.summary.ballDetectionsPerSecond??0).toFixed(2)}</b><span>Detection/sec</span></div><div><b>{vision.summary.fullBallDetections??0}</b><span>Raw full-frame</span></div><div><b>{vision.summary.tiledBallDetections??0}</b><span>Raw tiled</span></div><div><b>{vision.summary.framesWithBall}</b><span>Frame con palla accettata</span></div></div>
     {vision.summary.personConfidenceBuckets&&<div className="diagnostic-note"><b>Diagnostica person tracker:</b> conf media {((vision.summary.averagePersonConfidence??0)*100).toFixed(1)}%, mediana {((vision.summary.medianPersonConfidence??0)*100).toFixed(1)}%. Sotto 0.25: {vision.summary.personConfidenceBuckets.belowTrackLow025}; 0.25–0.60: {vision.summary.personConfidenceBuckets.trackLow025To060}; 0.60–0.70: {vision.summary.personConfidenceBuckets.trackHigh060To070}; ≥0.70: {vision.summary.personConfidenceBuckets.newTrack070Plus}. Creazioni: {vision.summary.personTrackCreations??'-'}; associazioni: {vision.summary.personTrackAssociations??'-'}; frame con ID: {vision.summary.personFramesWithTracks??'-'}; detection ≥0.70 con ID: {vision.summary.personHighConfidenceWithId??'-'}, senza ID: {vision.summary.personHighConfidenceWithoutId??'-'}.</div>}
     {(vision.summary.ballAcceptanceReasons||vision.summary.ballRejectionReasons)&&<div className="diagnostic-note"><b>Decisioni ball:</b> track create {vision.summary.ballTracksCreated??0}, update deboli {vision.summary.ballWeakTrackUpdates??0}. Accepted: {Object.entries(vision.summary.ballAcceptanceReasons??{}).map(([reason,count])=>`${reason}=${count}`).join(', ')||'-'}. Rejected: {Object.entries(vision.summary.ballRejectionReasons??{}).map(([reason,count])=>`${reason}=${count}`).join(', ')||'-'}.</div>}
     {(vision.debugFrames?.length??0)>0&&<><h3>Campioni debug annotati</h3><div className="debug-gallery">{vision.debugFrames!.slice(0,6).map(sample=><a key={sample.fileName} href={`${API}/api/analysis/${vision.analysisId}/debug/${encodeURIComponent(sample.fileName)}`} target="_blank" rel="noreferrer"><img src={`${API}/api/analysis/${vision.analysisId}/debug/${encodeURIComponent(sample.fileName)}`} alt={`Detection accettata a ${sample.timestamp.toFixed(2)} secondi`}/><b>{sample.timestamp.toFixed(2)}s</b><span>raw {sample.rawCandidates} · accepted {sample.acceptedDetections} · rejected {sample.rejectedCandidates}</span></a>)}</div></>}
     {vision.shotCandidateCalibration&&<><h3>Candidati di tiro sperimentali ({vision.shotCandidates?.length??0})</h3><p className="diagnostic-note">Richiedono revisione: non indicano canestro segnato o sbagliato e la squadra non è ancora attribuita.</p>{(vision.shotCandidates?.length??0)===0?<p>Nessun candidato nell’intervallo calibrato.</p>:<div className="events">{vision.shotCandidates!.map((candidate,i)=><button className="event shot-candidate" key={`${candidate.timestamp}-${i}`} onClick={()=>seek(candidate.timestamp)}><b>{candidate.timestamp.toFixed(2)}s</b><span>Da revisionare</span><span>{candidate.reason==='rising_rim_approach'?'Avvicinamento al ferro':'Discesa vicino al ferro'}</span><small>{Math.round(candidate.confidence*100)}%</small></button>)}</div>}</>}
     <h3>Prime detection accettate</h3>{vision.ballTrack.length===0?<p>Nessuna detection accettata: verificare soglie soft o usare un detector basket-specifico.</p>:<div className="events">{vision.ballTrack.slice(0,150).map((p,i)=><button className="event" title={p.acceptanceReason??p.rejectionReason} key={`${p.timestamp}-${i}`} onClick={()=>seek(p.timestamp)}><b>{p.timestamp.toFixed(2)}s</b><span>{p.source??'ball'}</span><span>track {p.trackId??'-'} · {p.trackState??'legacy'}</span><small>{Math.round(p.confidence*100)}%</small></button>)}</div>}
   </details>}

   {report&&(showStatistics||report.events.length>0)&&<section className="grid">{showStatistics&&<div className="card"><h2>Statistiche eventi</h2><p>I candidati di tiro restano separati dalle statistiche finché non vengono classificati e attribuiti a una squadra.</p><table><thead><tr><th>Stat</th>{report.teams.map(t=><th key={t.teamId}>{t.teamName}</th>)}</tr></thead><tbody>{Object.keys(report.teams[0]?.stats??{}).map(k=><tr key={k}><td>{eventLabels[k]??k}</td>{report.teams.map(t=><td key={t.teamId}>{t.stats[k]??0}</td>)}</tr>)}</tbody></table></div>}<div className="card"><h2>Eventi e candidati</h2><div className="events">{report.events.map(ev=><button className={`event ${ev.type==='ShotCandidate'?'shot-candidate':''}`} key={ev.id} onClick={()=>seek(ev.videoTimestamp)}><b>{ev.videoTimestamp.toFixed(1)}s</b><span>{ev.team??(ev.type==='ShotCandidate'?'Da attribuire':'-')}</span><span>{eventLabels[ev.type]??ev.type}</span><small>{Math.round(ev.confidence*100)}%</small></button>)}</div></div></section>}</>}
 </main>
}
const root=document.getElementById('root')!;
const application=<Session>{(me,reloadMe,logout)=><App key={me.id} me={me} reloadMe={reloadMe} logout={logout}/>}</Session>;
if(root.hasChildNodes() && location.pathname==='/' && !location.search) hydrateRoot(root,application);
else createRoot(root).render(application);
