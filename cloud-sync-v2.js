(()=>{
  // Compatibility shim for pages cached before cloud-sync-v3.
  // v3 owns pairing, automatic pull/push, and same-tab state application.
  const url=new URL('./cloud-sync-v3.js?v=20260915-r6',import.meta.url);
  import(url.href).catch(err=>console.warn('AI3D cloud sync v3 unavailable',err));
})();
