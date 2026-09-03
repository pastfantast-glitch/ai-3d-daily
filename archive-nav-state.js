(()=>{
  const KEY='ai3d-archive-nav-sticky';
  const NAV_SELECTOR='nav.global-category-nav';

  function navIsSticky(nav){
    if(!nav)return false;
    const rect=nav.getBoundingClientRect();
    return rect.top<=1 && window.scrollY>0;
  }

  function restoreStickyNav(){
    const nav=document.querySelector(NAV_SELECTOR);
    if(!nav)return;
    let restore=false;
    try{
      restore=sessionStorage.getItem(KEY)==='1';
      sessionStorage.removeItem(KEY);
    }catch(_){return;}
    if(!restore)return;
    requestAnimationFrame(()=>{
      const top=nav.getBoundingClientRect().top+window.scrollY;
      window.scrollTo({top,behavior:'auto'});
    });
  }

  function rememberStickyNav(event){
    const link=event.target.closest(`${NAV_SELECTOR} a`);
    if(!link)return;
    const nav=document.querySelector(NAV_SELECTOR);
    if(!navIsSticky(nav))return;
    const url=new URL(link.href,location.href);
    if(url.origin!==location.origin)return;
    try{sessionStorage.setItem(KEY,'1');}catch(_){}
  }

  document.addEventListener('click',rememberStickyNav,true);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',restoreStickyNav,{once:true});
  else restoreStickyNav();
})();
