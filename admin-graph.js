import {connectTopic,moveConnection,connectionState,stageData} from './admin-graph-model.mjs?v=20261126-wiring1';
import {zoomAt,fitNodes,workspaceState,editHistory,changeSummary} from './admin-graph-workspace.mjs?v=20261126-wiring1';
import {createGraphDetails} from './admin-graph-details.mjs?v=20261126-scope1';
const el=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
const svgEl=tag=>document.createElementNS('http://www.w3.org/2000/svg',tag);
export function mountGraph({onChange,onEdit,onAdd,onSave,onDiscard,onView,onValidation,notify}) {
  const root=document.querySelector('#graph-view'),viewport=root.querySelector('.graph-viewport'),space=root.querySelector('.graph-space'),world=root.querySelector('.graph-world'),edges=root.querySelector('.graph-edges'),nodes=root.querySelector('.graph-nodes'),inspector=root.querySelector('.graph-inspector-body');
  let data=null,selected=null,selectedWire=null,armed=null,zoom=1,cameraX=0,cameraY=0,positions=new Map(),visible=[],stageNodes=[],gesture=null,clickBlocked=false;
  let mode='configuration',storageKey=null,historyVersion=null,restoring=false,selection=new Set(),pendingCamera=null;
  const history=editHistory(),details=createGraphDetails();
  const $=s=>root.querySelector(s),label=$('#graph-local-state');
  const camera=()=>({zoom,x:cameraX,y:cameraY});
  function setCamera(c){zoom=c.zoom;cameraX=c.x;cameraY=c.y;bounds();}
  function applyDraft(next){onChange(next);viewport.focus({preventScroll:true});}
  const frame=()=>({settings:data.settings,positions:[...positions]});
  function persist(){if(!storageKey||!viewport.clientWidth||pendingCamera)return;try{localStorage.setItem(storageKey,JSON.stringify({schema:2,positions:[...positions],camera:camera(),mode,selected}));}catch{}}
  const editing=()=>$('#graph-inline-editor').contains(document.querySelector('#editor-form'));
  function historyButtons(){$('#graph-undo').disabled=!history.canUndo||data?.busy||editing();$('#graph-redo').disabled=!history.canRedo||data?.busy||editing();}
  function travel(back){if(data?.busy||editing())return;restoreFrame(back?history.undo():history.redo());}
  function remember(){if(!restoring&&data)history.push(frame());historyButtons();persist();}
  function restoreFrame(value){if(!value||data.busy||$('#graph-inline-editor').contains(document.querySelector('#editor-form')))return;restoring=true;positions=new Map(value.positions);applyDraft(value.settings);restoring=false;render();persist();}
  function fit(all=false){const targets=[...visible,...stageNodes].filter(n=>all||selection.has(n.key)||n.key===selected);const c=fitNodes(targets,viewport.clientWidth,viewport.clientHeight);if(c){setCamera(c);persist();}}
  function emphasize(){const related=new Set(selection);if(selected)related.add(selected);
    for(const s of data.settings.sources)for(const id of s.topic_ids)if(selected==='source:'+s.id||selected==='topic:'+id){related.add('source:'+s.id);related.add('topic:'+id);}
    for(const n of nodes.children){n.classList.toggle('selected',selection.has(n.dataset.key)||n.dataset.key===selected);n.classList.toggle('unrelated',!!selected&&!related.has(n.dataset.key)&&!selected.startsWith('stage:'));}
  }
  function action(text,fn,cls){const b=el('button',text,cls);b.type='button';b.onclick=fn;return b;}
  function filtered(){const q=$('#graph-search').value.trim().toLowerCase();return data.settings.sources.filter(s=>(s.name+' '+s.base_url).toLowerCase().includes(q));}
  function pos(key,fallback){if(!positions.has(key))positions.set(key,fallback);return positions.get(key);}
  function bounds(){world.style.transform=`translate(${-cameraX}px,${-cameraY}px) scale(${zoom})`;viewport.style.backgroundPosition=`${-cameraX}px ${-cameraY}px`;viewport.style.backgroundSize=`${22*zoom}px ${22*zoom}px`;$('#graph-zoom-label').textContent=Math.round(zoom*100)+'%';}
  function path(from,to,cls,labelText){const p=svgEl('path');const bend=Math.max(70,Math.abs(to.x-from.x)*.5);p.setAttribute('d',`M ${from.x} ${from.y} C ${from.x+bend} ${from.y}, ${to.x-bend} ${to.y}, ${to.x} ${to.y}`);p.setAttribute('class',cls);p.setAttribute('marker-end','url(#graph-arrow)');edges.append(p);if(labelText){const t=svgEl('text');t.setAttribute('x',(from.x+to.x)/2);t.setAttribute('y',(from.y+to.y)/2-9);t.textContent=labelText;edges.append(t);}return p;}
  function paintEdges(){edges.replaceChildren();if(!data)return;const lookup=new Map([...visible,...stageNodes].map(n=>[n.key,n]));
    const defs=svgEl('defs'),marker=svgEl('marker');marker.id='graph-arrow';for(const [k,v]of Object.entries({viewBox:'0 0 10 10',refX:'10',refY:'5',markerWidth:'5',markerHeight:'5',orient:'auto-start-reverse'}))marker.setAttribute(k,v);const arrow=svgEl('path');arrow.setAttribute('d','M 0 0 L 10 5 L 0 10 z');arrow.setAttribute('fill','#a4b5d0');marker.append(arrow);defs.append(marker);edges.append(defs);
    const wire=(a,b,cls,text,connection)=>{const x=lookup.get(a),y=lookup.get(b);if(selected&&!selected.startsWith('stage:')&&a!==selected&&b!==selected)cls+=' subdued';if(x&&y){
      const line=path({x:x.x+x.width,y:x.y+65},{x:y.x,y:y.y+65},cls,text);
      if(connection){
        const [source,topic]=connection,active=selectedWire?.source===source&&selectedWire?.topic===topic;
        line.classList.toggle('wire-selected',active);
        const hit=svgEl('path');hit.setAttribute('d',line.getAttribute('d'));hit.setAttribute('class','graph-wire-hit');hit.setAttribute('tabindex','0');hit.setAttribute('role','button');
        const sourceName=data.settings.sources.find(s=>s.id===source)?.name,topicName=data.settings.topics.find(t=>t.id===topic)?.name;
        hit.setAttribute('aria-label',`選取連線 ${sourceName} → ${topicName}`);hit.dataset.source=source;hit.dataset.topic=topic;hit.setAttribute('aria-pressed',String(active));
        const pick=()=>{if(data.busy||editing())return;selectedWire={source,topic};selected=null;selection.clear();emphasize();for(const h of edges.querySelectorAll('.graph-wire-hit')){const yes=h.dataset.source===source&&h.dataset.topic===topic;h.setAttribute('aria-pressed',String(yes));h.previousElementSibling?.classList.toggle('wire-selected',yes);}renderInspector();renderHint();};
        hit.onclick=e=>{e.stopPropagation();pick();};hit.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();pick();}};
        hit.oncontextmenu=e=>{e.preventDefault();pick();inspector.querySelector('.graph-remove-wire')?.focus();};edges.append(hit);
      }
    }};
    for(const s of filtered())for(const id of s.topic_ids){const changed=connectionState(data.activeSettings,s.id,id)==='draft';wire('source:'+s.id,'topic:'+id,'graph-wire '+(changed?'draft ':'')+(selected==='source:'+s.id||selected==='topic:'+id?'highlight ':''),null,[s.id,id]);}
    // Ghosts make removed connections visible until activation, not just until saving.
    for(const s of data.activeSettings?.sources||[])for(const id of s.topic_ids)if(data.settings.sources.some(x=>x.id===s.id&&!x.topic_ids.includes(id)))wire('source:'+s.id,'topic:'+id,'graph-wire removed');
    for(const t of data.settings.topics)wire('topic:'+t.id,'stage:filter','graph-wire fixed');
    for(const [a,b,text] of [['filter','evidence',''],['evidence','review',''],['review','reserve','剩餘合格稿'],['review','publish','當期入選'],['reserve','publish','重新核對後']])wire('stage:'+a,'stage:'+b,'graph-wire fixed',text);
    if(['connect','rewire'].includes(gesture?.kind)){const n=lookup.get('source:'+gesture.source);if(n)path({x:n.x+n.width,y:n.y+65},gesture.to,'graph-wire draft highlight');}
  }
  function select(key){if($('#graph-inline-editor').contains(document.querySelector('#editor-form'))){notify('請先完成或取消右側節點編輯。');return;}selectedWire=null;selected=key;selection=new Set([key]);emphasize();paintEdges();renderInspector();persist();}
  function connect(source,topic,connected=true){if(data.busy)return;if($('#graph-inline-editor').contains(document.querySelector('#editor-form'))){notify('請先完成或取消右側節點編輯。');return;}try{const next=connectTopic(data.settings,source,topic,connected);armed=null;selectedWire=null;applyDraft(next);notify(connected?'連線已加入草稿，儲存並驗證後才能套用。':'連線已移出草稿，現行設定保持不變。');}catch(e){notify(e.message,true);renderInspector();}renderHint();}
  function renderHint(){$('#graph-hint').textContent=selectedWire?'已選取連線：拖曳主題端接點改接，放到空白處可斷線；也可按 Delete 或右側「移除連線」。只修改草稿，可復原。':armed?`已選取「${data.settings.sources.find(s=>s.id===armed)?.name}」；點主題的輸入接點完成連線，Esc 取消。`:'滾輪以游標為中心縮放；空白處或中鍵拖曳平移。Shift＋拖曳空白處框選，按「聚焦選取」。拖曳節點標題移動；拖曳來源接點到主題接線。點選連線後按 Delete 移除。';}
  function node(n,title,subtitle,status,kind){const box=el('article',undefined,'graph-node '+kind);box.dataset.key=n.key;box.style.left=n.x+'px';box.style.top=n.y+'px';box.style.width=n.width+'px';
    const heading=action(title,()=>{if(!clickBlocked)select(n.key);},'graph-node-title');heading.setAttribute('aria-label','選取'+title);heading.onpointerdown=e=>{if(e.button!==0||data.busy||editing())return;gesture={kind:'node',capture:heading,id:e.pointerId,n,startX:e.clientX,startY:e.clientY,x:n.x,y:n.y};heading.setPointerCapture(e.pointerId);};
    heading.onkeydown=e=>{if(!data.busy&&!editing()&&e.altKey&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();n.x+=(e.key==='ArrowLeft'?-24:e.key==='ArrowRight'?24:0);n.y+=(e.key==='ArrowUp'?-24:e.key==='ArrowDown'?24:0);positions.set(n.key,{x:n.x,y:n.y});box.style.left=n.x+'px';box.style.top=n.y+'px';bounds();paintEdges();remember();}};
    box.append(el('span',kind==='source'?'來源':kind==='topic'?'收集主題':'固定流程','graph-kind'),heading,el('p',subtitle),el('small',status));box.classList.toggle('selected',selected===n.key);nodes.append(box);return box;
  }
  function render(){if(!data)return;nodes.replaceChildren();visible=[];stageNodes=[];const sources=filtered();
    (mode==='configuration'?sources:[]).forEach((s,i)=>{const key='source:'+s.id;const p=pos(key,{x:35,y:55+data.settings.sources.findIndex(x=>x.id===s.id)*150});const n={key,...p,width:255,height:130};visible.push(n);const m=data.monitor?.sources?.[s.id];const state=!s.topic_ids.length?'未連接主題 · 不參與收集':!s.enabled?'已暫停':m?.status==='blocked'?'讀取被拒':m?.status==='unavailable'?'讀取失敗':m?.status==='not-scheduled'?'本批未排入':m?'本批已檢查':'尚無紀錄';const box=node(n,s.name,`正文 ${m?.evidence_extracted??'—'} · 核准 ${m?.review_approved??'—'} · 待審 ${m?.awaiting_review??'—'}`,(JSON.stringify(data.activeSettings?.sources.find(x=>x.id===s.id))!==JSON.stringify(s)?'待套用 · ':'')+state,'source');box.classList.toggle('muted-node',!s.enabled);box.classList.toggle('warning-node',s.enabled&&['blocked','unavailable'].includes(m?.status));
      const port=action('●',()=>{if(clickBlocked||data.busy||editing())return;armed=armed===s.id?null:s.id;select(key);renderHint();},'graph-port output');port.setAttribute('aria-label','連接來源 '+s.name);port.onpointerdown=e=>{if(e.button!==0||data.busy||editing())return;e.stopPropagation();const r=world.getBoundingClientRect();gesture={kind:'connect',capture:port,id:e.pointerId,source:s.id,startX:e.clientX,startY:e.clientY,to:{x:(e.clientX-r.left)/zoom,y:(e.clientY-r.top)/zoom}};port.setPointerCapture(e.pointerId);root.classList.add('connecting');};box.append(port);
    });
    data.settings.topics.forEach((t,i)=>{const key='topic:'+t.id,n={key,...pos(key,{x:420,y:55+i*170}),width:255,height:140};visible.push(n);const box=node(n,t.name,`近 ${t.max_age_months} 個月 · 每期目標 ${t.target_items}`,(JSON.stringify(data.activeSettings?.topics.find(x=>x.id===t.id))!==JSON.stringify(t)?'待套用 · ':'')+(t.enabled?'啟用中':'已暫停'),'topic');box.classList.toggle('muted-node',!t.enabled);const port=action('●',()=>{if(clickBlocked||data.busy||editing())return;if(armed)connect(armed,t.id);else{select(key);notify('先選來源的輸出接點，再選這個主題。');}},'graph-port input');port.dataset.topicInput=t.id;
      port.onpointerdown=e=>{if(e.button!==0||!selectedWire||selectedWire.topic!==t.id||data.busy||editing())return;e.stopPropagation();const r=world.getBoundingClientRect();gesture={kind:'rewire',capture:port,id:e.pointerId,source:selectedWire.source,topic:t.id,startX:e.clientX,startY:e.clientY,to:{x:(e.clientX-r.left)/zoom,y:(e.clientY-r.top)/zoom}};port.setPointerCapture(e.pointerId);root.classList.add('connecting');};port.setAttribute('aria-label','連接到主題 '+t.name);box.append(port);});
    const layouts={filter:[790,55],evidence:[1100,55],review:[1100,245],reserve:[790,460],publish:[1410,390]};
    for(const s of mode==='operations'?stageData(data.operations,data.monitor):[]){const key='stage:'+s.id,[x,y]=layouts[s.id],n={key,...pos(key,{x,y}),width:230,height:140};stageNodes.push(n);const box=node(n,s.name,s.value,s.id==='publish'?(data.operations?.issues?.[0]||'系統流程 · '+(data.operations?.date||'日期未知')):'系統流程 · '+(data.operations?.date||'日期未知'),'stage');box.title=s.note;box.classList.toggle('warning-node',s.id==='publish'&&!!data.operations?.issues?.length);}
    $('#graph-data-date').textContent=`來源紀錄：${data.monitor?.date||'尚未取得'} · 發布查核：${data.operations?.date||'狀態未知'}（台北時間）`;
    $('#graph-empty').hidden=mode==='operations'||!!sources.length;const validationText={PASSED:'驗證通過，可查看結果並套用',FAILED:'驗證失敗；現行設定保持不變',VALIDATING:'驗證中；現行設定保持不變',SAVED:'草稿已儲存，等待驗證',STALE:'設定版本已更新，需重新驗證',UNKNOWN:'驗證狀態未知；現行設定保持不變'};label.textContent=data.dirty?'有未儲存草稿；現行設定未改變':data.validation?.draft?(validationText[data.validation.state]||'顯示待驗證設定；現行設定尚未改變'):'顯示現行設定';$('#graph-validation').hidden=data.dirty||!data.validation?.draft;$('#graph-save').disabled=!data.dirty||data.busy;$('#graph-discard').disabled=!data.dirty||data.busy;
    const changes=changeSummary(data.activeSettings,data.settings);$('#graph-change-summary').replaceChildren(...(changes.length?changes.map(x=>el('li',x)):[el('li','來源與主題設定沒有待套用變更。')]));
    $('#graph-mode').value=mode;bounds();paintEdges();emphasize();renderInspector();renderHint();historyButtons();
  }
  function renderInspector(){if($('#graph-inline-editor').contains(document.querySelector('#editor-form')))return;inspector.replaceChildren();
    if(selectedWire){const {source,topic}=selectedWire,s=data.settings.sources.find(s=>s.id===source),t=data.settings.topics.find(t=>t.id===topic);
      if(s?.topic_ids.includes(topic)&&t){const remove=action('移除連線',()=>connect(source,topic,false),'graph-remove-wire');remove.disabled=data.busy;inspector.append(el('span','連線詳情','eyebrow'),el('h3',`${s.name} → ${t.name}`),el('p','拖曳主題端接點到其他主題可改接，拖到畫布空白處可移除。移除只會修改草稿，可按「復原」還原。斷開最後一條連線會停用來源，保留來源設定與已收錄文章。'),remove);return;}selectedWire=null;
    }
    if(!selected){inspector.append(el('span','NODE DETAILS','eyebrow'),el('h3','選取一個節點'),el('p','來源連到主題，決定收錄範圍。固定流程呈現實際狀態，不會因為拉線就開始收集或批准稿件。'),el('p','紫色實線：既有連線；金色虛線：新增連線；紅色虛線：待移除連線。'),el('p','配置與觀看位置會保存在這個瀏覽器。來源設定仍須儲存、驗證並套用。','help'));return;}
    const [kind,id]=selected.split(':');if(kind==='stage'){const s=stageData(data.operations,data.monitor).find(x=>x.id===id);if(!s)return;inspector.append(el('span','今日運作','pill'),el('h3',s.name),el('strong',s.value),el('p',s.note));details(inspector,selected,data);return;}
    const item=(kind==='source'?data.settings.sources:data.settings.topics).find(x=>x.id===id);if(!item){selected=null;renderInspector();return;}inspector.append(el('span',kind==='source'?'來源節點':'主題節點','eyebrow'),el('h3',item.name));
    if(kind==='source'){const m=data.monitor?.sources?.[id],stat=data.metrics?.sources?.[id];inspector.append(el('p',item.base_url,'address'),el('p',`收集紀錄：${data.monitor?.date||'尚無紀錄'} · ${m?.reason||m?.status||'此來源尚未檢查'}`),el('p',`30 日已發布日報累計發布：${stat?.published??'—'} 篇`),el('h4','連接的主題'));
      for(const t of data.settings.topics){const row=el('label',undefined,'graph-binding'),check=el('input');check.type='checkbox';check.checked=item.topic_ids.includes(t.id);check.onchange=()=>connect(id,t.id,check.checked);row.append(check,document.createTextNode(t.name));inspector.append(row);}
      inspector.append(el('p','勾選可加入連線；取消勾選可移除。移除最後一條連線會停用來源；重新接線後可在此啟用。','help'));
    }else{inspector.append(el('p',item.description),el('p',`來源期限：近 ${item.max_age_months} 個月 · 目標 ${item.target_items} 篇`),el('p','收錄關鍵字：'+(item.include_terms.join('、')||'沿用 AI／3D 相關性檢查')),el('p','排除關鍵字：'+(item.exclude_terms.join('、')||'無')),el('p',`連接來源 ${data.settings.sources.filter(s=>s.topic_ids.includes(id)).length} 個；是否啟用仍按來源與主題設定。`));}
    inspector.append(action('編輯'+(kind==='source'?'來源':'主題')+'設定',()=>onEdit(kind,id),'primary'));
    if(id!=='ai-3d')inspector.append(action(item.enabled?'暫停此'+(kind==='source'?'來源':'主題'):'啟用此'+(kind==='source'?'來源':'主題'),()=>{const next=structuredClone(data.settings);(kind==='source'?next.sources:next.topics).find(x=>x.id===id).enabled=!item.enabled;applyDraft(next);}));
    details(inspector,selected,data);
  }
  viewport.addEventListener('pointerdown',e=>{if(e.button!==1&&(e.button!==0||e.target.closest('button,input,article,.graph-wire-hit')))return;e.preventDefault();e.stopPropagation();selectedWire=null;viewport.focus({preventScroll:true});const r=world.getBoundingClientRect();gesture={kind:e.shiftKey&&e.button===0?'select':'pan',capture:viewport,id:e.pointerId,startX:e.clientX,startY:e.clientY,x:cameraX,y:cameraY,origin:{x:(e.clientX-r.left)/zoom,y:(e.clientY-r.top)/zoom}};viewport.setPointerCapture(e.pointerId);paintEdges();renderInspector();renderHint();},true);
  viewport.addEventListener('auxclick',e=>{if(e.button===1)e.preventDefault();});
  root.addEventListener('pointermove',e=>{if(!gesture||e.pointerId!==gesture.id)return;const dx=e.clientX-gesture.startX,dy=e.clientY-gesture.startY;if(Math.abs(dx)+Math.abs(dy)>5)clickBlocked=true;
    if(gesture.kind==='pan'){cameraX=gesture.x-dx;cameraY=gesture.y-dy;bounds();}
    if(gesture.kind==='node'){const n=gesture.n;n.x=gesture.x+dx/zoom;n.y=gesture.y+dy/zoom;positions.set(n.key,{x:n.x,y:n.y});const box=[...nodes.children].find(x=>x.dataset.key===n.key);box.style.left=n.x+'px';box.style.top=n.y+'px';bounds();paintEdges();}
    if(['connect','rewire'].includes(gesture.kind)){const r=world.getBoundingClientRect();gesture.to={x:(e.clientX-r.left)/zoom,y:(e.clientY-r.top)/zoom};const target=document.elementFromPoint(e.clientX,e.clientY)?.closest('[data-topic-input]');for(const port of nodes.querySelectorAll('[data-topic-input]'))port.classList.toggle('drop-target',port===target);paintEdges();}
    if(gesture.kind==='select'){const r=world.getBoundingClientRect(),x=(e.clientX-r.left)/zoom,y=(e.clientY-r.top)/zoom,o=gesture.origin;let box=$('.graph-selection-box');if(!box){box=el('div',undefined,'graph-selection-box');world.append(box);}Object.assign(box.style,{left:Math.min(x,o.x)+'px',top:Math.min(y,o.y)+'px',width:Math.abs(x-o.x)+'px',height:Math.abs(y-o.y)+'px'});selection=new Set([...visible,...stageNodes].filter(n=>n.x+n.width>=Math.min(x,o.x)&&n.x<=Math.max(x,o.x)&&n.y+n.height>=Math.min(y,o.y)&&n.y<=Math.max(y,o.y)).map(n=>n.key));emphasize();}
  });
  function release(g){if(g.capture?.hasPointerCapture(g.id))g.capture.releasePointerCapture(g.id);root.classList.remove('connecting');nodes.querySelectorAll('.drop-target').forEach(p=>p.classList.remove('drop-target'));$('.graph-selection-box')?.remove();}
  function cancelGesture(){if(gesture){const g=gesture;gesture=null;release(g);if(g.kind==='node'){positions.set(g.n.key,{x:g.x,y:g.y});render();}if(g.kind==='pan'){cameraX=g.x;cameraY=g.y;bounds();}}armed=null;clickBlocked=true;setTimeout(()=>clickBlocked=false,0);paintEdges();renderHint();}
  const finish=e=>{if(!gesture||e.pointerId!==gesture.id)return;if(e.type==='pointercancel'){cancelGesture();return;}const g=gesture;gesture=null;release(g);
    if(g.kind==='connect'&&clickBlocked){const target=document.elementFromPoint(e.clientX,e.clientY)?.closest('[data-topic-input]');if(target)connect(g.source,target.dataset.topicInput);else notify('請把來源接點連到主題的輸入接點。固定流程不可修改。',true);}
    if(g.kind==='rewire'&&clickBlocked){const hit=document.elementFromPoint(e.clientX,e.clientY),target=hit?.closest('[data-topic-input]');
      if(target||hit?.closest('.graph-viewport')&&!hit.closest('article,.graph-wire-hit')){try{const next=moveConnection(data.settings,g.source,g.topic,target?.dataset.topicInput||null);selectedWire=null;armed=null;applyDraft(next);notify(target?'連線已改接至草稿，可復原。':'連線已移出草稿，現行設定保持不變。');}catch(error){notify(error.message,true);}}
      else notify('請放到主題輸入接點，或畫布空白處；本次未修改連線。',true);
    }
    if(g.kind==='node')remember();else persist();paintEdges();setTimeout(()=>{clickBlocked=false;},0);
  };
  root.addEventListener('pointerup',finish);root.addEventListener('pointercancel',finish);
  root.addEventListener('keydown',e=>{if(e.key==='Escape'){cancelGesture();selectedWire=null;renderInspector();paintEdges();}if(['Delete','Backspace'].includes(e.key)&&selectedWire&&!e.target.closest('input,textarea,select,[contenteditable]')){e.preventDefault();connect(selectedWire.source,selectedWire.topic,false);}});
  function scale(value,point={x:viewport.clientWidth/2,y:viewport.clientHeight/2}){setCamera(zoomAt(camera(),value,point));persist();}
  viewport.addEventListener('wheel',e=>{e.preventDefault();const r=viewport.getBoundingClientRect(),delta=e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?viewport.clientHeight:1);scale(zoom*Math.exp(-Math.max(-300,Math.min(300,delta))*.0015),{x:e.clientX-r.left,y:e.clientY-r.top});},{passive:false});
  new ResizeObserver(()=>{if(viewport.clientWidth&&pendingCamera){const c=pendingCamera;pendingCamera=null;setCamera(c);}}).observe(viewport);
  $('#graph-zoom-in').onclick=()=>scale(zoom+.1);$('#graph-zoom-out').onclick=()=>scale(zoom-.1);$('#graph-arrange').onclick=()=>{positions.clear();render();remember();fit(true);};
  root.addEventListener('pointerup',()=>$('.graph-selection-box')?.remove());root.addEventListener('pointercancel',()=>$('.graph-selection-box')?.remove());
  root.addEventListener('keydown',e=>{if(e.key==='Escape'){root.classList.remove('details-expanded');$('#graph-expand-details').textContent='展開詳情';$('.graph-selection-box')?.remove();}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'&&!e.target.closest('input,textarea,select,[contenteditable]')){e.preventDefault();travel(!e.shiftKey);}});
  $('#graph-fit').onclick=()=>fit(true);$('#graph-fit-selection').onclick=()=>fit();$('#graph-undo').onclick=()=>travel(true);$('#graph-redo').onclick=()=>travel(false);
  $('#graph-mode').onchange=()=>{mode=$('#graph-mode').value;selectedWire=null;selected=null;selection.clear();render();fit(true);persist();};
  $('#graph-expand-details').onclick=()=>{root.classList.toggle('details-expanded');$('#graph-expand-details').textContent=root.classList.contains('details-expanded')?'收合詳情':'展開詳情';};
  $('#graph-validation').onclick=()=>{if(editing())return;inspector.replaceChildren(el('h3','設定驗證'),el('p',data.validation?.message||data.validation?.state||'狀態未知'),el('p','現行設定會在驗證通過並由你套用後更新。'));if(data.validation?.run_url){const a=el('a','開啟驗證執行紀錄');a.href=data.validation.run_url;a.target='_blank';a.rel='noopener';inspector.append(a);}inspector.append(action('管理設定套用',onValidation));};
  $('#graph-focus').onclick=()=>{root.classList.toggle('graph-focus');$('#graph-focus').textContent=root.classList.contains('graph-focus')?'收合畫布':'展開畫布';};
  $('#graph-search').oninput=()=>render();$('#graph-save').onclick=()=>onSave();$('#graph-discard').onclick=()=>onDiscard();$('#graph-add-source').onclick=()=>onAdd('source');$('#graph-add-topic').onclick=()=>onAdd('topic');
  return{update(next){let saved=null;if(storageKey!==next.storageKey){storageKey=next.storageKey;try{saved=workspaceState(JSON.parse(localStorage.getItem(storageKey)));}catch{saved=workspaceState(null);}positions=new Map(saved.positions);zoom=saved.camera.zoom;cameraX=saved.camera.x;cameraY=saved.camera.y;mode=saved.mode;selected=saved.selected;pendingCamera=saved.camera;}data=next;render();if(historyVersion!==next.version){historyVersion=next.version;history.reset(frame());}else if(!restoring)history.push(frame());historyButtons();if(saved&&viewport.clientWidth){pendingCamera=null;setCamera(saved.camera);}},select,refreshInspector:renderInspector};
}
