(()=>{
  // Compatibility shim for pages cached before the single-owner sync migration.
  // Never create or use per-device sync accounts here.
  import(new URL('./cloud-sync-owner.js?v=20260915-owner-v1',import.meta.url).href)
    .catch(err=>console.warn('AI3D owner cloud sync unavailable',err));
})();
