(()=>{
  const KEY='ai3d-archive-nav-sticky';
  const NAV_SELECTOR='nav.global-category-nav';

  function repairCategoryLinks(){
    if(!document.body.classList.contains('category-page'))return;
    const nav=document.querySelector(NAV_SELECTOR);
    if(!nav)return;
    const category=document.body.dataset.category||'';

    // Category pages live at /YYYY-MM-DD/<category>/.
    // One level up is the selected date archive; two levels up is the site root.
    const home=nav.querySelector('.archive-nav-home');
    if(home)home.setAttribute('href','../../');

    nav.querySelectorAll('.archive-nav-arrow[href]').forEach(link=>{
      const match=link.getAttribute('href').match(/20\d{2}-\d{2}-\d{2}/);
      if(match&&category)link.setAttribute('href',`../../${match[0]}/${category}/`);
    });

    const top=nav.querySelector('a.global-category-link:not([data-category])');
    if(top)top.setAttribute('href','../#top');

    document.querySelectorAll('.category-bottom-nav a').forEach(link=>{
      if(link.textContent.trim()==='TOP5')link.setAttribute('href','../#top');
    });
  }

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

  function init(){
    repairCategoryLinks();
    restoreStickyNav();
  }

  document.addEventListener('click',rememberStickyNav,true);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();
