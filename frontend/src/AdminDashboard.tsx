import React, {useCallback, useEffect, useState} from 'react';
import {API, apiFetch, errorMessage} from './auth';

type Dashboard = {
  generatedAt:string; onlineWindowMinutes:number; registeredUsers:number; onlineUsers:number;
  validSessions:number; games:number; videos:number; storageBytes:number; videosWithoutSize:number;
  monthlyAnalysesStarted:number; monthlyRequestedMinutes:number; jobs:Record<string,number>;
  users:{id:string,email:string,plan:string|null,lastSeenAt:string|null,validSessions:number,onlineSessions:number}[];
};
const statusNames:Record<string,string>={Pending:'In coda',Processing:'In elaborazione',Paused:'In pausa',Completed:'Completate',Failed:'Fallite'};
const date=(value:string)=>new Date(value).toLocaleString('it-IT');
function size(bytes:number){return bytes>=1024**3?`${(bytes/1024**3).toFixed(2)} GiB`:`${(bytes/1024**2).toFixed(1)} MiB`;}

export function AdminDashboard(){
  const [data,setData]=useState<Dashboard|null>(null);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const load=useCallback(async()=>{
    setBusy(true);
    try{
      const response=await apiFetch(`${API}/api/admin/dashboard`);
      if(!response.ok) throw new Error(await errorMessage(response));
      setData(await response.json());setError('');
    }catch(e){setError(e instanceof Error?e.message:'Statistiche non disponibili.');}
    finally{setBusy(false);}
  },[]);
  useEffect(()=>{
    void load();
    const timer=setInterval(()=>{if(document.visibilityState==='visible') void load();},30000);
    return()=>clearInterval(timer);
  },[load]);
  return <section className="card admin-dashboard">
    <div className="admin-heading"><h2>Monitoraggio amministrativo</h2><button onClick={load} disabled={busy}>{busy?'Aggiornamento…':'Aggiorna statistiche'}</button></div>
    {error&&<p role="alert">{error} {data?'Sono mostrati gli ultimi dati disponibili.':''}</p>}
    {!data&&!error&&<p>Caricamento statistiche…</p>}
    {data&&<>
      <p>Ultimo aggiornamento: {date(data.generatedAt)} · aggiornamento automatico ogni 30 secondi.</p>
      <div className="vision-stats">
        <div><b>{data.onlineUsers}</b><span>Utenti attivi · ultimi {data.onlineWindowMinutes} minuti</span></div>
        <div><b>{data.registeredUsers}</b><span>Utenti registrati</span></div>
        <div><b>{data.validSessions}</b><span>Sessioni di login valide</span></div>
        <div><b>{data.games}</b><span>Partite</span></div>
        <div><b>{data.videos}</b><span>Video caricati</span></div>
        <div><b>{size(data.storageBytes)}</b><span>Storage video censito</span></div>
        <div><b>{data.monthlyAnalysesStarted}</b><span>Analisi avviate nel mese UTC</span></div>
        <div><b>{data.monthlyRequestedMinutes.toFixed(1)}</b><span>Minuti richiesti nel mese UTC</span></div>
      </div>
      {data.videosWithoutSize>0&&<p>{data.videosWithoutSize} video precedenti non hanno ancora una dimensione registrata e non sono inclusi nel totale storage.</p>}
      <h3>Stato delle analisi</h3>
      <div className="vision-stats">{Object.entries(statusNames).map(([status,label])=><div key={status}><b>{data.jobs[status]??0}</b><span>{label}</span></div>)}</div>
      <h3>Utenti e connessioni</h3>
      <p>“Attivo” indica richieste autenticate negli ultimi {data.onlineWindowMinutes} minuti, incluso il controllo automatico dei job. Una sessione valida può restare aperta anche dopo la chiusura del browser. Più schede o dispositivi non aumentano il numero di utenti.</p>
      <div className="admin-users"><table><thead><tr><th>Email</th><th>Piano</th><th>Stato</th><th>Ultima attività</th><th>Sessioni valide</th></tr></thead><tbody>
        {data.users.map(user=><tr key={user.id}><td>{user.email}</td><td>{user.plan??'Nessun piano attivo'}</td><td><span className={user.onlineSessions>0?'presence-online':''}>{user.onlineSessions>0?'Attivo':user.validSessions>0?'Sessione valida':'Non connesso'}</span></td><td>{user.lastSeenAt?date(user.lastSeenAt):'Non ancora rilevata'}</td><td>{user.validSessions}</td></tr>)}
      </tbody></table></div>
      {data.users.length===0&&<p>Nessun utente registrato.</p>}
      {data.registeredUsers>data.users.length&&<p>Mostrati i primi {data.users.length} utenti, ordinati per presenza e attività recente, su {data.registeredUsers} registrati.</p>}
      <p>I conteggi per stato riguardano le analisi ancora presenti. L’utilizzo mensile conserva anche le analisi eliminate, a partire dall’introduzione delle quote. Il piano commerciale non rappresenta i privilegi Admin.</p>
    </>}
  </section>;
}
