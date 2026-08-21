document.addEventListener('DOMContentLoaded',()=>{
  const report={
    date:'2026-08-21',
    previous:null,
    next:null,
    statuses:[
      {match:'Meshy',label:'UPDATE',type:'update'},
      {match:'Unreal Engine 5.8',label:'持續追蹤',type:'track'},
      {match:'UE 5.8',label:'持續追蹤',type:'track'},
      {match:'Unity AI',label:'持續追蹤',type:'track'},
      {match:'Blender 5.2',label:'持續追蹤',type:'track'},
      {match:'Mudbox',label:'UPDATE',type:'update'},
      {match:'Tripo',label:'持續追蹤',type:'track'},
      {match:'3ds Max',label:'持續追蹤',type:'track'},
      {match:'AI 生成不是終點',label:'持續追蹤',type:'track'},
      {match:'程序化場景',label:'持續追蹤',type:'track'},
      {match:'3D Artist 職務持續技術化',label:'持續追蹤',type:'track'},
      {match:'最值得追的內容',label:'持續追蹤',type:'track'}
    ]
  };

  document.body.classList.add('archive-page');
  const siteHead=document.querySelector('.site-head');
  if(siteHead){
    const title=siteHead.querySelector('h1');
    const intro=siteHead.querySelector('.intro');
    if(title) title.textContent=`${report.date} 歷史日報`;
    if(intro) intro.textContent='完整保存當日情報、Production 分析、實測方式與來源。平常閱讀以首頁為主；這裡作為歷史快照與查閱資料庫。';
    const note=document.createElement('div');
    note.className='archive-note';
    note.textContent='ARCHIVE DATABASE · 當日完整快照';
    const stats=siteHead.querySelector('.stats');
    if(stats) stats.before(note);
  }
  const top=document.getElementById('top');
  if(top){
    const kicker=top.querySelector('.section-kicker');
    const heading=top.querySelector('h2');
    if(kicker) kicker.textContent='ARCHIVE SNAPSHOT';
    if(heading) heading.textContent='當日必看 TOP 5';
  }

  const groups=[...document.querySelectorAll('details')];
  groups.forEach(item=>{item.open=false;});
  groups.forEach(item=>{
    item.addEventListener('toggle',()=>{
      if(!item.open)return;
      groups.forEach(other=>{if(other!==item&&other.open)other.open=false;});
    });
  });

  const originalNav=document.querySelector('.jumpbar');
  if(originalNav) originalNav.hidden=true;

  const style=document.createElement('style');
  style.textContent=`
    .archive-page .site-head{background:#fafbfc}
    .archive-note{display:inline-flex;margin:18px 0 0;padding:6px 9px;border:1px solid #dfe3ea;border-radius:999px;background:#fff;color:#68717f;font-size:.67rem;font-weight:900;letter-spacing:.05em}
    .archive-page details:not([open]) .detail-body{display:none}
    .dailybar{position:sticky;top:0;z-index:60;background:rgba(255,255,255,.97);backdrop-filter:blur(12px);border-bottom:1px solid #dfe4eb;box-shadow:0 4px 14px rgba(25,35,52,.05)}
    .dailybar-inner{width:min(980px,calc(100% - 32px));margin:auto;display:flex;align-items:stretch;min-height:48px;overflow:hidden}
    .daily-id{display:flex;align-items:center;gap:8px;flex:0 0 auto;padding-right:12px;border-right:1px solid #dfe4eb;background:rgba(255,255,255,.98);z-index:2}
    .daily-home{color:#202837;text-decoration:none;font-size:.78rem;font-weight:850;white-space:nowrap}
    .date-nav{display:flex;align-items:center;gap:5px;white-space:nowrap}
    .daily-date{color:#6d7583;font-size:.72rem;font-weight:800;white-space:nowrap}
    .day-link{display:flex;align-items:center;justify-content:center;min-width:23px;height:26px;border-radius:7px;color:#5a6371;text-decoration:none;font-size:.74rem;font-weight:900}
    .day-link:hover{background:#f1f2f7;color:#594ed0}
    .daily-nav{display:flex;align-items:stretch;overflow-x:auto;scrollbar-width:none;min-width:0}
    .daily-nav::-webkit-scrollbar{display:none}
    .daily-nav a{position:relative;display:flex;align-items:center;white-space:nowrap;text-decoration:none;color:#596272;font-size:.78rem;font-weight:750;padding:0 11px;border-right:1px solid #edf0f4;transition:.15s ease}
    .daily-nav a:hover{color:#4e47c8;background:#f7f7fc}
    .daily-nav a.is-active{color:#594ed0;font-weight:900;background:#f7f6ff}
    .daily-nav a.is-active:after{content:"";position:absolute;left:10px;right:10px;bottom:0;height:3px;border-radius:3px 3px 0 0;background:#6658e8}
    .news-status{display:inline-flex;align-items:center;min-height:20px;padding:2px 7px;border-radius:999px;font-size:.62rem;font-weight:900;letter-spacing:.04em;white-space:nowrap}
    .news-status.status-new{background:#eaf7f0;color:#20764d}
    .news-status.status-update{background:#fff0dd;color:#9b5b18}
    .news-status.status-track{background:#eef1f6;color:#5c6675}
    #top,.category-deep,#try{scroll-margin-top:62px}
    @media(max-width:640px){
      .dailybar-inner{width:100%;padding-left:11px;min-height:46px}
      .daily-id{gap:6px;padding-right:8px}
      .daily-home{font-size:.75rem}
      .daily-date{font-size:.66rem}
      .day-link{min-width:21px;height:24px}
      .daily-nav a{padding:0 10px;font-size:.74rem}
    }
    @media(max-width:440px){.daily-date{font-size:.63rem}.daily-home{font-size:0}.daily-home:after{content:'← 首頁';font-size:.73rem}}
  `;
  document.head.append(style);

  const prev=report.previous?`<a class="day-link" href="../${report.previous}/" aria-label="前一日日報">←</a>`:'';
  const next=report.next?`<a class="day-link" href="../${report.next}/" aria-label="後一日日報">→</a>`:'';
  const bar=document.createElement('nav');
  bar.className='dailybar';
  bar.setAttribute('aria-label','歷史日報導覽');
  bar.innerHTML=`<div class="dailybar-inner">
    <div class="daily-id"><a class="daily-home" href="../">← 首頁</a><div class="date-nav">${prev}<span class="daily-date">${report.date}</span>${next}</div></div>
    <div class="daily-nav">
      <a href="#top" data-section="top">TOP 5</a>
      <a href="#ai" data-section="ai">生成式 AI</a>
      <a href="#tools" data-section="tools">3D 工具</a>
      <a href="#engine" data-section="engine">引擎</a>
      <a href="#workflow" data-section="workflow">流程</a>
      <a href="#license" data-section="license">授權</a>
      <a href="#industry" data-section="industry">產業</a>
      <a href="#stefan" data-section="stefan">Stefan</a>
      <a href="#try" data-section="try">實測</a>
    </div>
  </div>`;
  document.body.prepend(bar);

  const reportCards=[...document.querySelectorAll('.news,.category-news')];
  reportCards.forEach(card=>{
    const text=card.textContent||'';
    const rule=report.statuses.find(entry=>text.includes(entry.match));
    if(!rule)return;
    const meta=card.querySelector('.meta');
    if(!meta||meta.querySelector('.news-status'))return;
    const badge=document.createElement('span');
    badge.className=`news-status status-${rule.type}`;
    badge.textContent=rule.label;
    meta.append(badge);
  });

  const navLinks=[...bar.querySelectorAll('.daily-nav a')];
  const sectionIds=['top','ai','tools','engine','workflow','license','industry','stefan','try'];
  const sections=sectionIds.map(id=>document.getElementById(id)).filter(Boolean);

  const activate=(id,scrollNav=false)=>{
    navLinks.forEach(link=>link.classList.toggle('is-active',link.dataset.section===id));
    const active=navLinks.find(link=>link.dataset.section===id);
    if(scrollNav) active?.scrollIntoView({behavior:'smooth',block:'nearest',inline:'center'});
  };

  navLinks.forEach(link=>link.addEventListener('click',()=>activate(link.dataset.section,true)));

  let ticking=false;
  const updateActive=()=>{
    const y=window.scrollY+84;
    let current=sections[0]?.id||'top';
    sections.forEach(section=>{if(section.offsetTop<=y)current=section.id;});
    activate(current,false);
    ticking=false;
  };
  window.addEventListener('scroll',()=>{
    if(!ticking){window.requestAnimationFrame(updateActive);ticking=true;}
  },{passive:true});
  updateActive();
});
