# 來源試收與備稿產量

2026-11-26：CG Channel 的 publisher feed 會導向 HTTP。`publisher_feeds.py` 只把其精確網址及 BlenderNation 精確訂閱網址對應到出版者指定的 FeedBurner HTTPS 版本；不接受任意外部 feed、不放寬公開 DNS／HTTPS／轉址限制。文章仍須屬於原註冊來源，RSS 摘要不作為正文證據。來源設定保留出版者入口，因此網站管理與來源歸屬不會變成 FeedBurner。

Godot、Khronos、BlenderNation 先經 `collection-pending.json` 的實際正文／日期驗證，再套用為 AI／3D 試收來源。Godot 原文章使用唯一的 `span.date[data-post-date]`，不以 feed 更新日期替代；Khronos feed 連結解碼 HTML entity 後再去除追蹤參數，仍保留真正選擇內容的 query。分類、正文、12 個月期限、去重與人工來源審稿規則不變。

## 同一 Collector 的發布後試收

既有 `daily-collector.yml` 的手動 `source_trial=true` 只接受台北當日、已通過嚴格 DONE 檢查、無 active Publisher/handoff。沿用 `autonomous-daily-collector` concurrency，不新增 workflow、排程或 writer。只試收四個已啟用來源，每個最多 8 篇及 2 篇來源內補查；最多 40 個候選。

此模式只輸出同一格式的 `collector-review-日期-run_id` 七日 artifact 與既有監測 metadata。禁止建立 collection-session、canonical、發布 marker 或 collector-target；既有 handoff 在沒有 target 時安全停止。因此試收成功不等於新增日報或自動核准。ChatGPT 依原 artifact 與官方 run.json 逐篇審稿、第二輪來源核對，另以不可變的 `YYYY-MM-DD-RUN_ID.json` reserve PR 入庫。下次正常 Collector 才重新擷取、比對正文 hash／日期、去重與品質後，交由唯一 Publisher 發布。

## 追蹤口徑

`collection-monitor.json` 保留近 30 天、最多 60 個 run 的 `yield_history`，同一 run 重寫會取代原觀測，不累加。每批記錄來源候選、正文可讀、待審、核准、品質去重通過、入選、剩餘合格；試收與日常分開標示。不同 run 可能重複看到相同候選，不可把候選數相加當作唯一文章數。

`yield_inventory` 記錄近 30 日審稿檔的唯一核准 URL、其中經 DONE／commit 驗證的已發布數、目前已審未發布且未被暫停／超期／停用的待複核庫存。沒有取得的量測不得補零；核准庫存仍須當日重新讀來源。快照在 Collector 完成時更新，審稿 PR 後即時庫存仍看既有備稿管理。

後臺來源管理顯示上述三項庫存數字及最近七次實際供稿觀測。七次觀測不是連續七天，也不代表來源已達穩定性驗收；需跨日資料才能判斷長期供稿量。目標維持每日 30 篇、備稿約兩天份，沒有降低發布品質或篇數門檻。
