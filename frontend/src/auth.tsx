import React, {useEffect, useState} from 'react';

export const API = import.meta.env.VITE_API_URL ?? '';
export type Me = {id:string,email:string,roles:string[],plan:string,bypass:boolean,
  entitlements:Record<string,{enabled:boolean|null,limit:number|null}>,
  usage:{analysesStarted:number,reservedMinutes:number,analyzedMinutes:number,storageBytes:number}};
let accessToken:string|null=null;
let refreshing:Promise<boolean>|null=null;

async function refresh():Promise<boolean>{
  if(!refreshing) refreshing=(async()=>{
    try{
      const response=await window.fetch(`${API}/auth/refresh`,{method:'POST',credentials:'include',headers:{'X-BasketVision-CSRF':'1'}});
      if(!response.ok){accessToken=null;return false;}
      accessToken=(await response.json()).accessToken; return true;
    }catch{return false;}
    finally{refreshing=null;}
  })();
  return refreshing;
}

export async function apiFetch(input:string, init:RequestInit={}):Promise<Response>{
  const send=()=>window.fetch(input,{...init,credentials:'include',headers:{...Object.fromEntries(new Headers(init.headers)),Authorization:`Bearer ${accessToken??''}`}});
  let response=await send();
  if(response.status===401){
    if(await refresh()) response=await send();
    if(response.status===401) window.dispatchEvent(new Event('session-expired'));
  }
  return response;
}

const featureNames:Record<string,string>={MaxAnalysesPerMonth:'analisi mensili',MaxConcurrentJobs:'analisi contemporanee',MaxVideoDurationMinutes:'durata in minuti',MaxStorageBytes:'spazio video',VideoAnalysis:'analisi video',AdvancedEvents:'eventi avanzati'};
export async function errorMessage(response:Response){
  const text=await response.text();
  try{
    const value=JSON.parse(text);
    if(value.code==='PLAN_LIMIT_EXCEEDED') return `Limite del piano superato: ${featureNames[value.feature]??value.feature}. Limite: ${value.limit}; utilizzo richiesto: ${value.current}.`;
    if(value.code==='FEATURE_NOT_AVAILABLE') return `Il piano attivo non include ${featureNames[value.feature]??value.feature}.`;
    return value.message??value.title??text;
  }catch{return text||`Operazione non riuscita (${response.status}).`;}
}

export function Session({children}:{children:(me:Me,reload:()=>Promise<void>,logout:()=>Promise<void>)=>React.ReactNode}){
  const [me,setMe]=useState<Me|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  async function reload(){
    const response=await apiFetch(`${API}/auth/me`);
    if(response.ok) setMe(await response.json());
  }
  useEffect(()=>{
    const expired=()=>{setMe(null);setError('Sessione scaduta. Accedi nuovamente.');};
    window.addEventListener('session-expired',expired);
    (async()=>{try{if(await refresh()) await reload();}finally{setLoading(false);}})();
    const timer=setInterval(async()=>{if(accessToken && await refresh()) await reload();},10*60*1000);
    return()=>{clearInterval(timer);window.removeEventListener('session-expired',expired);};
  },[]);
  async function logout(){
    const response=await apiFetch(`${API}/auth/logout`,{method:'POST'});
    if(!response.ok && response.status!==401){setError(await errorMessage(response));return;}
    accessToken=null;setMe(null);
  }
  async function login(event:React.FormEvent<HTMLFormElement>){
    event.preventDefault();setBusy(true);setError('');
    const form=new FormData(event.currentTarget);
    try{
      const response=await window.fetch(`${API}/auth/login`,{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:form.get('email'),password:form.get('password')})});
      if(!response.ok){setError(await errorMessage(response));return;}
      accessToken=(await response.json()).accessToken;
      await reload();
    }catch{setError('Impossibile contattare il server. Riprova.');}
    finally{setBusy(false);}
  }
  if(loading) return <main><p>Caricamento sessione…</p></main>;
  if(!me) return <main className="login"><section className="card"><h1>BasketVision</h1><h2>Accedi</h2><form onSubmit={login}><label>Email<input name="email" type="email" autoComplete="username" required/></label><label>Password<input name="password" type="password" autoComplete="current-password" required/></label><button disabled={busy}>{busy?'Accesso…':'Accedi'}</button></form>{error&&<p role="alert">{error}</p>}</section></main>;
  return <>{error&&<p role="alert">{error}</p>}{children(me,reload,logout)}</>;
}

export function AccountPanel({me,reload,logout}:{me:Me,reload:()=>Promise<void>,logout:()=>Promise<void>}){
  const [users,setUsers]=useState<{id:string,email:string,subscription?:{plan:string}}[]>([]);
  const [plans,setPlans]=useState<{id:string,name:string}[]>([]);
  const [userId,setUserId]=useState('');
  const [planId,setPlanId]=useState('');
  const [message,setMessage]=useState('');
  const isAdmin=me.roles.includes('Admin');
  const loadAdmin=async()=>{
    const [u,p]=await Promise.all([apiFetch(`${API}/api/admin/users`),apiFetch(`${API}/api/admin/plans`)]);
    if(u.ok) setUsers(await u.json());if(p.ok) setPlans(await p.json());
  };
  useEffect(()=>{if(isAdmin) loadAdmin().catch(()=>setMessage('Caricamento amministrazione non riuscito.'));},[isAdmin]);
  const allowed=(feature:string)=>me.bypass||me.entitlements[feature]?.enabled===true;
  const quota=me.bypass?'illimitate':(me.entitlements.MaxAnalysesPerMonth?.limit??0);
  return <section className="card"><div className="section-heading"><div><h2>{me.email}</h2><p>Piano: <b>{me.bypass?'Unlimited — Admin':me.plan}</b> · {me.usage.analysesStarted} / {quota} analisi usate questo mese (UTC)</p><p>{me.usage.analyzedMinutes.toFixed(1)} minuti completati · {me.usage.reservedMinutes.toFixed(1)} minuti richiesti · {(me.usage.storageBytes/1024/1024).toFixed(1)} MB video</p></div><button onClick={logout}>Esci</button></div>
    <div className="actions">{[['VideoAnalysis','Analisi video'],['AdvancedEvents','Eventi avanzati'],['ExportCsv','Export CSV'],['ExportPdf','Export PDF']].map(([key,label])=><span className={allowed(key)?'feature':'feature locked'} key={key}>{label}: {allowed(key)?(key.startsWith('Export')?'incluso, in sviluppo':'incluso'):'🔒 bloccato dal piano'}</span>)}</div>
    {isAdmin&&<details><summary>Gestione piani utenti</summary><form onSubmit={async e=>{e.preventDefault();try{const r=await apiFetch(`${API}/api/admin/users/${userId}/subscription`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({planId,endsAt:null})});setMessage(r.ok?'Piano aggiornato.':await errorMessage(r));if(r.ok){await loadAdmin();await reload();}}catch{setMessage('Aggiornamento non riuscito.');}}}><select required value={userId} onChange={e=>setUserId(e.target.value)}><option value="">Seleziona utente</option>{users.map(u=><option key={u.id} value={u.id}>{u.email} — {u.subscription?.plan??'nessun piano'}</option>)}</select><select required value={planId} onChange={e=>setPlanId(e.target.value)}><option value="">Seleziona piano</option>{plans.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select><button>Assegna piano</button></form>{message&&<p role="status">{message}</p>}</details>}
  </section>;
}
