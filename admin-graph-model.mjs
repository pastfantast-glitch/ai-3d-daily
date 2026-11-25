import {validateSettings} from './supabase/functions/collection-admin/policy.mjs';

// The graph edits the existing settings contract; it never defines executable routes.
export function connectTopic(settings, sourceId, topicId, connected=true) {
  const next=structuredClone(settings),source=next.sources.find(s=>s.id===sourceId);
  if(!source||!next.topics.some(t=>t.id===topicId))throw new Error('只能連接既有來源與收集主題。');
  const ids=new Set(source.topic_ids);
  if(connected)ids.add(topicId);else ids.delete(topicId);
  if(!ids.size)throw new Error('來源至少需要一個主題；停止收集請暫停來源。');
  source.topic_ids=[...ids];
  validateSettings(next);
  return next;
}

export function connectionState(active, sourceId, topicId) {
  return active?.sources.some(s=>s.id===sourceId&&s.topic_ids.includes(topicId))?'active':'draft';
}

export function stageData(operations,monitor) {
  const count=k=>operations?.counts?.[k]??'—';
  const date=operations?.date||'尚未查核';
  return [
    {id:'filter',name:'日期與主題篩選',value:'依主題設定',note:'來源期限、關鍵字與製作相關性仍由 Collector 檢查。',view:'topics'},
    {id:'evidence',name:'正文擷取與去重',value:`正文可讀 ${count('body_readable')}`,note:`${date} · 品質與去重通過 ${count('quality_pass_unpublished')}。候選不代表已發布。`,view:'overview'},
    {id:'review',name:'來源核對與審稿',value:`記錄核准 ${count('review_approved')}`,note:`${operations?.queue_date||monitor?.date||'尚無紀錄'} · ${operations?`待處理紀錄 ${operations.queue?.length??0} 篇`:'尚未取得審稿狀態'}；必須有原文證據，連線不會核准文章。`,view:'queue'},
    {id:'reserve',name:'合格備稿',value:`待複核 ${operations?.reserve_count??'—'}`,note:'只保存合格剩餘內容；跨日使用前仍須重新核對來源、期限與去重。',view:'reserve'},
    {id:'publish',name:'唯一正式發布者',value:operations?.state==='DONE'?`已發布 ${count('published')} 篇`:operations?.state||'狀態未知',note:`${date} · ${operations?.issues?.join('；')||'交接、發布品質檢查與 Pages 驗證均須通過，才算正式完成。'}`,view:'overview'},
  ];
}
