// Presentation state only. Never persist settings, credentials or article evidence here.
export const clampZoom=value=>Math.min(2,Math.max(.02,value));
export function zoomAt(camera,value,point){
  const zoom=clampZoom(value),ratio=zoom/camera.zoom;
  return {zoom,x:(camera.x+point.x)*ratio-point.x,y:(camera.y+point.y)*ratio-point.y};
}
export function fitNodes(nodes,width,height){
  if(!nodes.length||width<=0||height<=0)return null;
  const left=Math.min(...nodes.map(n=>n.x)),top=Math.min(...nodes.map(n=>n.y));
  const right=Math.max(...nodes.map(n=>n.x+n.width)),bottom=Math.max(...nodes.map(n=>n.y+n.height));
  const zoom=clampZoom(Math.min((width-80)/(right-left),(height-80)/(bottom-top),1.5));
  return {zoom,x:(left+right)*zoom/2-width/2,y:(top+bottom)*zoom/2-height/2};
}
export function workspaceState(value){
  const clean={positions:[],camera:{zoom:1,x:0,y:0},mode:'configuration',selected:null};
  if(!value||![1,2].includes(value.schema))return clean;
  for(const entry of (Array.isArray(value.positions)?value.positions:[]).slice(0,1000)){
    if(!Array.isArray(entry)||entry.length!==2)continue;
    const [key,p]=entry;
    if(typeof key==='string'&&/^(source|topic|stage):[a-z0-9-]+$/.test(key)&&Number.isFinite(p?.x)&&Number.isFinite(p?.y))
      clean.positions.push([key,{x:p.x,y:p.y}]);
  }
  if([value.camera?.zoom,value.camera?.x,value.camera?.y].every(Number.isFinite))clean.camera={zoom:clampZoom(value.camera.zoom),x:value.camera.x,y:value.camera.y};
  clean.mode=value.mode==='operations'?'operations':'configuration';
  clean.selected=typeof value.selected==='string'?value.selected:null;
  return clean;
}
export function changeSummary(before,after){
  if(!before||!after)return [];
  const changes=[];
  for(const [group,label]of [['sources','來源'],['topics','分類']]){
    const old=new Map(before[group].map(x=>[x.id,x]));
    for(const item of after[group]){const previous=old.get(item.id);old.delete(item.id);
      if(!previous){changes.push(`新增${label}：${item.name}`);continue;}
      if(group==='sources'){
        for(const id of item.topic_ids.filter(id=>!previous.topic_ids.includes(id)))changes.push(`新增連線：${item.name} → ${after.topics.find(t=>t.id===id)?.name||id}`);
        for(const id of previous.topic_ids.filter(id=>!item.topic_ids.includes(id)))changes.push(`移除連線：${item.name} → ${before.topics.find(t=>t.id===id)?.name||id}`);
        if(!item.topic_ids.length)changes.push(`停止供稿：${item.name} 未連接任何分類，套用後保持停用。`);
      }
      const omit=x=>Object.fromEntries(Object.entries(x).filter(([k])=>k!=='topic_ids'));
      if(JSON.stringify(omit(previous))!==JSON.stringify(omit(item)))changes.push(`調整${label}設定：${item.name}`);
    }
    for(const item of old.values())changes.push(`移除${label}：${item.name}`);
  }
  return changes;
}
export function editHistory(limit=50){
  let rows=[],cursor=-1;
  return {reset(value){rows=[structuredClone(value)];cursor=0;},push(value){if(JSON.stringify(rows[cursor])===JSON.stringify(value))return;rows=rows.slice(0,cursor+1);rows.push(structuredClone(value));if(rows.length>limit)rows.shift();cursor=rows.length-1;},undo(){return cursor>0?structuredClone(rows[--cursor]):null;},redo(){return cursor<rows.length-1?structuredClone(rows[++cursor]):null;},get canUndo(){return cursor>0;},get canRedo(){return cursor<rows.length-1;}};
}
