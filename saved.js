const preferenceUrl=new URL('./preference.js',import.meta.url);
preferenceUrl.searchParams.set('v','feedback-v1');
await import(preferenceUrl.href);

const list=document.querySelector('#saved-list');
const empty=document.querySelector('#saved-empty');
const count=document.querySelector('#saved-count');
const search=document.querySelector('#saved-search');
const pageCache=new Map();
let renderGeneration=0;

function clean(value){return String(value||'').replace(/\s+/g,' ').trim();}
function escapeHtml(value){return clean(value).replace(/[&<>'"]/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));}
function formatDate(iso){const time=Date.parse(iso||'');if(!Number.isFinite(time))return'';return new Intl.DateTimeFormat('zh-TW',{dateStyle:'medium',timeStyle:'short'}).format(new Date(time));}
function savedItems(){return typeof window.ai3dBookmarkList==='function'?window.ai3dBookmarkList():[];}

function fetchDocument(url){
  if(!url)return Promise.resolve(null);
  if(pageCache.has(url))return pageCache.get(url);
  const request=fetch(url,{credentials:'same-origin'}).then(async response=>{
    if(!response.ok)return null;
    return new DOMParser().parseFromString(await response.text(),'text/html');
  }).catch(()=>null);
  pageCache.set(url,request);
  return request;
}

function candidateReportPages(item){
  const report=clean(item.reportUrl);if(!report)return[];
  const pages=[report];
  const category=clean(item.category);
  if(category){try{pages.push(new URL(`${category}/`,report).href);}catch(_){}}
  return [...new Set(pages)];
}

async function imageFromReportPage(url,id){
  const doc=await fetchDocument(url);if(!doc)return null;
  const card=[...doc.querySelectorAll('[data-intel-id]')].find(node=>clean(node.dataset.intelId)===clean(id));
  const img=card?.querySelector('figure.case-preview img[src]');
  if(!img)return null;
  try{return{src:new URL(img.getAttribute('src'),url).href,alt:clean(img.getAttribute('alt'))};}catch(_){return null;}
}

async function resolveBookmarkImage(item){
  if(clean(item.imageUrl))return{src:clean(item.imageUrl),alt:clean(item.imageAlt)};
  for(const url of candidateReportPages(item)){
    const image=await imageFromReportPage(url,item.id);
    if(image)return image;
  }
  return null;
}

function hydrateBookmarkImage(article,item,generation){
  const media=article.querySelector('.saved-card-media');
  const img=media?.querySelector('img');
  if(!media||!img)return;
  resolveBookmarkImage(item).then(image=>{
    if(generation!==renderGeneration||!article.isConnected||!image?.src)return;
    img.src=image.src;
    img.alt=image.alt||`${clean(item.title||item.id)} 文章圖片`;
    media.href=clean(item.source)||clean(item.reportUrl)||image.src;
    media.hidden=false;
    article.classList.add('has-image');
    img.addEventListener('error',()=>{media.hidden=true;article.classList.remove('has-image');},{once:true});
  });
}

function render(){
  const generation=++renderGeneration;
  const query=clean(search?.value).toLowerCase();
  const all=savedItems();
  const visible=all.filter(item=>{
    if(!query)return true;
    return [item.title,item.summary,item.category,item.subcategory,item.reportDate].map(clean).join(' ').toLowerCase().includes(query);
  });
  if(count)count.textContent=String(all.length);
  if(!list||!empty)return;
  list.replaceChildren();
  empty.hidden=all.length!==0;
  if(all.length===0)return;

  if(visible.length===0){
    const noMatch=document.createElement('div');noMatch.className='saved-no-match';noMatch.textContent='沒有符合搜尋條件的收藏。';list.append(noMatch);return;
  }

  visible.forEach(item=>{
    const article=document.createElement('article');article.className='saved-card';article.dataset.intelId=clean(item.id);
    const meta=[clean(item.reportDate),clean(item.category),clean(item.subcategory)].filter(Boolean).map(escapeHtml).join(' · ');
    article.innerHTML=`
      <div class="saved-card-layout">
        <a class="saved-card-media" href="#" target="_blank" rel="noopener noreferrer" hidden>
          <img alt="" loading="lazy" decoding="async">
        </a>
        <div class="saved-card-content">
          <div class="saved-card-meta">${meta||'已收藏情報'}</div>
          <h2>${escapeHtml(item.title||item.id)}</h2>
          ${item.summary?`<p class="saved-card-summary">${escapeHtml(item.summary)}</p>`:''}
          <div class="saved-card-footer">
            <span class="saved-at">收藏於 ${escapeHtml(formatDate(item.savedAt))}</span>
            <div class="saved-card-actions">
              ${item.reportUrl?`<a href="${escapeHtml(item.reportUrl)}">查看日報</a>`:''}
              ${item.source?`<a href="${escapeHtml(item.source)}" target="_blank" rel="noopener noreferrer">開啟來源</a>`:''}
              <button type="button" class="saved-remove" aria-label="取消收藏 ${escapeHtml(item.title||item.id)}" title="取消收藏">★ 已收藏</button>
            </div>
          </div>
        </div>
      </div>`;
    article.querySelector('.saved-remove')?.addEventListener('click',()=>{
      window.ai3dBookmarkRemove?.(item.id);
      render();
    });
    list.append(article);
    hydrateBookmarkImage(article,item,generation);
  });
}

search?.addEventListener('input',render);
window.addEventListener('ai3d:bookmark-change',render);
window.addEventListener('storage',event=>{if(event.key==='ai3d-bookmarks-v1')render();});
render();
