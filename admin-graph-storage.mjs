import {layoutStore,boundedLayoutRequest} from './admin-graph-layout.mjs?v=20261127-toolbar1';
export function mountLayoutStorage({auth,graph,notify}){
  const status=document.querySelector('#graph-layout-state'),save=document.querySelector('#graph-layout-save'),reload=document.querySelector('#graph-layout-reload');
  let started=false,loading=false,saving=false,updated=null,error='',restoring=false;
  const store=layoutStore(async(name,args)=>{const {data,error}=await boundedLayoutRequest(signal=>{const request=auth.rpc(name,args);return request.abortSignal?request.abortSignal(signal):request;});if(error){if(error.message?.includes('layout_version_conflict'))throw Error('另一個分頁已更新版面。本次未覆蓋，請先還原已儲存版面再調整。');throw Error('帳號版面服務暫時無法使用（'+String(error.code||'network').replace(/[^a-zA-Z0-9_-]/g,'').slice(0,30)+'）；目前操作仍保留在此瀏覽器，尚未確認儲存成功。');}return data;});
  const dirty=()=>started&&!loading&&store.dirty(graph.getLayout());
  function paint(){document.querySelector('#graph-view').inert=loading;if(restoring)return;save.disabled=loading||saving||!store.ready||!dirty();reload.disabled=loading||saving;status.textContent=loading?'正在載入帳號版面…':saving?'正在儲存版面…':error||(dirty()?'版面有未儲存變更':updated?'版面已儲存 · '+new Date(updated).toLocaleString('zh-TW'):'尚未儲存帳號版面');}
  async function load(){if(loading||saving)return;loading=true;error='';paint();try{const r=await store.load();updated=r.updated_at;if(r.layout){restoring=true;graph.restoreLayout(r.layout);restoring=false;}started=true;}catch(e){started=true;error=e.message;notify(error,true);}finally{loading=false;restoring=false;paint();}}
  save.onclick=async()=>{if(save.disabled)return;saving=true;error='';paint();try{const r=await store.save(graph.getLayout());updated=r.updated_at;notify('版面已儲存到站主帳號；收集設定未變更。');}catch(e){error=e.message;notify(error,true);}finally{saving=false;paint();}};
  reload.onclick=async()=>{if(dirty()&&!confirm('還原帳號中已儲存的版面？目前未儲存的位置調整將捨棄；收集設定草稿保持不變。'))return;await load();};
  return {get dirty(){return dirty();},changed(){paint();},async start(){if(!started&&!loading)await load();}};
}
