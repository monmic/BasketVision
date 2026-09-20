import {readFile,writeFile} from 'node:fs/promises';
import {createServer} from 'vite';
import React from 'react';
import {renderToString} from 'react-dom/server';

const vite=await createServer({server:{middlewareMode:true},appType:'custom'});
try{
  const {LandingPage}=await vite.ssrLoadModule('/src/LandingPage.tsx');
  const {structuredData}=await vite.ssrLoadModule('/src/PageMetadata.tsx');
  const template=await readFile('dist/index.html','utf8');
  // Preserve React text boundaries for hydrateRoot on the client.
  const landing=renderToString(React.createElement(LandingPage));
  const publicHtml=template.replace('<div id="root"></div>',`<div id="root">${landing}</div>`)
    .replace('</head>',`<script id="bv-structured-data" type="application/ld+json">${JSON.stringify(structuredData).replace(/</g,'\\u003c')}</script></head>`);
  await writeFile('dist/index.html',publicHtml);
  const privateHtml=template.replace('<title>BasketVision | Analisi video automatica per il basket</title>','<title>Area riservata | BasketVision</title>')
    .replace('content="index, follow"','content="noindex, nofollow"')
    .replace(/\s*<link rel="canonical"[^>]+>/,'')
    .replace(/<meta name="description"[^>]+>/,'<meta name="description" content="Accedi alla tua area riservata BasketVision." />')
    .replace(/\s*<meta (?:property="og:[^"]+"|name="twitter:[^"]+")[^>]+>/g,'');
  await writeFile('dist/private.html',privateHtml);
  console.log('Prerendered public homepage and noindex private shell.');
}finally{await vite.close();}
