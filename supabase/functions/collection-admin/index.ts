import { REPO, SETTINGS, ORIGIN, validateSettings, publicURL, publicIP } from './policy.mjs';
import {snapshot,decode,validationState,savePending,activate} from './settings-flow.mjs';
import { operations, CONTROL_PATH, validateControls, taipeiDate } from './operations.mjs';
import {classifyURL,saveRecommendation,INTAKE_PATH} from './intake.mjs';

const MAX_BODY=100000, MAX_REMOTE=2000000;
function reply(status:number, body:unknown, origin:string){return new Response(JSON.stringify(body),{status,headers:{
  'Content-Type':'application/json','Cache-Control':'no-store','Vary':'Origin',
  ...(origin===ORIGIN?{'Access-Control-Allow-Origin':origin,'Access-Control-Allow-Headers':'authorization,apikey,content-type','Access-Control-Allow-Methods':'POST,OPTIONS'}:{})}});}
async function limited(response:Response,max:number){
  const reader=response.body?.getReader();if(!reader)throw new Error('empty_response');let size=0;const chunks=[];
  while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>max){await reader.cancel();throw new Error('response_too_large');}chunks.push(value);}
  const out=new Uint8Array(size);let offset=0;for(const c of chunks){out.set(c,offset);offset+=c.length;}return new TextDecoder().decode(out);
}
async function github(path:string, method='GET',body?:unknown){
  const key=Deno.env.get('COLLECTION_GITHUB_TOKEN');if(!key)throw new Error('admin_not_configured');
  const r=await fetch(`https://api.github.com/repos/${REPO}${path}`,{method,headers:{Authorization:`Bearer ${key}`,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(15000)});
  if(!r.ok)throw new Error(r.status===409||r.status===422?'version_conflict':`repository_${r.status}`);
  return JSON.parse(await limited(r,1500000));
}
async function settingsRuns(head:string){
  if(!/^[a-f0-9]{40}$/.test(head))throw new Error('invalid_version');
  const r=await fetch(`https://api.github.com/repos/${REPO}/actions/runs?head_sha=${head}&per_page=100`,{headers:{Accept:'application/vnd.github+json'},signal:AbortSignal.timeout(15000)});
  if(!r.ok)throw new Error('checks_unavailable');return JSON.parse(await limited(r,1500000));
}
async function commitSettings(head:string,content:string){
  const r=await fetch('https://api.github.com/graphql',{method:'POST',headers:{Authorization:`Bearer ${Deno.env.get('COLLECTION_GITHUB_TOKEN')}`,'Content-Type':'application/json'},body:JSON.stringify({query:'mutation($input:CreateCommitOnBranchInput!){createCommitOnBranch(input:$input){commit{oid url}}}',variables:{input:{branch:{repositoryNameWithOwner:REPO,branchName:'main'},expectedHeadOid:head,message:{headline:'Apply validated collection settings [collection-settings]'},fileChanges:{additions:[{path:SETTINGS,contents:content}]}}}}),signal:AbortSignal.timeout(15000)});
  const data=JSON.parse(await limited(r,100000));
  if(!r.ok||data.errors||!data.data?.createCommitOnBranch?.commit)throw new Error('version_conflict');
  return data.data.createCommitOnBranch.commit;
}
async function owner(req:Request){
  const auth=req.headers.get('authorization')||'';if(!/^Bearer [A-Za-z0-9_.-]{20,16000}$/.test(auth))return false;
  const base=Deno.env.get('SUPABASE_URL')!,key=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
  const user=await fetch(`${base}/auth/v1/user`,{headers:{apikey:key,Authorization:auth},signal:AbortSignal.timeout(8000)});
  if(!user.ok)return false;const u=await user.json();if(typeof u.id!=='string')return false;
  const r=await fetch(`${base}/rest/v1/app_owner?singleton=eq.true&select=user_id&limit=2`,{headers:{apikey:key,Authorization:`Bearer ${key}`},signal:AbortSignal.timeout(8000)});
  if(!r.ok)return false;const rows=await r.json();return Array.isArray(rows)&&rows.length===1&&rows[0].user_id===u.id;
}
async function external(url:string){
  for(let hop=0;hop<4;hop++){
    if(!publicURL(url))throw new Error('unsafe_source_url');
    const host=new URL(url).hostname;
    const results=await Promise.allSettled([Deno.resolveDns(host,'A'),Deno.resolveDns(host,'AAAA')]);
    const ips=results.flatMap(r=>r.status==='fulfilled'?r.value:[]);
    if(!ips.length||!ips.every(publicIP))throw new Error('unsafe_source_address');
    const r=await fetch(url,{redirect:'manual',headers:{'User-Agent':'ai3d-source-preview/1.0','Accept':'text/html,application/rss+xml,application/atom+xml,application/xml'},signal:AbortSignal.timeout(10000)});
    if([301,302,303,307,308].includes(r.status)){await r.body?.cancel();url=new URL(r.headers.get('location')||'',url).href;continue;}
    if(!r.ok){await r.body?.cancel();throw new Error(`source_http_${r.status}`);}
    return {url,text:await limited(r,MAX_REMOTE)};
  }throw new Error('too_many_redirects');
}
async function inspection(html:string,url:string){
  const {load}=await import('npm:cheerio@1.1.2');
  const $=load(html,{xmlMode:/^(<\?xml|<rss|<feed)/i.test(html.trim())});
  const dates:string[]=[];const visit=(v:any)=>{if(!v||typeof v!=='object')return;if(Array.isArray(v)){v.forEach(visit);return;}if(/Article|BlogPosting|NewsArticle/.test(String(v['@type']||''))&&typeof v.datePublished==='string')dates.push(v.datePublished);if(v['@graph'])visit(v['@graph']);};
  $('script[type="application/ld+json"]').each((_,e)=>{try{visit(JSON.parse($(e).text()));}catch{}});$('script,style,nav,footer,aside').remove();
  const title=$('meta[property="og:title"]').attr('content')||$('title').first().text()||$('h1').first().text();
  let date=dates[0]||$('meta[property="article:published_time"],meta[name="date"],meta[itemprop="datePublished"]').first().attr('content')||$('article time[datetime]').first().attr('datetime')||null;
  const body=$('article,[itemprop="articleBody"],main').first().text().replace(/\s+/g,' ').trim();
  const links=[...$('item link,entry link,a[href]')].map(e=>$(e).attr('href')||$(e).text()).map(h=>{try{return new URL(h,url).href;}catch{return '';}}).filter(u=>publicURL(u)&&new URL(u).hostname===new URL(url).hostname);
  const today=new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Taipei'});const cutoff=new Date(`${today}T00:00:00Z`);const month=cutoff.getUTCMonth();cutoff.setUTCFullYear(cutoff.getUTCFullYear()-1);if(cutoff.getUTCMonth()!==month)cutoff.setUTCDate(0);
  const validDate=date&&/^\d{4}-\d{2}-\d{2}/.test(date)?date.slice(0,10):null;
  return {url,title:title.slice(0,200),source_date:validDate,date_eligible:validDate?validDate>=cutoff.toISOString().slice(0,10)&&validDate<=today:null,
    date_eligible_note:'日期僅作試讀；正式驗證由 Collector 的擷取器重新核對。',body_characters:body.length,body_preview:body.slice(0,240),article_links:[...new Set(links)].slice(0,5),
    note:'來源連通性預覽；正式 Collector 仍會重新擷取日期、正文、去重與審稿。列表／RSS 缺少文章日期並不代表文章本身不合格。'};
}

export async function handle(req:Request){
  const origin=req.headers.get('origin')||'';
  if(origin&&origin!==ORIGIN)return reply(403,{error:'origin_not_allowed'},origin);
  if(req.method==='OPTIONS')return reply(200,{ok:true},origin);
  if(req.method!=='POST')return reply(405,{error:'method_not_allowed'},origin);
  try{
    if(!await owner(req))return reply(403,{error:'owner_required'},origin);
    const body=JSON.parse(await limited(new Response(req.body),MAX_BODY));
    if(body.op==='lookup_url'||body.op==='recommend_url'){
      if(!publicURL(body.url))return reply(400,{error:'unsafe_source_url'},origin);
      const snap=await snapshot(github),settings=validateSettings(decode(snap.active));
      if(body.op==='recommend_url')return reply(200,await saveRecommendation(github,body,settings),origin);
      const data=await operations(github,async()=>{throw Error('actions_not_requested');});
      const registry=decode(await github(`/contents/data/candidates/published-registry-snapshot.json?ref=${data.head_sha}`));
      return reply(200,{...classifyURL(body.url,{...data,registry:registry.published_sources||[]},settings),head:data.head_sha,intake_sha:data.intake_sha},origin);
    }
    if(body.op==='operations'){
      const runs=async(date:string)=>{
        const from=new Date(date+'T00:00:00+08:00').toISOString();
        // Public run metadata does not require expanding the Contents-only credential.
        const r=await fetch(`https://api.github.com/repos/${REPO}/actions/runs?branch=main&created=${encodeURIComponent('>='+from)}&per_page=100`,{headers:{Accept:'application/vnd.github+json'},signal:AbortSignal.timeout(15000)});
        if(!r.ok)throw new Error('actions_unavailable');const data=JSON.parse(await limited(r,1500000));
        if(data.total_count>100||!Array.isArray(data.workflow_runs))throw new Error('incomplete_actions');
        return data.workflow_runs.filter((x:any)=>x.head_branch==='main'&&taipeiDate(new Date(x.created_at))===date);
      };
      return reply(200,await operations(github,runs),origin);
    }
    if(body.op==='selection'){
      if(!/^[a-f0-9]{40}$/.test(body.sha))return reply(400,{error:'missing_version'},origin);
      const controls=validateControls(body.controls);
      if(!controls.held_urls.every(publicURL))return reply(400,{error:'invalid_editorial_controls'},origin);
      const bytes=new TextEncoder().encode(JSON.stringify(controls,null,2)+'\n');let binary='';for(const b of bytes)binary+=String.fromCharCode(b);
      const result=await github(`/contents/${CONTROL_PATH}`,'PUT',{branch:'main',sha:body.sha,content:btoa(binary),message:'Update editorial holds [editorial-selection]'});
      return reply(200,{sha:result.content.sha,commit_url:result.commit.html_url},origin);
    }
    if(body.op==='load'){
      const snap=await snapshot(github);
      const status=await validationState(snap,settingsRuns);
      let metrics=null,monitor=null;
      for(const [path,key] of [['data/ops/source-metrics.json','metrics'],['data/ops/collection-monitor.json','monitor']]){
        try{const value=decode(await github(`/contents/${path}?ref=${snap.head}`));if(key==='metrics')metrics=value;else monitor=value;}catch(e){if(!(e instanceof Error)||e.message!=='repository_404')throw e;}
      }
      return reply(200,{settings:validateSettings(decode(snap.active)),sha:snap.active.sha,head:snap.head,pending_sha:snap.pending?.sha||null,validation:status,metrics,monitor},origin);
    }
    if(body.op==='save'){
      if(!/^[a-f0-9]{40}$/.test(body.sha))return reply(400,{error:'missing_version'},origin);
      return reply(200,await savePending(github,body),origin);
    }
    if(body.op==='activate')return reply(200,await activate(github,settingsRuns,commitSettings,body),origin);
    if(body.op==='history'){
      const rows=await github(`/commits?path=${SETTINGS}&sha=main&per_page=10`);
      return reply(200,{history:rows.map((r:any)=>({sha:r.sha,message:r.commit.message.split('\n')[0],date:r.commit.committer.date,actor:r.author?.login||r.commit.author?.name||null,url:r.html_url}))},origin);
    }
    if(body.op==='version'){
      if(!/^[a-f0-9]{40}$/.test(body.commit))throw new Error('invalid_version');
      const file=await github(`/contents/${SETTINGS}?ref=${body.commit}`);
      return reply(200,{settings:validateSettings(JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(file.content.replace(/\s/g,'')),c=>c.charCodeAt(0)))))},origin);
    }
    if(body.op==='probe'){
      const {text,url}=await external(body.url);const index=await inspection(text,url);const samples=[];
      for(const link of index.article_links.filter((x:string)=>x!==url).slice(0,3)){try{const page=await external(link);samples.push(await inspection(page.text,page.url));}catch(e){samples.push({url:link,error:e instanceof Error?e.message:'source_unavailable'});}}
      return reply(200,{...index,samples},origin);
    }
    return reply(400,{error:'unknown_operation'},origin);
  }catch(e){
    const message=e instanceof Error?e.message:'request_failed';
    const known=/^(admin_not_configured|version_conflict|validation_required|repository_\d+|source_http_\d+|unsafe_source_\w+|too_many_redirects|response_too_large|invalid_version)$/.test(message);
    return reply(message==='version_conflict'?409:known?503:400,{error:known?message:'invalid_request',...(!known?{message:message.slice(0,180)}:{})},origin);
  }
}
if (typeof Deno !== 'undefined' && typeof Deno.serve === 'function') Deno.serve(handle);
