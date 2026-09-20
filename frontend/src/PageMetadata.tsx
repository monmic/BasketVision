import {useEffect} from 'react';

export const publicTitle = 'BasketVision | Analisi video automatica per il basket';
export const publicDescription = 'Analizza i video delle partite di basket con la computer vision: rilevamento di persone e palla, tracking e report da esplorare direttamente sul video.';
export const publicUrl = 'https://basketvision.it/';
export const structuredData = {'@context':'https://schema.org','@graph':[
  {'@type':'WebSite',name:'BasketVision',url:publicUrl,inLanguage:'it'},
  {'@type':'SoftwareApplication',name:'BasketVision',url:publicUrl,applicationCategory:'SportsApplication',operatingSystem:'Web',description:publicDescription,inLanguage:'it'},
]};
export function isPublicHome(){return window.location.pathname==='/' && !window.location.search;}
export function PageMetadata({publicPage}:{publicPage:boolean}){
  useEffect(()=>{
    document.title=publicPage?publicTitle:'Area riservata | BasketVision';
    const set=(selector:string,content:string)=>document.querySelector(selector)?.setAttribute('content',content);
    set('meta[name="robots"]',publicPage?'index, follow':'noindex, nofollow');
    set('meta[name="description"]',publicPage?publicDescription:'Accedi alla tua area riservata BasketVision.');
    set('meta[property="og:title"]',document.title);
    set('meta[property="og:description"]',publicPage?publicDescription:'Area riservata BasketVision.');
    const canonical=document.querySelector('link[rel="canonical"]');
    if(publicPage){
      if(!canonical){const link=document.createElement('link');link.rel='canonical';link.href=publicUrl;document.head.append(link);}
      if(!document.getElementById('bv-structured-data')){const script=document.createElement('script');script.id='bv-structured-data';script.type='application/ld+json';script.textContent=JSON.stringify(structuredData);document.head.append(script);}
    }else{canonical?.remove();document.getElementById('bv-structured-data')?.remove();}
  },[publicPage]);
  return null;
}
