import {connectTopic,connectionState,stageData} from './admin-graph-model.mjs';
const el=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
const svgEl=tag=>document.createElementNS('http://www.w3.org/2000/svg',tag);
export function mountGraph({onChange,onEdit,onAdd,onSave,onDiscard,onView,notify}) {
  const root=document.querySelector('#graph-view'),viewport=root.querySelector('.graph-viewport'),space=root.querySelector('.graph-space'),world=root.querySelector('.graph-world'),edges=root.querySelector('.graph-edges'),nodes=root.querySelector('.graph-nodes'),inspector=root.querySelector('.graph-inspector-body');
  let data=null,selected=null,armed=null,zoom=1,positions=new Map(),visible=[],stageNodes=[],gesture=null,clickBlocked=false;
  const $=s=>root.querySelector(s),label=$('#graph-local-state');
  function action(text,fn,cls){const b=el('button',text,cls);b.type='button';b.onclick=fn;return b;}
  function filtered(){const q=$('#graph-search').value.trim().toLowerCase();return data.settings.sources.filter(s=>(s.name+' '+s.base_url).toLowerCase().includes(q));}
  function pos(key,fallback){if(!positions.has(key))positions.set(key,fallback);return positions.get(key);}
  function bounds(){const entries=[...visible,...stageNodes];const w=Math.max(1650,...entries.map(n=>n.x+n.width+60)),h=Math.max(640,...entries.map(n=>n.y+n.height+60));world.style.width=w+'px';world.style.height=h+'px';space.style.width=w*zoom+'px';space.style.height=h*zoom+'px';edges.setAttribute('width',w);edges.setAttribute('height',h);world.style.transform=`scale(${zoom})`;$('#graph-zoom-label').textContent=Math.round(zoom*100)+'%';}
  function path(from,to,cls,labelText){const p=svgEl('path');const bend=Math.max(70,Math.abs(to.x-from.x)*.5);p.setAttribute('d',`M ${from.x} ${from.y} C ${from.x+bend} ${from.y}, ${to.x-bend} ${to.y}, ${to.x} ${to.y}`);p.setAttribute('class',cls);edges.append(p);if(labelText){const t=svgEl('text');t.setAttribute('x',(from.x+to.x)/2);t.setAttribute('y',(from.y+to.y)/2-9);t.textContent=labelText;edges.append(t);}}
  function paintEdges(){edges.replaceChildren();if(!data)return;const lookup=new Map([...visible,...stageNodes].map(n=>[n.key,n]));
    const wire=(a,b,cls,text)=>{const x=lookup.get(a),y=lookup.get(b);if(x&&y)path({x:x.x+x.width,y:x.y+65},{x:y.x,y:y.y+65},cls,text);};
    for(const s of filtered())for(const id of s.topic_ids){const changed=connectionState(data.activeSettings,s.id,id)==='draft';wire('source:'+s.id,'topic:'+id,'graph-wire '+(changed?'draft ':'')+(selected==='source:'+s.id||selected==='topic:'+id?'highlight ':''));}
    // Ghosts make removed connections visible until activation, not just until saving.
    for(const s of data.activeSettings?.sources||[])for(const id of s.topic_ids)if(data.settings.sources.some(x=>x.id===s.id&&!x.topic_ids.includes(id)))wire('source:'+s.id,'topic:'+id,'graph-wire removed');
    for(const t of data.settings.topics)wire('topic:'+t.id,'stage:filter','graph-wire fixed');
    for(const [a,b,text] of [['filter','evidence',''],['evidence','review',''],['review','reserve','剩餘合格稿'],['review','publish','當期入選'],['reserve','publish','重新核對後']])wire('stage:'+a,'stage:'+b,'graph-wire fixed',text);
    if(gesture?.kind==='connect'){const n=lookup.get('source:'+gesture.source);if(n)path({x:n.x+n.width,y:n.y+65},gesture.to,'graph-wire draft highlight');}
  }
  function select(key){if($('#graph-inline-editor').contains(document.querySelector('#editor-form'))){notify('請先完成或取消右側節點編輯。');return;}selected=key;for(const n of nodes.children)n.classList.toggle('selected',n.dataset.key===key);paintEdges();renderInspector();}
  function connect(source,topic,connected=true){if($('#graph-inline-editor').contains(document.querySelector('#editor-form'))){notify('請先完成或取消右側節點編輯。');return;}try{const next=connectTopic(data.settings,source,topic,connected);armed=null;onChange(next);notify(connected?'連線已加入草稿，儲存並驗證後才能套用。':'連線已移出草稿，現行設定保持不變。');}catch(e){notify(e.message,true);renderInspector();}renderHint();}
  function renderHint(){$('#graph-hint').textContent=armed?`已選取「${data.settings.sources.find(s=>s.id===armed)?.name}」；點主題的輸入接點完成連線，Esc 取消。`:'拖曳節點標題移動；拖曳接點連線，或依序點選來源與主題接點。空白處拖曳可平移。';}
  function node(n,title,subtitle,status,kind){const box=el('article',undefined,'graph-node '+kind);box.dataset.key=n.key;box.style.left=n.x+'px';box.style.top=n.y+'px';box.style.width=n.width+'px';
    const heading=action(title,()=>{if(!clickBlocked)select(n.key);},'graph-node-title');heading.setAttribute('aria-label','選取'+title);heading.onpointerdown=e=>{if(e.button!==0)return;gesture={kind:'node',id:e.pointerId,n,startX:e.clientX,startY:e.clientY,x:n.x,y:n.y};heading.setPointerCapture(e.pointerId);};
    heading.onkeydown=e=>{if(e.altKey&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();n.x=Math.max(30,n.x+(e.key==='ArrowLeft'?-24:e.key==='ArrowRight'?24:0));n.y=Math.max(35,n.y+(e.key==='ArrowUp'?-24:e.key==='ArrowDown'?24:0));positions.set(n.key,{x:n.x,y:n.y});box.style.left=n.x+'px';box.style.top=n.y+'px';bounds();paintEdges();}};
    box.append(el('span',kind==='source'?'來源':kind==='topic'?'收集主題':'固定流程','graph-kind'),heading,el('p',subtitle),el('small',status));box.classList.toggle('selected',selected===n.key);nodes.append(box);return box;
  }
  function render(){if(!data)return;nodes.replaceChildren();visible=[];stageNodes=[];const sources=filtered();
    sources.forEach((s,i)=>{const key='source:'+s.id;const p=pos(key,{x:35,y:55+i*150});const n={key,...p,width:255,height:130};visible.push(n);const m=data.monitor?.sources?.[s.id];const state=!s.enabled?'已暫停':m?.status==='blocked'?'讀取被拒':m?.status==='unavailable'?'讀取失敗':m?.status==='not-scheduled'?'本批未排入':m?'本批已檢查':'尚無紀錄';const box=node(n,s.name,`正文 ${m?.evidence_extracted??'—'} · 核准 ${m?.review_approved??'—'} · 待審 ${m?.awaiting_review??'—'}`,state,'source');box.classList.toggle('muted-node',!s.enabled);box.classList.toggle('warning-node',s.enabled&&['blocked','unavailable'].includes(m?.status));
      const port=action('●',()=>{if(clickBlocked)return;armed=armed===s.id?null:s.id;select(key);renderHint();},'graph-port output');port.setAttribute('aria-label','連接來源 '+s.name);port.onpointerdown=e=>{if(e.button!==0)return;e.stopPropagation();const r=world.getBoundingClientRect();gesture={kind:'connect',id:e.pointerId,source:s.id,startX:e.clientX,startY:e.clientY,to:{x:(e.clientX-r.left)/zoom,y:(e.clientY-r.top)/zoom}};port.setPointerCapture(e.pointerId);};box.append(port);
    });
    data.settings.topics.forEach((t,i)=>{const key='topic:'+t.id,n={key,...pos(key,{x:420,y:55+i*170}),width:255,height:140};visible.push(n);const box=node(n,t.name,`近 ${t.max_age_months} 個月 · 每期目標 ${t.target_items}`,t.enabled?'啟用中':'已暫停','topic');box.classList.toggle('muted-node',!t.enabled);const port=action('●',()=>{if(armed)connect(armed,t.id);else{select(key);notify('先選來源的輸出接點，再選這個主題。');}},'graph-port input');port.dataset.topicInput=t.id;port.setAttribute('aria-label','連接到主題 '+t.name);box.append(port);});
    const layouts={filter:[790,55],evidence:[1100,55],review:[1100,245],reserve:[790,460],publish:[1410,390]};
    for(const s of stageData(data.operations,data.monitor)){const key='stage:'+s.id,[x,y]=layouts[s.id],n={key,...pos(key,{x,y}),width:230,height:140};stageNodes.push(n);node(n,s.name,s.value,'唯讀 · 不可繞過','stage');}
    $('#graph-data-date').textContent=`來源紀錄：${data.monitor?.date||'尚未取得'} · 發布查核：${data.operations?.date||'狀態未知'}（台北時間）`;
    $('#graph-empty').hidden=!!sources.length;label.textContent=data.dirty?'有未儲存草稿；現行設定未改變':data.validation?.draft?'顯示待驗證設定；現行設定尚未改變':'顯示現行設定';$('#graph-save').disabled=!data.dirty||data.busy;$('#graph-discard').disabled=!data.dirty||data.busy;
    bounds();paintEdges();renderInspector();renderHint();
  }
  function renderInspector(){if($('#graph-inline-editor').contains(document.querySelector('#editor-form')))return;inspector.replaceChildren();if(!selected){inspector.append(el('span','NODE DETAILS','eyebrow'),el('h3','選取一個節點'),el('p','來源連到主題，決定收錄範圍。固定流程呈現實際狀態，不會因為拉線就開始收集或批准稿件。'),el('p','紫色實線：既有連線；金色虛線：新增連線；紅色虛線：待移除連線。'),el('p','配置位置只影響畫面；重新整理會回到預設排列。','help'));return;}
    const [kind,id]=selected.split(':');if(kind==='stage'){const s=stageData(data.operations,data.monitor).find(x=>x.id===id);inspector.append(el('span','固定流程 · 唯讀','pill'),el('h3',s.name),el('strong',s.value),el('p',s.note),action('查看詳細紀錄',()=>onView(s.view)));return;}
    const item=(kind==='source'?data.settings.sources:data.settings.topics).find(x=>x.id===id);if(!item){selected=null;renderInspector();return;}inspector.append(el('span',kind==='source'?'來源節點':'主題節點','eyebrow'),el('h3',item.name));
    if(kind==='source'){const m=data.monitor?.sources?.[id],stat=data.metrics?.sources?.[id];inspector.append(el('p',item.base_url,'address'),el('p',`收集紀錄：${data.monitor?.date||'尚無紀錄'} · ${m?.reason||m?.status||'此來源尚未檢查'}`),el('p',`30 日已發布日報累計發布：${stat?.published??'—'} 篇`),el('h4','連接的主題'));
      for(const t of data.settings.topics){const row=el('label',undefined,'graph-binding'),check=el('input');check.type='checkbox';check.checked=item.topic_ids.includes(t.id);check.onchange=()=>connect(id,t.id,check.checked);row.append(check,document.createTextNode(t.name));inspector.append(row);}
      inspector.append(el('p','勾選可加入連線；取消勾選可移除。每個來源至少保留一個主題。','help'));
    }else{inspector.append(el('p',item.description),el('p',`來源期限：近 ${item.max_age_months} 個月 · 目標 ${item.target_items} 篇`),el('p','收錄關鍵字：'+(item.include_terms.join('、')||'沿用 AI／3D 相關性檢查')),el('p','排除關鍵字：'+(item.exclude_terms.join('、')||'無')),el('p',`連接來源 ${data.settings.sources.filter(s=>s.topic_ids.includes(id)).length} 個；是否啟用仍按來源與主題設定。`));}
    inspector.append(action('編輯'+(kind==='source'?'來源':'主題')+'設定',()=>onEdit(kind,id),'primary'));
    if(id!=='ai-3d')inspector.append(action(item.enabled?'暫停此'+(kind==='source'?'來源':'主題'):'啟用此'+(kind==='source'?'來源':'主題'),()=>{const next=structuredClone(data.settings);(kind==='source'?next.sources:next.topics).find(x=>x.id===id).enabled=!item.enabled;onChange(next);}));
  }
  viewport.onpointerdown=e=>{if(e.button!==0||e.target.closest('button,input,article'))return;gesture={kind:'pan',id:e.pointerId,startX:e.clientX,startY:e.clientY,x:viewport.scrollLeft,y:viewport.scrollTop};viewport.setPointerCapture(e.pointerId);};
  root.addEventListener('pointermove',e=>{if(!gesture||e.pointerId!==gesture.id)return;const dx=e.clientX-gesture.startX,dy=e.clientY-gesture.startY;if(Math.abs(dx)+Math.abs(dy)>5)clickBlocked=true;
    if(gesture.kind==='pan'){viewport.scrollLeft=gesture.x-dx;viewport.scrollTop=gesture.y-dy;}
    if(gesture.kind==='node'){const n=gesture.n;n.x=Math.max(30,gesture.x+dx/zoom);n.y=Math.max(35,gesture.y+dy/zoom);positions.set(n.key,{x:n.x,y:n.y});const box=[...nodes.children].find(x=>x.dataset.key===n.key);box.style.left=n.x+'px';box.style.top=n.y+'px';bounds();paintEdges();}
    if(gesture.kind==='connect'){const r=world.getBoundingClientRect();gesture.to={x:(e.clientX-r.left)/zoom,y:(e.clientY-r.top)/zoom};paintEdges();}
  });
  const finish=e=>{if(!gesture||e.pointerId!==gesture.id)return;const g=gesture;gesture=null;if(g.kind==='connect'&&clickBlocked&&e.type!=='pointercancel'){const target=document.elementFromPoint(e.clientX,e.clientY)?.closest('[data-topic-input]');if(target)connect(g.source,target.dataset.topicInput);else notify('請把來源接點連到主題的輸入接點。固定流程不可修改。',true);}paintEdges();setTimeout(()=>{clickBlocked=false;},0);};
  root.addEventListener('pointerup',finish);root.addEventListener('pointercancel',finish);root.addEventListener('keydown',e=>{if(e.key==='Escape'){armed=null;gesture=null;paintEdges();renderHint();}});
  function scale(value){const old=zoom;zoom=Math.min(1.5,Math.max(.4,value));const x=(viewport.scrollLeft+viewport.clientWidth/2)/old,y=(viewport.scrollTop+viewport.clientHeight/2)/old;bounds();viewport.scrollLeft=x*zoom-viewport.clientWidth/2;viewport.scrollTop=y*zoom-viewport.clientHeight/2;}
  $('#graph-zoom-in').onclick=()=>scale(zoom+.1);$('#graph-zoom-out').onclick=()=>scale(zoom-.1);$('#graph-arrange').onclick=()=>{positions.clear();zoom=1;viewport.scrollLeft=0;viewport.scrollTop=0;render();};
  $('#graph-focus').onclick=()=>{root.classList.toggle('graph-focus');$('#graph-focus').textContent=root.classList.contains('graph-focus')?'收合畫布':'展開畫布';};
  $('#graph-search').oninput=()=>{for(const s of data?.settings.sources||[])positions.delete('source:'+s.id);viewport.scrollLeft=0;viewport.scrollTop=0;render();};$('#graph-save').onclick=()=>onSave();$('#graph-discard').onclick=()=>onDiscard();$('#graph-add-source').onclick=()=>onAdd('source');$('#graph-add-topic').onclick=()=>onAdd('topic');
  return{update(next){data=next;render();},select,refreshInspector:renderInspector};
}
