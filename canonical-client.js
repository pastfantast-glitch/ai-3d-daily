const RULES=[
['blender-52-geometry-nodes-physics',['geometry-nodes-physics'],['Geometry Nodes Physics']],
['retopoflow-419',['retopoflow'],['RetopoFlow 4.1.9']],
['endfield-hybrid-npr',['project-endfield-character-rendering'],['Arknights: Endfield']],
['procedural-hand-painted-eevee',['hand-painted-look'],['Procedural Hand-Painted EEVEE Shader']],
['blender-52-lts',['blender.org/releases/5-2'],['Blender 5.2 LTS']],
['node-preview-thumbnails',['node-preview'],['Node Preview Thumbnails']],
['geo-nodes-guide',['geo-nodes-guide'],['Geo Nodes Guide']],
['ppeh-tools',['ppeh-tools'],['ppeh_tools']],
['node-wrangler-52-preview',['node_wrangler'],['Node Wrangler 5.2']],
['stylized-pixelated-caustics',[],['Stylized / Pixelated Caustics']],
['material-lighting-nodes',[],['Material Lighting Nodes']]
];
function identify(card){
 const href=[...card.querySelectorAll('a.source')].map(a=>a.href).join(' ');
 const title=card.querySelector('h2,h3,h4')?.textContent||'';
 for(const [id,hrefs,titles] of RULES){if(hrefs.some(k=>href.includes(k))||titles.some(k=>title.includes(k)))return id;}
 return null;
}
function reportDate(){return document.body.dataset.reportDate||document.querySelector('.week-asof')?.textContent.trim()||document.querySelector('.topline span:last-child')?.textContent.trim()||'';}
export async function hydrateCanonicalAnalysis(){
 const date=reportDate(); if(!date)return;
 try{
  const url=new URL(`./data/daily/${date}.json`,import.meta.url);
  const data=await fetch(url,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(r.status);return r.json();});
  const records=new Map(data.items.map(x=>[x.id,x]));
  const cards=[...document.querySelectorAll('.top-item,.more-card,#top .news,.category-news')];
  cards.forEach(card=>{
   const id=card.dataset.intelId||identify(card); if(!id)return; card.dataset.intelId=id;
   const rec=records.get(id),body=card.querySelector('details .detail-body'); if(!rec||!body)return;
   body.replaceChildren();
   rec.full_analysis.forEach(block=>{const h=document.createElement('h4');h.textContent=block.label;const p=document.createElement('p');p.textContent=block.text;body.append(h,p);});
   card.dataset.canonicalRendered='1';
  });
 }catch(err){console.warn('Canonical intelligence hydration skipped',err);}
}
