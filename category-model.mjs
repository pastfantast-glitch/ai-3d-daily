// Navigation is an editable view of approved articles, never publication authority.
export const BUILTINS=['ai-generation','3d-production','3d-animation','engine-art','emerging-case','blender-dcc'];
const names=['AI 生成','3D 製作','3D 動作','遊戲引擎','新技術 / Case','Blender / DCC'];
export function categories(settings){
 if(settings.navigation)return structuredClone(settings.navigation);
 return [...BUILTINS.map((id,order)=>({id,name:names[order],description:'沿用既有分類，可增加關鍵字與人工指定文章。',enabled:true,visible:true,hide_empty:false,order,include_terms:[],exclude_terms:[],manual_urls:[],excluded_urls:[],source_ids:settings.sources.map(s=>s.id)})),
 ...settings.topics.filter(t=>t.id!=='ai-3d'&&!BUILTINS.includes(t.id)).map((t,i)=>({...Object.fromEntries(['id','name','description','enabled','include_terms','exclude_terms'].map(k=>[k,t[k]])),visible:true,hide_empty:true,order:6+i,source_ids:settings.sources.filter(s=>s.topic_ids.includes(t.id)).map(s=>s.id),manual_urls:[],excluded_urls:[]}))];
}
export function validateCategories(rows,sources){
 const need=(ok,message)=>{if(!ok)throw Error(message);},ids=new Set(),sourceIds=new Set(sources.map(s=>s.id));
 const keys='id,name,description,enabled,visible,hide_empty,order,include_terms,exclude_terms,source_ids,manual_urls,excluded_urls'.split(',').sort().join();
 need(Array.isArray(rows)&&rows.length>=1&&rows.length<=30,'分類數量需為 1–30');
 for(const c of rows){
  need(c&&Object.keys(c).sort().join()===keys,'分類欄位不正確');
  need(typeof c.id==='string'&&/^[a-z0-9][a-z0-9-]{1,47}$/.test(c.id)&&!['top5','ai-3d','history','admin','saved','topics','categories'].includes(c.id)&&!ids.has(c.id),'分類代號需唯一，不能使用保留網址');ids.add(c.id);
  for(const [k,n,empty]of [['name',80,false],['description',500,true]])need(typeof c[k]==='string'&&c[k].length<=n&&(empty||c[k].trim())&&!/[\x00-\x1f]/.test(c[k]),'分類名稱或說明不正確');
  for(const k of ['enabled','visible','hide_empty'])need(typeof c[k]==='boolean','分類開關不正確');
  need(Number.isInteger(c.order)&&c.order>=0&&c.order<=999,'排序需為 0–999');
  for(const k of ['include_terms','exclude_terms'])need(Array.isArray(c[k])&&c[k].length<=30&&c[k].every(s=>typeof s==='string'&&s.trim()&&s.length<=80&&!/[\x00-\x1f]/.test(s)),'關鍵字最多 30 組');
  need(BUILTINS.includes(c.id)||c.include_terms.length>0,'新增分類需要收錄關鍵字');
  need(Array.isArray(c.source_ids)&&c.source_ids.length<=100&&new Set(c.source_ids).size===c.source_ids.length&&c.source_ids.every(id=>sourceIds.has(id)),'分類連線包含不存在或重複來源');
  for(const k of ['manual_urls','excluded_urls'])need(Array.isArray(c[k])&&c[k].length<=200&&new Set(c[k]).size===c[k].length&&c[k].every(s=>{try{const u=new URL(s);return s.length<=1500&&u.protocol==='https:'&&!u.username&&!u.password&&!u.hash;}catch{return false;}}),'人工分類請填有效、唯一的 HTTPS 原文網址（最多 200 筆）');
  need(!c.manual_urls.some(u=>c.excluded_urls.includes(u)),'同一文章不能同時指定加入與排除');
 }
 for(const id of BUILTINS)need(ids.has(id),'既有分類須保留；可停用或隱藏，不能刪除');
 return rows;
}
export function sourceId(item,settings){
 if(item.source_id)return item.source_id;
 try{const host=new URL(item.source_url||item.url).hostname.replace(/^www\./,'');return settings.sources.find(s=>{const h=new URL(s.base_url).hostname.replace(/^www\./,'');return host===h||host.endsWith('.'+h);})?.id;}catch{return null;}
}
export function matchesCategory(item,c,settings){
 if(!c.enabled||c.excluded_urls.includes(item.source_url))return false;
 if(c.manual_urls.includes(item.source_url))return true;
 const text=[item.title,item.summary,item.description,item.article_excerpt,item.subcategory,...(item.tags||[])].filter(Boolean).join(' ').toLowerCase();
 if(c.exclude_terms.some(t=>text.includes(t.toLowerCase())))return false;
 // Historic, approved memberships survive a later source pause/disconnection.
 if((item.navigation_category_ids||[]).includes(c.id))return true;
 if(!c.include_terms.length&&((item.category||item.primary_category)===c.id||(item.topic_ids||[]).includes(c.id)))return true;
 return c.source_ids.includes(sourceId(item,settings))&&c.include_terms.some(t=>text.includes(t.toLowerCase()));
}
export function categoryItems(items,c,settings){const seen=new Set();return items.filter(i=>matchesCategory(i,c,settings)&&!seen.has(i.id||i.source_url)&&seen.add(i.id||i.source_url));}
export function visibleCategories(settings,items){return categories(settings).filter(c=>c.enabled&&c.visible&&(!c.hide_empty||categoryItems(items,c,settings).length)).sort((a,b)=>a.order-b.order||a.id.localeCompare(b.id));}
// Adapter: existing canvas/history/merge tools edit categories without changing
// the immutable collection-topic snapshots in already published editions.
export function projectSettings(raw){
 if(raw?._collection)return structuredClone(raw);
 const rows=categories(raw).sort((a,b)=>a.order-b.order||a.id.localeCompare(b.id));
 return {schema_version:1,_collection:structuredClone(raw),topics:rows.map(c=>({...c,target_items:30,max_age_months:12})),sources:raw.sources.map(s=>({...s,topic_ids:rows.filter(c=>c.source_ids.includes(s.id)).map(c=>c.id)}))};
}
export function unprojectSettings(view){
 if(!view?._collection)return view;
 const result=structuredClone(view._collection);
 result.navigation=view.topics.map(({target_items,max_age_months,...c})=>({...c,source_ids:view.sources.filter(s=>s.topic_ids.includes(c.id)).map(s=>s.id)}));
 result.sources=view.sources.map(s=>({...s,topic_ids:(result.sources.find(old=>old.id===s.id)?.topic_ids?.length||!s.enabled)?(result.sources.find(old=>old.id===s.id)?.topic_ids||['ai-3d']):['ai-3d']}));
 return result;
}
