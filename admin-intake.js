const $=s=>document.querySelector(s),el=(tag,text)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;return e;};
const labels={unknown:'紀錄不完整，尚無法判定',published:'已發布',awaiting_review:'等待逐篇審稿',recheck_required:'已審，使用前待複核',recommended:'已推薦，等待收集',discovered:'已發現，等待正文擷取',source_unavailable:'正文暫時無法讀取',rejected:'需處理退件原因',held:'已暫緩',date_ineligible:'來源日期超過收錄範圍',not_discovered:'尚無發現紀錄',unregistered:'尚未加入資訊池',source_disabled:'來源已停用'};
export function mountIntake(api,notify,refresh){
 const form=el('form'),input=el('input'),search=el('button','查詢收錄狀態'),out=el('div');
 form.className='panel';input.type='url';input.required=true;input.placeholder='貼上文章 HTTPS 網址';input.setAttribute('aria-label','查詢或推薦文章網址');search.type='submit';out.setAttribute('role','status');
 form.append(el('h3','查網址・推薦收錄'),el('p','推薦文章會交給下一次既有收集流程，仍須正文、日期、去重與審稿檢查。'),input,search,out);
 $('#queue-view .section-heading').after(form);
 let busy=false;
 form.onsubmit=async e=>{e.preventDefault();if(busy)return;busy=true;search.disabled=true;out.textContent='正在對照收錄紀錄…';try{
  const data=await api('lookup_url',{url:input.value.trim()});out.replaceChildren(el('strong',labels[data.state]||data.state),el('p',data.source_name||'未註冊來源'),el('p',data.note));
  if(data.row?.errors?.length)out.append(el('p',data.row.errors.join(' · ')));
  if(data.row?.source_run_id){const a=el('a','查看來源證據執行紀錄');a.href=`https://github.com/pastfantast-glitch/ai-3d-daily/actions/runs/${data.row.source_run_id}`;a.target='_blank';a.rel='noopener';out.append(a);}
  if(data.row?.first_seen)out.append(el('p',`首次發現：${data.row.first_seen}；最近處理：${data.row.last_attempt_on||'尚未擷取'}`));
  if(data.can_recommend){const recommend=el('button','推薦收錄');recommend.type='button';recommend.onclick=async()=>{recommend.disabled=true;try{const r=await api('recommend_url',{url:data.url,head:data.head,sha:data.intake_sha});out.replaceChildren(el('p',r.message));await refresh();}catch(e){notify(e.message,true);out.append(el('p','未確認加入成功，請重新查詢；不會自動重送。'));}};out.append(recommend);}
  if(data.state==='unregistered')out.append(el('p','請先到來源管理新增並驗證這個網站。'));
 }catch(e){out.textContent='查詢失敗：'+e.message;}finally{busy=false;search.disabled=false;}};
}
