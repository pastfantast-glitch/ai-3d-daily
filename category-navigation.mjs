import {categories,categoryItems,visibleCategories,validateCategories} from './category-model.mjs';
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
export async function prepareNavigation(nav,date){
 const read=async path=>{const r=await fetch(path,{cache:'no-cache',signal:AbortSignal.timeout(15000)});if(!r.ok)throw Error('分類資料無法讀取');return r.json();};
 const [settings,data]=await Promise.all([read('config/collection-admin.json'),read(`data/daily/${date}.json`)]);
 if(data.date!==date)throw Error('分類資料日期不一致');
 const rows=categories(settings);validateCategories(rows,settings.sources);
 const items=[...(data.items||[]),...(data.topic_items||[])],shown=visibleCategories(settings,items);
 const select=document.querySelector('#today-category');if(select){select.replaceChildren(new Option('全部分類','all'),...shown.map(c=>new Option(c.name,c.id)));}
 for(const card of document.querySelectorAll('.today-library [data-intel-role="card"]')){const item=items.find(i=>i.id===card.dataset.intelId);if(item)card.dataset.categoryIds=rows.filter(c=>categoryItems([item],c,settings).length).map(c=>c.id).join(' ');}
 const registry=new Map(rows.map(c=>[c.id,c])),templates=new Map();
 for(const card of document.querySelectorAll('main.home-main [data-intel-role="card"]'))if(!templates.has(card.dataset.intelId))templates.set(card.dataset.intelId,card.cloneNode(true));
 for(const old of nav.querySelectorAll('a[data-category]'))old.remove();
 const anchor=nav.querySelector('.global-history-link');
 for(const c of shown){const a=el('a',c.name,'global-category-link');a.href=`?view=${c.id}`;a.dataset.category=c.id;anchor.before(a);}
 const grid=document.querySelector('.category-nav-grid')||document.querySelector('.category-nav-card')?.parentElement;
 if(grid){grid.replaceChildren();for(const c of shown){const a=el('a',undefined,'category-nav-card');a.href=`?view=${c.id}`;a.dataset.category=c.id;a.append(el('h3',c.name),el('p',c.description),el('span',`${categoryItems(items,c,settings).length} 篇`));grid.append(a);}}
 return {has:id=>registry.has(id),label:id=>registry.get(id)?.name,render(id){
  const c=registry.get(id);if(!c)return null;
  const matches=categoryItems(items,c,settings),main=el('main',undefined,'page category-main managed-category'),header=el('header');
  header.append(el('h1',c.name),el('p',c.description),el('p',`最新發布：${date}・本分類 ${matches.length} 篇（跨分類不重複計入本期總數）`));
  const search=el('input');search.type='search';search.placeholder='搜尋本分類';search.setAttribute('aria-label','搜尋本分類');
  const list=el('div',undefined,'topic-grid'),more=el('button','顯示更多'),count=el('p'),empty=el('p','本期尚無符合此分類的已發布文章。','category-empty');count.setAttribute('aria-live','polite');let limit=10;
  const draw=()=>{list.replaceChildren();const query=search.value.trim().toLowerCase(),found=matches.filter(i=>[i.title,i.summary,i.subcategory].join(' ').toLowerCase().includes(query));
   for(const item of found.slice(0,limit)){let card=templates.get(item.id)?.cloneNode(true);
    if(!card){card=el('article',undefined,'home-card more-card');card.dataset.intelRole='card';card.dataset.intelId=item.id;card.dataset.libraryId=item.id;card.append(el('h2',item.title),el('p',item.summary,'summary'),el('p',`來源日期 ${item.source_published_at||'待核對'}`,'article-date'));const a=el('a','原始來源');a.href=item.source_url;a.target='_blank';a.rel='noopener noreferrer';card.append(a);const d=el('details'),s=el('summary','完整分析');d.append(s);for(const b of item.full_analysis||[])d.append(el('h4',b.label),el('p',b.text));card.append(d);}
    card.hidden=false;card.removeAttribute('id');card.querySelector('.top-no')?.remove();card.classList.remove('top-item');card.classList.add('more-card');for(const d of card.querySelectorAll('details'))d.open=false;list.append(card);
   }
   empty.hidden=found.length>0;more.hidden=found.length<=limit;count.textContent=`顯示 ${Math.min(limit,found.length)}／${found.length} 篇`;
  };
  search.oninput=()=>{limit=10;draw();};more.onclick=()=>{limit+=10;draw();};main.append(header,search,list,empty,more,count);draw();return main;
 }};
}
