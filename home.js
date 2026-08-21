document.addEventListener('DOMContentLoaded',()=>{
  const search=document.querySelector('#news-search');
  const filters=[...document.querySelectorAll('.filter')];
  const items=[...document.querySelectorAll('.searchable')];
  const empty=document.querySelector('#empty-state');
  let active='all';
  const apply=()=>{
    const q=(search?.value||'').trim().toLowerCase();
    let shown=0;
    items.forEach(item=>{
      const categories=(item.dataset.category||'').split(/\s+/);
      const text=(item.dataset.search||item.textContent||'').toLowerCase();
      const okCategory=active==='all'||categories.includes(active);
      const okSearch=!q||text.includes(q);
      const visible=okCategory&&okSearch;
      item.hidden=!visible;
      if(visible)shown++;
    });
    if(empty)empty.hidden=shown!==0;
  };
  filters.forEach(btn=>btn.addEventListener('click',()=>{
    active=btn.dataset.filter||'all';
    filters.forEach(x=>x.classList.toggle('is-active',x===btn));
    apply();
  }));
  search?.addEventListener('input',apply);

  const analysis={
    meshy:{
      match:['Meshy 7','Meshy 7：'],
      body:`<h4>更新內容</h4><p>Meshy 7 把控制 Geometry 的多視圖參考與控制 Texture 的參考圖拆開，讓四視圖負責輪廓、比例與結構，彩色設定圖則專心控制材質。這解決了過去線稿、背視圖與不完整材質資訊彼此干擾的問題。</p><h4>對 3D 美術的影響</h4><p>角色裝備、武器、載具與 Prop 最直接受益。合理流程會變成「四視圖控制 Geometry → 彩色設定控制 Texture → AI 生成 → Blender / Max Cleanup → Unity / Unreal」，更像正式資產流程，而不是只追求 Turntable 好看。</p><h4>Production 評估</h4><p>適合作為 Blockout、High-poly 起點與材質 First Pass；目前仍需人工檢查 Topology、UV、Normal、分件與 Silhouette。真正要量化的是 AI 生成＋Cleanup 是否比人工 Blockout 總時間更短。</p><h4>適合誰</h4><p>角色建模、Prop Artist、場景美術、3D Generalist，以及正在建立 AI Asset SOP 的團隊。</p><h4>20 分鐘實測</h4><p>挑一個已有完成答案的 Prop，四視圖只控制 Geometry、2–3 張彩色設定控制 Texture。生成後只記 Silhouette、硬表面轉角、UV、材質分區與 Cleanup 分鐘數，再和人工 Blockout 比較。</p><a class="home-analysis-source" href="https://docs.meshy.ai/en/api/changelog" target="_blank" rel="noreferrer">官方來源 ↗</a>`
    },
    unreal:{
      match:['UE 5.8','Unreal Engine 5.8'],
      body:`<h4>更新內容</h4><p>UE 5.8 持續把 PCG、Mesh Terrain、植被與大型世界相關能力往規則化製作整合。對 Environment Artist 而言，重點不是多一個工具，而是可以把部分逐顆擺設轉成 Modular Kit、Variation、Density、Mask 與 Scatter Rule。</p><h4>對 3D 美術的影響</h4><p>大型地圖、開放世界與高重複資產場景會最有感。美術工作的價值會從「擺得快」移向「規則設計得穩、Variation 做得夠、例外情況處理得好」。</p><h4>Production 評估</h4><p>PCG 已經值得正式測試，但 Mesh Terrain 等較新的流程仍應保留 fallback。導入前要一起看控制力、修改成本、Shader / GPU 成本與團隊學習曲線，而不是只看生成速度。</p><h4>適合誰</h4><p>Environment Artist、Level Artist、TA、World Building 團隊與負責大型場景效能的人。</p><h4>20 分鐘實測</h4><p>在一個 20×20 公尺測試區，用同一批 2–3 種 Prop 做人工擺設與 PCG 兩版，比較時間、重複感、局部手改便利性，以及 Shader Complexity / Stat GPU 結果。</p><a class="home-analysis-source" href="https://www.unrealengine.com/news/unreal-engine-5-8-is-now-available" target="_blank" rel="noreferrer">官方來源 ↗</a>`
    },
    unity:{
      match:['Unity AI'],
      body:`<h4>更新內容</h4><p>Unity AI 的方向從單純聊天與產生 C#，往能理解 Scene、GameObject、Component 與 Project Context 的 Agent 前進。這使它有機會直接針對專案內資產與設定做檢查。</p><h4>對 3D 美術的影響</h4><p>對美術最有價值的使用方式不是「幫我做完整遊戲」，而是 Project-aware QA：找出 Texture Import、LOD、Material、Renderer、Prefab 或命名設定的異常，把大量重複檢查交給 Agent。</p><h4>Production 評估</h4><p>目前建議從只讀分析開始，不要先開放大量自動修改。真正要測的是它能抓到多少已知問題、假陽性比例多高，以及報告是否足以讓 Artist 或 TA 快速採取行動。</p><h4>適合誰</h4><p>Unity 3D Artist、TA、Lead、Technical Artist，以及需要做資產規範檢查的團隊。</p><h4>20 分鐘實測</h4><p>要求 Agent 掃描目前 Scene 的 Mesh Renderer、Material、Texture 與 LOD，只輸出問題清單、不做修改。事先準備幾個已知錯誤，再比對它的命中率與誤判。</p><a class="home-analysis-source" href="https://unity.com/blog/unity-ai-assistant-ask-plan-agent-mode-explained" target="_blank" rel="noreferrer">官方來源 ↗</a>`
    },
    blender:{
      match:['Blender 5.2'],
      body:`<h4>更新內容</h4><p>Blender 5.2 LTS 的核心價值是長期穩定支援，而不是單一功能比一般版本更多。團隊可以把 Add-on、Python、Scene Units、FBX / USD、Export Preset 與檔案版本固定在同一個基準。</p><h4>對 3D 美術的影響</h4><p>對正在從 Max / Maya 導入 Blender 的團隊，統一版本能明顯降低「每個人環境不同」造成的 Export、Plugin 與 Script 問題，也比較適合建立可重現的 SOP。</p><h4>Production 評估</h4><p>值得作為正式候選基準版，但先不要只因為是 LTS 就全員切換。應先驗證角色、場景、Rig、Morph、材質與引擎輸出，確認常用 Add-on 與 Python 工具沒有阻斷問題。</p><h4>適合誰</h4><p>Blender 導入團隊、角色／場景 Lead、TA、Pipeline TD，以及需要維護跨 DCC Export SOP 的人。</p><h4>20 分鐘實測</h4><p>用一個真實資產跑 Max → Blender 5.2 → Unity / Unreal，集中檢查 Scale、Axis、Normal、UV、Material Slot、Pivot、Skeleton 與 Root 是否一致。</p><a class="home-analysis-source" href="https://www.blender.org/download/lts/" target="_blank" rel="noreferrer">官方來源 ↗</a>`
    },
    mudbox:{
      match:['Mudbox'],
      body:`<h4>更新內容</h4><p>Autodesk 推進 Mudbox 的停售時程，這已經不是一般價格變化，而是產品生命週期正在結束的訊號。對既有團隊來說，問題會逐漸轉成歷史資產與舊流程是否還能長期重現。</p><h4>對 3D 美術的影響</h4><p>仍使用 Mudbox Sculpt、Texture Paint、Bake Preset、Script 或舊檔案的專案不必立即停用，但現在就應盤點依賴；新專案則不適合再把 Mudbox 當長期核心。</p><h4>Production 評估</h4><p>最大的風險不是「今天不能用」，而是未來人員、授權、OS、外掛或檔案相容性變化後，舊 SOP 難以重現。遷移測試應包含功能、時間與歷史資產兼容，而不是只找一套功能表看起來相似的軟體。</p><h4>適合誰</h4><p>仍維護 Mudbox 舊案的角色／材質團隊、Lead、Pipeline TD 與外包管理。</p><h4>20 分鐘實測</h4><p>挑一個歷史 Mudbox 資產，用 ZBrush 或 Blender 重做同一段 Sculpt / Paint / Export，記錄缺失功能、檔案轉換問題與實際時間差。</p><a class="home-analysis-source" href="https://www.autodesk.com/products/mudbox/buy" target="_blank" rel="noreferrer">官方來源 ↗</a>`
    }
  };

  const findAnalysis=text=>Object.values(analysis).find(item=>item.match.some(key=>text.includes(key)));
  const makeDetails=(data,label='完整分析')=>{
    const details=document.createElement('details');
    details.className='home-full-analysis';
    details.innerHTML=`<summary>${label}</summary><div class="home-analysis-body">${data.body}</div>`;
    return details;
  };

  document.querySelectorAll('.week-topic').forEach(card=>{
    const data=findAnalysis(card.textContent||'');
    if(data&&!card.querySelector('.home-full-analysis')) card.append(makeDetails(data,'完整分析'));
  });

  document.querySelectorAll('.top-item').forEach(link=>{
    const data=findAnalysis(link.textContent||'');
    if(!data)return;
    const article=document.createElement('article');
    article.className='top-item top-item-expandable';
    article.innerHTML=link.innerHTML;
    article.querySelector(':scope > strong')?.remove();
    const content=article.querySelector(':scope > div');
    if(content) content.append(makeDetails(data,'完整分析'));
    link.replaceWith(article);
  });

  const analysisDetails=[...document.querySelectorAll('.home-full-analysis,.more-card details')];
  analysisDetails.forEach(item=>{
    item.addEventListener('toggle',()=>{
      if(!item.open)return;
      analysisDetails.forEach(other=>{
        if(other!==item&&other.open)other.open=false;
      });
    });
  });

  const style=document.createElement('style');
  style.textContent=`
    .home-full-analysis{margin-top:12px;border:1px solid #e1e5eb;border-radius:10px;background:#fafbfc;overflow:hidden}
    .home-full-analysis>summary{padding:10px 12px;cursor:pointer;color:#505968;font-size:.76rem;font-weight:900;list-style:none}
    .home-full-analysis>summary::-webkit-details-marker{display:none}
    .home-full-analysis>summary:after{content:'＋';float:right;color:#777f8d}
    .home-full-analysis[open]>summary{border-bottom:1px solid #e2e6ec;background:#f6f7fa}
    .home-full-analysis[open]>summary:after{content:'－'}
    .home-analysis-body{padding:13px 14px}
    .home-analysis-body h4{margin:13px 0 5px;font-size:.82rem;line-height:1.4;color:#343d4c}
    .home-analysis-body h4:first-child{margin-top:0}
    .home-analysis-body p{margin:0;color:#596371;font-size:.81rem;line-height:1.72}
    .home-analysis-source{display:inline-flex;margin-top:13px;color:#5550b8;text-decoration:none;font-size:.73rem;font-weight:850}
    .week-topic>.home-full-analysis{margin-top:13px}
    .top-item-expandable{cursor:default}
    .top-item-expandable:hover{background:#fff}
    .top-item-expandable>div{min-width:0}
    .top-item-expandable .home-full-analysis{max-width:780px}
    @media(max-width:760px){.home-analysis-body{padding:12px}.home-analysis-body p{font-size:.79rem}.home-full-analysis>summary{padding:9px 11px}}
  `;
  document.head.append(style);
});