(()=>{
  // Compatibility shim for pages cached before cloud-sync-v2.
  // Never perform network, DOM observation, registration, pull, or reload here.
  const url=new URL('./cloud-sync-v2.js?v=20260915-r4',import.meta.url);
  import(url.href).catch(err=>console.warn('AI3D passive cloud sync unavailable',err));
})();
