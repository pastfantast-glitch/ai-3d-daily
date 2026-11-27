import {publicURL} from './policy.mjs';
import {urlKey,sourceMatch} from './supply.mjs';
import {decode,encode} from './settings-flow.mjs';
export const INTAKE_PATH='config/collection-intake.json';
export function classifyURL(url,data,settings){
 if(!publicURL(url))throw Error('unsafe_source_url');
 const key=urlKey(url),match=rows=>(rows||[]).find(x=>urlKey(x.source_url)===key);
 const source=sourceMatch(url,settings.sources);
 const published=match(data.published_items)||match(data.registry);
 const row=published||match(data.reserve)||match(data.queue)||match(data.intake);
 return {url:key,source_id:source?.id||null,source_name:source?.name||null,
  state:published?'published':row?.state||(row?'recommended':data.reserve_complete===false||data.queue_complete===false?'unknown':source?'not_discovered':'unregistered'),
  source_enabled:source?.enabled??false,row:row||null,
  can_recommend:!!source?.enabled&&!row&&data.reserve_complete!==false,
  note:'查詢以已持久化紀錄為準；未發現不代表網站沒有文章。推薦不等於審稿核准或立即發布。'};
}
export async function saveRecommendation(github,{url,sha,head},settings,now=new Date()){
 if(!publicURL(url)||!head||!/^[a-f0-9]{40}$/.test(head))throw Error('invalid_recommendation');
 const source=sourceMatch(url,settings.sources);
 if(!source?.enabled||!source.topic_ids?.length)throw Error('source_not_enabled');
 const current=(await github('/git/ref/heads/main')).object.sha;
 if(current!==head)throw Error('version_conflict');
 let file=null;
 try{file=await github(`/contents/${INTAKE_PATH}?ref=${head}`);}catch(e){if(e.message!=='repository_404')throw e;}
 if((file?.sha||null)!==(sha||null))throw Error('version_conflict');
 const data=file?decode(file):{schema_version:1,items:[]};
 if(data.schema_version!==1||!Array.isArray(data.items))throw Error('invalid_intake');
 const normalized=urlKey(url);
 if(data.items.some(x=>urlKey(x.source_url)===normalized))return {unchanged:true,sha:file.sha,message:'此網址已在推薦佇列中。'};
 if(data.items.length>=500)throw Error('intake_capacity');
 const item={source_url:normalized,source_id:source.id,requested_on:new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Taipei'}).format(now)};
 const result=await github(`/contents/${INTAKE_PATH}`,'PUT',{branch:'main',...(file?{sha:file.sha}:{}),
  content:encode({schema_version:1,items:[...data.items,item]}),message:'Recommend article for existing Collector [collection-intake]'});
 return {sha:result.content.sha,commit_url:result.commit.html_url,message:'已加入推薦；下一次既有 Collector 會重新擷取、去重及送審。'};
}
