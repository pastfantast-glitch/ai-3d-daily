// Layout is presentation only; never send collection settings through this channel.
const keyOK=k=>typeof k==='string'&&/^(source|topic|stage):[a-z0-9-]{1,100}$/.test(k);
const point=p=>p&&Number.isFinite(p.x)&&Number.isFinite(p.y)&&Math.abs(p.x)<=1e9&&Math.abs(p.y)<=1e9;
const camera=c=>point(c)&&Number.isFinite(c.zoom)&&c.zoom>=.02&&c.zoom<=2;
const keys=a=>Array.isArray(a)&&a.length<=1000&&a.every(keyOK)&&new Set(a).size===a.length;
export function layoutDocument(value){
  const v=structuredClone(value);
  if(v?.schema!==3||!Array.isArray(v.positions)||v.positions.length>1000||!v.positions.every(e=>Array.isArray(e)&&e.length===2&&keyOK(e[0])&&point(e[1]))||new Set(v.positions.map(e=>e[0])).size!==v.positions.length||!camera(v.camera)||!['configuration','operations'].includes(v.mode))throw Error('版面資料格式不正確。');
  const n=v.navigation;if(!n||!keys(n.locks)||!Array.isArray(n.views)||n.views.length>8||!Array.isArray(n.groups)||n.groups.length>20)throw Error('版面導覽格式不正確。');
  const name=s=>typeof s==='string'&&s.length>0&&s.length<=40;
  if(!n.views.every(x=>name(x.name)&&camera(x.camera))||!n.groups.every(x=>name(x.name)&&keys(x.ids)))throw Error('版面群組格式不正確。');
  return {schema:3,positions:v.positions.map(([k,p])=>[k,{x:p.x,y:p.y}]).sort(([a],[b])=>a.localeCompare(b)),camera:{x:v.camera.x,y:v.camera.y,zoom:v.camera.zoom},mode:v.mode,navigation:{locks:[...n.locks].sort(),views:n.views.map(x=>({name:x.name,camera:{x:x.camera.x,y:x.camera.y,zoom:x.camera.zoom}})),groups:n.groups.map(x=>({name:x.name,ids:[...x.ids]}))}};
}
export function layoutStore(rpc){
  let revision=null,baseline=null;
  return {
    get ready(){return revision!==null;},
    dirty(value){return baseline!==JSON.stringify(layoutDocument(value));},
    async load(){const r=await rpc('get_admin_graph_layout',{});revision=r.revision;baseline=r.layout?JSON.stringify(layoutDocument(r.layout)):null;return r;},
    async save(value){if(revision===null)throw Error('請先載入帳號版面，避免覆蓋其他裝置的變更。');const layout=layoutDocument(value);const r=await rpc('save_admin_graph_layout',{p_expected_revision:revision,p_layout:layout});revision=r.revision;baseline=JSON.stringify(layout);return r;}
  };
}
export function movedNodes(nodes,selected,locked,dx,dy){return nodes.filter(n=>selected.has(n.key)&&!locked(n.key)).map(n=>[n.key,{x:n.x+dx,y:n.y+dy}]);}
export function alignedNodes(nodes,selected,locked,kind){
  const list=nodes.filter(n=>selected.has(n.key));if(list.length<2)return [];
  const axis=['left','horizontal'].includes(kind)?'x':'y',size=axis==='x'?'width':'height';
  if(['left','top'].includes(kind)){const anchor=list.find(n=>locked(n.key)),target=anchor?anchor[axis]:Math.min(...list.map(n=>n[axis]));return list.filter(n=>!locked(n.key)).map(n=>[n.key,{x:n.x,y:n.y,[axis]:target}]);}
  if(list.length<3)return [];
  list.sort((a,b)=>a[axis]-b[axis]||a.key.localeCompare(b.key));
  // Fixed nodes split spacing into independent spans; endpoints stay in place.
  const anchors=[0,...list.flatMap((n,i)=>i>0&&i<list.length-1&&locked(n.key)?[i]:[]),list.length-1],out=[];
  for(let j=1;j<anchors.length;j++){const a=anchors[j-1],b=anchors[j],span=list[b][axis]-list[a][axis],width=list.slice(a,b).reduce((s,n)=>s+n[size],0),gap=(span-width)/(b-a);let at=list[a][axis];for(let i=a+1;i<b;i++){at+=list[i-1][size]+gap;out.push([list[i].key,{x:list[i].x,y:list[i].y,[axis]:at}]);}}
  return out;
}
export function arrangedNodes(nodes,links,selected,locked){
  const targets=nodes.filter(n=>(!selected||selected.has(n.key))&&!locked(n.key));if(!targets.length)return [];
  const stage={filter:2,evidence:3,review:4,reserve:5,publish:6,top5:7};
  const rank=n=>n.key.startsWith('source:')?0:n.key.startsWith('topic:')?1:(n.key==='stage:top5'&&!nodes.some(x=>x.key==='stage:publish')?2:(stage[n.key.split(':')[1]]??2));
  const columns=new Map();for(const n of nodes){const r=rank(n);if(!columns.has(r))columns.set(r,[]);columns.get(r).push(n);}
  // Barycentric ordering groups shared connections; ties preserve the owner's ordering.
  const order=new Map(nodes.map(n=>[n.key,n.y]));
  for(let sweep=0;sweep<4;sweep++)for(const r of [...columns.keys()].sort((a,b)=>sweep%2?b-a:a-b)){
    const rows=columns.get(r),score=n=>{const peers=links.flatMap(([a,b])=>a===n.key?[b]:b===n.key?[a]:[]).filter(k=>order.has(k));return peers.length?peers.reduce((s,k)=>s+order.get(k),0)/peers.length:order.get(n.key);};
    rows.sort((a,b)=>score(a)-score(b)||a.y-b.y||a.key.localeCompare(b.key));rows.forEach((n,i)=>order.set(n.key,i*190));
  }
  const origin={x:Math.min(...targets.map(n=>n.x)),y:Math.min(...targets.map(n=>n.y))},minRank=Math.min(...targets.map(rank)),out=[],obstacles=nodes.filter(n=>!targets.includes(n));
  for(const r of [...columns.keys()].sort((a,b)=>a-b)){let y=origin.y;for(const n of columns.get(r).filter(n=>targets.includes(n))){const x=origin.x+(r-minRank)*390;let collision;do{collision=obstacles.find(o=>x<o.x+o.width+24&&x+n.width+24>o.x&&y<o.y+o.height+30&&y+n.height+30>o.y);if(collision)y=collision.y+collision.height+50;}while(collision);out.push([n.key,{x,y}]);obstacles.push({...n,x,y});y+=n.height+60;}}
  return out;
}

export async function boundedLayoutRequest(run,timeoutMs=15000){
  const controller=new AbortController();let timer;
  try{return await Promise.race([Promise.resolve().then(()=>run(controller.signal)),new Promise((_,reject)=>{timer=setTimeout(()=>{controller.abort();reject(Error('版面服務回應逾時，儲存結果尚未確認；請重新載入帳號版面確認後再操作。'));},timeoutMs);})]);}
  finally{clearTimeout(timer);}
}
