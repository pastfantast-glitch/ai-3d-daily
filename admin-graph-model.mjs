import {validateSettings} from './supabase/functions/collection-admin/policy.mjs?v=20261126-wiring1';

import {unprojectSettings,BUILTINS} from './category-model.mjs';
export function validateGraphSettings(settings,options={}){validateSettings(unprojectSettings(settings),options);return settings;}
export const validateGraphDraft=settings=>validateGraphSettings(settings,{draft:true});

// The graph edits the existing settings contract; it never defines executable routes.
export function connectTopic(settings, sourceId, topicId, connected=true) {
  const next=structuredClone(settings),source=next.sources.find(s=>s.id===sourceId);
  if(!source||!next.topics.some(t=>t.id===topicId))throw new Error('只能連接既有來源與分類與分頁。');
  const ids=new Set(source.topic_ids);
  if(connected)ids.add(topicId);else ids.delete(topicId);
  source.topic_ids=[...ids];
  if(!ids.size)source.enabled=false;
  validateGraphDraft(next);
  return next;
}

export function connectionState(active, sourceId, topicId) {
  return active?.sources.some(s=>s.id===sourceId&&s.topic_ids.includes(topicId))?'active':'draft';
}

export function moveConnection(settings,source,from,to=null){
  if(!settings.sources.some(s=>s.id===source&&s.topic_ids.includes(from)))throw new Error('連線已變更，請重新選取。');
  if(to===from)return structuredClone(settings);
  // Add first so moving the only edge does not inadvertently pause an enabled source.
  return connectTopic(to?connectTopic(settings,source,to):settings,source,from,false);
}

export function stageData(operations,monitor) {
  const count=k=>operations?.counts?.[k]??'—';
  const date=operations?.date||'尚未查核';
  return [
    {id:'top5',name:'TOP5 精選',value:'跨分類精選 5 篇',note:'固定精選入口，沿用既有排名與發布品質檢查；不接受來源連線，不另開收集流程。',view:'overview'},
    {id:'filter',name:'日期與分類篩選',value:'依分類設定',note:'來源期限、關鍵字與製作相關性仍由 Collector 檢查。',view:'topics'},
    {id:'evidence',name:'正文擷取與去重',value:`正文可讀 ${count('body_readable')}`,note:`${date} · 品質與去重通過 ${count('quality_pass_unpublished')}。候選不代表已發布。`,view:'overview'},
    {id:'review',name:'來源核對與審稿',value:`記錄核准 ${count('review_approved')}`,note:`${operations?.queue_date||monitor?.date||'尚無紀錄'} · ${operations?`待處理紀錄 ${operations.queue?.length??0} 篇`:'尚未取得審稿狀態'}；必須有原文證據，連線不會核准文章。`,view:'queue'},
    {id:'reserve',name:'合格備稿',value:`待複核 ${operations?.reserve_count??'—'}`,note:'只保存合格剩餘內容；跨日使用前仍須重新核對來源、期限與去重。',view:'reserve'},
    {id:'publish',name:'唯一正式發布者',value:operations?.state==='DONE'?`已發布 ${count('published')} 篇`:operations?.state||'狀態未知',note:`${date} · ${operations?.issues?.join('；')||'交接、發布品質檢查與 Pages 驗證均須通過，才算正式完成。'}`,view:'overview'},
  ];
}

// Delete only the editable navigation category, never collection snapshots/articles.
export function removeCustomCategory(settings,id){
  if(!settings?._collection)throw Error('請先載入分類工作區。');
  if(BUILTINS.includes(id)||['ai-3d','top5'].includes(id))throw Error('系統分類不能刪除；可使用隱藏或停用。');
  if(!settings.topics.some(t=>t.id===id))throw Error('分類已不存在，請更新設定。');
  const next=structuredClone(settings);
  next.topics=next.topics.filter(t=>t.id!==id);
  for(const source of next.sources){
    if(!source.topic_ids.includes(id))continue;
    source.topic_ids=source.topic_ids.filter(t=>t!==id);
    if(!source.topic_ids.length)source.enabled=false;
  }
  return validateGraphDraft(next);
}
