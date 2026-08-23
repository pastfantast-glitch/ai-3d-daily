const LEGACY_20260823_RULES=[
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

function legacyIdentify20260823(card){
  const href=[...card.querySelectorAll('a.source')].map(a=>a.href).join(' ');
  const title=card.querySelector('h2,h3,h4')?.textContent||'';
  for(const [id,hrefs,titles] of LEGACY_20260823_RULES){
    if(hrefs.some(k=>href.includes(k))||titles.some(k=>title.includes(k)))return id;
  }
  return null;
}

function reportDate(){
  return document.body.dataset.reportDate||
    document.querySelector('.week-asof')?.textContent.trim()||
    document.querySelector('.topline span:last-child')?.textContent.trim()||'';
}

function canonicalCards(){
  return [...document.querySelectorAll('.top-item,.more-card,#top .news,.category-news')];
}

function renderAnalysis(card,record){
  const body=card.querySelector('details .detail-body');
  if(!record||!body)return;
  body.replaceChildren();
  record.full_analysis.forEach(block=>{
    const h=document.createElement('h4');
    h.textContent=block.label;
    const p=document.createElement('p');
    p.textContent=block.text;
    body.append(h,p);
  });
  card.dataset.canonicalRendered='1';
}

function makeVisual(entry){
  const fig=document.createElement('figure');
  fig.className='case-preview';
  fig.dataset.intelId=entry.id;
  fig.dataset.intelRole='visual';
  fig.dataset.visualId=entry.id;

  const a=document.createElement('a');
  a.href=entry.page_url;
  a.target='_blank';
  a.rel='noopener noreferrer';
  a.title='開啟原始案例';

  const img=document.createElement('img');
  img.src=new URL(entry.asset_path,import.meta.url).href;
  img.alt=`${entry.label||'SOURCE PREVIEW'} preview`;
  img.loading='lazy';
  img.decoding='async';
  img.addEventListener('error',()=>{fig.style.display='none';},{once:true});
  a.append(img);
  fig.append(a);

  const cap=document.createElement('figcaption');
  const badge=document.createElement('span');
  badge.textContent=entry.label||'SOURCE PREVIEW';
  cap.append(badge,document.createTextNode(' · Local visual evidence · 點圖開啟原始來源'));
  fig.append(cap);
  return fig;
}

function renderVisual(card,entry){
  const existing=card.querySelector('figure.case-preview');
  if(!entry)return; // Historical static preview must never be removed by a newer manifest.

  const expected=new URL(entry.asset_path,import.meta.url).href;
  if(existing){
    existing.dataset.intelId=entry.id;
    existing.dataset.intelRole='visual';
    existing.dataset.visualId=entry.id;
    const img=existing.querySelector('img');
    const a=existing.querySelector('a');
    if(img&&img.src!==expected)img.src=expected;
    if(a&&a.href!==entry.page_url)a.href=entry.page_url;
    return;
  }

  const fig=makeVisual(entry);
  const impact=card.querySelector('.quick-impact');
  if(impact)impact.before(fig);
  else{
    const details=card.querySelector('details');
    if(details)details.before(fig);else card.append(fig);
  }
}

async function loadVisualManifest(date){
  const snapshotUrl=new URL(`./assets/visual/${date}/manifest.json`,import.meta.url);
  try{
    const r=await fetch(snapshotUrl,{cache:'no-store'});
    if(r.ok){
      const m=await r.json();
      if(m.date===date)return m;
    }
  }catch(_){}

  // Transitional fallback for a release that has not yet been migrated to a
  // date-scoped manifest. It is accepted only when the root manifest date matches.
  try{
    const rootUrl=new URL('./assets/visual/manifest.json',import.meta.url);
    const r=await fetch(rootUrl,{cache:'no-store'});
    if(!r.ok)return {date,entries:[]};
    const m=await r.json();
    return m.date===date?m:{date,entries:[]};
  }catch(_){return {date,entries:[]};}
}

export async function hydrateCanonicalAnalysis(){
  const date=reportDate();
  if(!date)return;
  try{
    const dataUrl=new URL(`./data/daily/${date}.json`,import.meta.url);
    const [data,manifest]=await Promise.all([
      fetch(dataUrl,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(`canonical ${r.status}`);return r.json();}),
      loadVisualManifest(date)
    ]);

    const records=new Map(data.items.map(x=>[x.id,x]));
    const visuals=new Map((manifest.entries||[])
      .filter(x=>x.status==='ok')
      .map(x=>[x.id,x]));

    canonicalCards().forEach(card=>{
      let id=card.dataset.intelId||'';
      // Compatibility only for the pre-stable-ID 2026-08-23 snapshot. New dates
      // must ship data-intel-id in source markup and pass release preflight.
      if(!id&&date==='2026-08-23')id=legacyIdentify20260823(card)||'';
      if(!id)return;
      card.dataset.intelId=id;
      card.dataset.intelRole='card';
      renderAnalysis(card,records.get(id));
      renderVisual(card,visuals.get(id));
    });
  }catch(err){
    console.warn('Canonical intelligence hydration skipped',err);
  }
}
