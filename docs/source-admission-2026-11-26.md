# 新增來源的存取診斷

2026-11-26 的限量唯讀檢查使用既有 Collector 識別、HTTPS 公開 DNS 驗證與相同正文擷取器。Tripo 教學索引（中文與英文）、Meshy 繁體教學索引及 Unreal 官方頁回傳 HTTP 403，回應帶 `Cf-Mitigated: challenge`。Epic 社群首頁亦 403；其 learning 頁雖可回應，沒有通過抽樣的日期與正文。這是當次自動存取結果，不代表每個網路環境永遠無法讀取；今日較早 Collector 曾讀到 Tripo 文章。

不得以換偽裝識別、登入 cookie、代理或外部快取繞過驗證，也不能把搜尋摘要當作正文。正式取用時來源不可讀，就保留未發布的核准稿並等待後續正常 Collector 複核。

本次處理保留現行啟用設定：Tripo/Meshy 的待驗證 base URL 恢復現行根網址，Epic 待新增的 learning 入口移除，新增 Unreal 留在待驗證設定中但停用。這不宣稱解除外部 challenge，也不把無法驗證的入口直接啟用。其他站主設定保持原樣。來源驗證與 Collector 共用請求識別，並明確回報 `source-challenge-required`，避免把攔截誤認為內容不足。

日後只有官方公開入口在 GitHub 執行環境通過日期與正文驗證，才能再啟用。現有低量發布門檻、審稿門檻、單一 Publisher 與排程不變。
