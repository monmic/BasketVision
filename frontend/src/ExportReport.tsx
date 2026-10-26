import React,{useState} from 'react';
import {API,apiFetch,errorMessage} from './auth';

export function ExportReport({gameId,analysisId}:{gameId:string,analysisId:string}){
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState('');
 async function download(){
   setBusy(true);setError('');
   try{
     const response=await apiFetch(`${API}/api/games/${gameId}/report.csv?analysisId=${analysisId}`);
     if(!response.ok){setError(await errorMessage(response));return}
     const url=URL.createObjectURL(await response.blob());
     const link=document.createElement('a');
     link.href=url;link.download=`basketvision-${gameId}-${analysisId}.csv`;
     document.body.appendChild(link);link.click();link.remove();
     setTimeout(()=>URL.revokeObjectURL(url),1000);
   }catch{setError('Esportazione non riuscita. Riprova.')}finally{setBusy(false)}
 }
 return <div><button disabled={busy} onClick={download}>{busy?'Esportazione…':'Esporta report CSV'}</button>{error&&<p role="alert">{error}</p>}</div>
}
