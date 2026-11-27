import {categories,categoryItems} from './category-model.mjs';

const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
export const newCategoryVisibility={visible:true,hide_empty:false};
export function saveControl({busy,dirty,validation}){
  if(busy)return {disabled:true,busy:true,label:'正在儲存設定…',reason:'正在確認儲存結果，請稍候。'};
  if(dirty)return {disabled:false,busy:false,label:'儲存收集設定並驗證',reason:'草稿尚未儲存；儲存、驗證並套用後才會更新首頁。'};
  return {disabled:true,busy:false,label:'設定已儲存',reason:validation?.draft?'沒有未儲存變更；請查看驗證結果並套用。':'沒有未儲存變更；編輯分類或連線後即可儲存。'};
}
export function categoryStatus(id,{settings,active,saved,validation,publicState}){
  const row=categories(settings).find(c=>c.id===id),current=categories(active).find(c=>c.id===id),stored=categories(saved).find(c=>c.id===id);
  const labels={PASSED:'驗證通過，待套用',FAILED:'驗證失敗，尚未套用',VALIDATING:'驗證中，尚未套用',SAVED:'已儲存，等待驗證',STALE:'版本已變更，需重新驗證',UNKNOWN:'驗證狀態未知，尚未套用'};
  const applied=same(row,current),application=applied?'已套用':!same(row,stored)?'未儲存草稿':labels[validation?.state]||'已儲存，尚未套用';
  const published=publicState?.settings&&categories(publicState.settings).find(c=>c.id===id);
  let homepage;
  if(!publicState?.settings)homepage='首頁狀態未知：尚未取得線上設定。';
  else if(!published)homepage=current?'首頁尚未更新：等待設定部署。':'首頁未顯示：此分類尚未套用。';
  else if(!published.enabled)homepage='首頁隱藏：分類已停用。';
  else if(!published.visible)homepage='首頁隱藏：未勾選「在導覽列顯示」。';
  else if(!publicState.items)homepage='首頁文章數未知：已發布資料讀取失敗，請更新狀態。';
  else{
    const count=categoryItems(publicState.items,published,publicState.settings).length;
    homepage=published.hide_empty&&!count?`首頁隱藏：${publicState.date} 本期 0 篇，且已設定空分類隱藏。`:`首頁顯示：${publicState.date} 本期 ${count} 篇${count?'':'，保留空分類入口'}。`;
  }
  if(current&&published&&!same(current,published))homepage+=' 線上仍是舊設定，等待部署更新。';
  if(!applied&&published)homepage+=' 目前依已套用版本顯示；草稿尚未生效。';
  return {application,homepage};
}
