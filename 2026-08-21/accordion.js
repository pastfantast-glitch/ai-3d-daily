document.addEventListener('DOMContentLoaded',()=>{
  const groups=[...document.querySelectorAll('details')];
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
    .dailybar{position:sticky;top:0;z-index:60;background:rgba(255,255,255,.97);backdrop-filter:blur(12px);border-bottom:1px solid #dfe4eb;box-shadow:0 4px 14px rgba(25,35,52,.05)}
    .dailybar-inner{width:min(980px,calc(100% - 32px));margin:auto;display:flex;align-items:stretch;min-height:48px;overflow:hidden}
    .daily-id{display:flex;align-items:center;gap:10px;flex:0 0 auto;padding-right:12px;border-right:1px solid #dfe4eb;background:rgba(255,255,255,.98);z-index:2}
    .daily-home{color:#202837;text-decoration:none;font-size:.78rem;font-weight:850;white-space:nowrap}
    .daily-date{color:#7a8290;font-size:.72rem;font-weight:750;white-space:nowrap}
    .daily-nav{display:flex;align-items:stretch;overflow-x:auto;scrollbar-width:none;min-width:0}
    .daily-nav::-webkit-scrollbar{display:none}
    .daily-nav a{position:relative;display:flex;align-items:center;white-space:nowrap;text-decoration:none;color:#596272;font-size:.78rem;font-weight:750;padding:0 11px;border-right:1px solid #edf0f4;transition:.15s ease}
    .daily-nav a:hover{color:#4e47c8;background:#f7f7fc}
    .daily-nav a.is-active{color:#594ed0;font-weight:900;background:#f7f6ff}
    .daily-nav a.is-active:after{content:"";position:absolute;left:10px;right:10px;bottom:0;height:3px;border-radius:3px 3px 0 0;background:#6658e8}
    #top,.category-deep,#try{scroll-margin-top:62px}
    @media(max-width:640px){
      .dailybar-inner{width:100%;padding-left:11px;min-height:46px}
      .daily-id{gap:7px;padding-right:9px}
      .daily-home{font-size:.75rem}
      .daily-date{font-size:.66rem}
      .daily-nav a{padding:0 10px;font-size:.74rem}
    }
    @media(max-width:420px){.daily-date{display:none}}
  `;
  document.head.append(style);

  const bar=document.createElement('nav');
  bar.className='dailybar';
  bar.setAttribute('aria-label','當日日報導覽');
  bar.innerHTML=`<div class="dailybar-inner">
    <div class="daily-id"><a class="daily-home" href="../">← 總覽</a><span class="daily-date">2026-08-21</span></div>
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

  const navLinks=[...bar.querySelectorAll('.daily-nav a')];
  const sectionIds=['top','ai','tools','engine','workflow','license','industry','stefan','try'];
  const sections=sectionIds.map(id=>document.getElementById(id)).filter(Boolean);

  const activate=id=>{
    navLinks.forEach(link=>link.classList.toggle('is-active',link.dataset.section===id));
    const active=navLinks.find(link=>link.dataset.section===id);
    active?.scrollIntoView({behavior:'smooth',block:'nearest',inline:'center'});
  };

  navLinks.forEach(link=>link.addEventListener('click',()=>activate(link.dataset.section)));

  let ticking=false;
  const updateActive=()=>{
    const y=window.scrollY+84;
    let current=sections[0]?.id||'top';
    sections.forEach(section=>{if(section.offsetTop<=y)current=section.id;});
    activate(current);
    ticking=false;
  };
  window.addEventListener('scroll',()=>{
    if(!ticking){window.requestAnimationFrame(updateActive);ticking=true;}
  },{passive:true});
  updateActive();
});
