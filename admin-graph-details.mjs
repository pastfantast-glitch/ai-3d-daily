const el=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
const labels={awaiting_review:'待審稿',rejected:'待修正',held:'已暫緩',recheck_required:'已審，使用前待複核',date_ineligible:'日期不符',source_unavailable:'來源暫時無法讀取',source_disabled:'來源或主題未啟用',published:'已發布'};
function link(text,url){const a=el('a',text);try{const u=new URL(url);if(u.protocol!=='https:')return el('span',text);a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';return a;}catch{return el('span',text);}}
export function sourceFor(row,settings){
  if(row.source_id)return settings.sources.find(s=>s.id===row.source_id);
  try{const host=new URL(row.source_url).hostname.replace(/^www\./,'');return settings.sources.find(s=>new URL(s.base_url).hostname.replace(/^www\./,'')===host);}catch{return undefined;}
}
export function scopedArticles(key,data){
  const [kind,id]=key.split(':'),ops=data.operations;
  const rows=id==='reserve'&&kind==='stage'?ops?.reserve||[]:id==='review'&&kind==='stage'?ops?.queue||[]:[...(ops?.queue||[]),...(ops?.reserve||[]),...(ops?.published_items||[])];
  return rows.filter(row=>kind==='source'?sourceFor(row,data.settings)?.id===id:kind==='topic'?(row.topic_ids||sourceFor(row,data.settings)?.topic_ids||[]).includes(id):true);
}
export function createGraphDetails(){
  const views=new Map();
  return function render(parent,key,data){
    const state=views.get(key)||{query:'',filter:'all',limit:10,article:null,scroll:0};views.set(key,state);
    const area=el('section',undefined,'graph-detail-content');parent.append(area);
    const draw=()=>{
      area.replaceChildren();const ops=data.operations,rows=scopedArticles(key,data);
      if(key==='stage:publish'||key==='stage:evidence'){
        area.append(el('h4','今日流程紀錄'),el('p',`${ops?.date||'未知日期'} · ${ops?.state||'狀態未知'}`));
        for(const issue of ops?.issues||[])area.append(el('p',issue,'error'));
        if(ops?.recovery)area.append(el('p',ops.recovery.next_step||ops.recovery.reason||''));
        for(const run of ops?.runs||[])area.append(link(`${run.name} · ${run.conclusion||run.status}`,run.url));
        if(!ops?.runs?.length)area.append(el('p',ops?.state==='DONE'?'本期已有核對通過的發布收據。':'尚未取得執行紀錄。'));
        if(ops?.daily_url)area.append(link('開啟本期日報',ops.daily_url));
      }
      if(state.article){
        const row=rows.find(x=>x.source_url===state.article);if(!row){state.article=null;draw();return;}
        const back=el('button','返回文章清單');back.onclick=()=>{state.article=null;draw();};area.append(back,el('h4',row.title||row.id),el('span',labels[row.state]||row.state||'紀錄','pill'),el('p','來源日期：'+(row.source_date||'未知')),link('開啟原始來源',row.source_url));
        if(row.summary)area.append(el('p',row.summary));
        for(const b of row.full_analysis||[])area.append(el('h5',b.label),el('p',b.text));
        for(const issue of row.errors||[])area.append(el('p',issue,'error'));
        if(row.evidence_refs?.length)area.append(el('p','來源段落引用：'+row.evidence_refs.join('、')));
        area.append(el('p',row.state==='published'?'此稿已完成發布。':'此畫面提供狀態與引用；正文核對及核准由既有審稿任務執行。','help'));
        if(row.source_run_id||ops?.source_run_url)area.append(link('查看來源證據執行紀錄',row.source_run_id?'https://github.com/pastfantast-glitch/ai-3d-daily/actions/runs/'+row.source_run_id:ops.source_run_url));return;
      }
      area.append(el('h4','相關文章'));
      const search=el('input');search.type='search';search.placeholder='搜尋此節點文章';search.setAttribute('aria-label','搜尋節點文章');search.value=state.query;
      const filter=el('select');filter.setAttribute('aria-label','節點文章狀態');
      for(const [value,text]of [['all','全部狀態'],...Object.entries(labels)]){const o=el('option',text);o.value=value;filter.append(o);}filter.value=state.filter;
      const count=el('p',undefined,'help'),list=el('div',undefined,'graph-article-list'),more=el('button','顯示更多文章');
      const fill=()=>{list.replaceChildren();const matches=rows.filter(r=>(state.filter==='all'||r.state===state.filter)&&[r.title,r.source_url,...(r.errors||[])].join(' ').toLowerCase().includes(state.query.toLowerCase()));count.textContent=`符合 ${matches.length} 篇 · 資料日期 ${ops?.queue_date||ops?.date||'未知'}`;
        for(const row of matches.slice(0,state.limit)){const button=el('button',undefined,'graph-article-row');button.append(el('strong',row.title||row.id),el('small',`${labels[row.state]||row.state||'紀錄'} · ${row.source_date||'日期未知'}`));button.onclick=()=>{state.scroll=list.scrollTop;state.article=row.source_url;draw();};list.append(button);}
        if(!matches.length)list.append(el('p',ops?'沒有符合條件的文章。':'尚未取得資料，不能確認是否有稿件。'));more.hidden=matches.length<=state.limit;list.scrollTop=state.scroll;};
      search.oninput=()=>{state.query=search.value;state.limit=10;state.scroll=0;fill();};filter.onchange=()=>{state.filter=filter.value;state.limit=10;state.scroll=0;fill();};more.onclick=()=>{state.limit+=10;fill();};area.append(search,filter,count,list,more);fill();
    };draw();
  };
}
