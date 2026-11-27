import {validateCategories} from '../../../category-model.mjs';
export const REPO='pastfantast-glitch/ai-3d-daily';
export const SETTINGS='config/collection-admin.json';
export const ORIGIN='https://pastfantast-glitch.github.io';
const slug=/^[a-z0-9][a-z0-9-]{1,47}$/;
export function publicURL(value){
  if(typeof value!=='string'||value.length>1500)return false;
  try{const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password&&!u.hash&&(!u.port||u.port==='443')&&
    /^[a-z0-9.-]+$/i.test(u.hostname)&&u.hostname.includes('.')&&!/^\d+(\.\d+){3}$/.test(u.hostname)&&
    !/(\.(local|internal|localhost|test|invalid)|\.)$/i.test(u.hostname);
  }catch{return false;}
}
export function validateSettings(data,{draft=false}={}){
  const need=(ok,message)=>{if(!ok)throw new Error(message);};
  const fields=(x,keys)=>x&&typeof x==='object'&&!Array.isArray(x)&&Object.keys(x).sort().join()===keys.split(',').sort().join();
  const text=(v,n,empty=false)=>typeof v==='string'&&v.length<=n&&(empty||v.trim())&&!/[\x00-\x1f]/.test(v);
  need(fields(data,data?.navigation===undefined?'schema_version,topics,sources':'schema_version,topics,sources,navigation')&&data.schema_version===1,'設定格式不正確');
  need(Array.isArray(data.topics)&&data.topics.length>=1&&data.topics.length<=20,'主題數量需為 1–20');
  const ids=new Set();
  for(const t of data.topics){
    need(fields(t,'id,name,description,enabled,include_terms,exclude_terms,target_items,max_age_months'),'主題欄位不正確');
    need(typeof t.id==='string'&&slug.test(t.id)&&!ids.has(t.id),'主題網址需唯一，使用 2–48 位小寫英數與連字號');ids.add(t.id);
    need(text(t.name,80)&&text(t.description,500,true),'請填寫有效主題名稱與說明');
    need(typeof t.enabled==='boolean'&&Number.isInteger(t.target_items)&&t.target_items>=1&&t.target_items<=30,'主題目標需為 1–30 篇');
    need(Number.isInteger(t.max_age_months)&&t.max_age_months>=1&&t.max_age_months<=12,'收錄期限需為 1–12 個月');
    for(const key of ['include_terms','exclude_terms'])need(Array.isArray(t[key])&&t[key].length<=30&&t[key].every(x=>text(x,80)),'關鍵字最多 30 組，每組 80 字');
    need(t.id==='ai-3d'||t.include_terms.length>0,'新主題需要至少一組收錄關鍵字');
  }
  need(data.topics.some(t=>t.id==='ai-3d'&&t.enabled&&t.target_items===30),'AI／3D 首頁必須保持啟用，發布目標維持 30 篇');
  need(Array.isArray(data.sources)&&data.sources.length>=1&&data.sources.length<=100,'來源數量需為 1–100');
  const sources=new Set(),hosts=new Set();
  for(const s of data.sources){
    need(fields(s,'id,name,base_url,endpoints,enabled,topic_ids'),'來源欄位不正確');
    need(typeof s.id==='string'&&slug.test(s.id)&&!sources.has(s.id),'來源代號需唯一');sources.add(s.id);
    need(text(s.name,100)&&publicURL(s.base_url)&&typeof s.enabled==='boolean','請填寫有效名稱及公開 HTTPS 網址');
    const host=new URL(s.base_url).hostname.replace(/^www\./,'');need(!hosts.has(host),'同一網站請編輯既有來源並增加主題');hosts.add(host);
    need(Array.isArray(s.topic_ids)&&s.topic_ids.length<=20&&new Set(s.topic_ids).size===s.topic_ids.length&&s.topic_ids.every(id=>ids.has(id)),'請選擇有效主題');
    need(!s.enabled||s.topic_ids.length>0,'未連接主題的來源必須停用；請先接線再啟用。');
    need(Array.isArray(s.endpoints)&&s.endpoints.length>=1&&s.endpoints.length<=5&&s.endpoints.every(u=>publicURL(u)&&(new URL(u).hostname.replace(/^www\./,'')===host||new URL(u).hostname.endsWith('.'+host))),'文章列表／RSS 最多 5 個，且須與來源同網域');
  }
  if(!draft)need(data.sources.some(s=>s.enabled&&s.topic_ids.includes('ai-3d')),'AI／3D 至少需保留一個啟用來源，才能儲存並驗證。');
  if(data.navigation!==undefined){validateCategories(data.navigation,data.sources);if(!draft)need(data.navigation.some(c=>c.enabled&&data.sources.some(s=>s.enabled&&c.source_ids.includes(s.id))),'至少保留一個啟用分類及供稿來源');}
  return data;
}

export function publicIP(ip){
  // DNS results are checked before every request and redirect. Deny special ranges.
  if(ip.includes(':'))return /^2[0-9a-f]{3}:/i.test(ip)&&!/^2001:(db8|0:)/i.test(ip);
  const p=ip.split('.').map(Number);if(p.length!==4||p.some(n=>!Number.isInteger(n)||n<0||n>255))return false;
  const [a,b,c]=p;
  return !(a===0||a===10||a===127||a>=224||a===169&&b===254||a===172&&b>=16&&b<=31||a===192&&(b===168||b===0||b===2)||a===100&&b>=64&&b<=127||a===198&&(b===18||b===19||b===51&&c===100)||a===203&&b===0&&c===113);
}
