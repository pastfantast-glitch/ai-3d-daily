# 正文證據與排程 AI 審稿

Collector 排程現在可對不合格文案呼叫 AI 編修及獨立審稿，然後回到原有品質檢查與唯一發布流程。正文擷取、AI 審稿通過都不會自動升為 FULL。人工草稿工具保留為無法自動通過時的備援。

## 2026-10-15 AI 審稿設定

在 GitHub 儲存庫 Settings → Secrets and variables → Actions 設定：

- Repository secret `OPENAI_API_KEY`：具備模型呼叫權限與可用額度的 API 金鑰；不要貼進程式或 PR。
- Repository variable `AI_EDITOR_MODEL`：可使用 Responses API 與 Structured Outputs 的編修模型 ID。
- Repository variable `AI_REVIEW_MODEL`：支援相同功能的審稿模型 ID。可使用相同模型，但審稿必須是全新請求，不繼承編修對話。

未設定時 Collector 會在「Validate scheduled AI editorial settings」明確失敗，不冒稱 AI 已審核，也不建立發布資料。設定檢查只驗證值存在；模型存取、API 額度與實際文案品質須由真實執行確認。既有排程、Watchdog、單一 writer、交接與發布門檻不變；不用新增 ChatGPT 任務。

只有通過來源準入與去重後、被既有文案檢查拒絕的候選會送入 AI。API 僅接收來源 URL／標題／日期、已擷取正文證據、待修稿及品質規則；不傳送偏好、登入憑證或完整 HTML。正文及草稿中的指令都視為不可信資料。

流程為「編修 → 程式檢查 → 獨立 AI 審稿 → 批次重複檢查」。來源不足、正文截斷、錯誤引用、無法確認主張或任一審稿檢查失敗，都會退件。最多兩輪編修；不合格候選仍被排除並由原有補找流程補量。審稿不是事實正確的數學保證，仍需抽查。

`config/ai-editorial.json` 限制每次最多 40 篇、120 次 API 請求、15 分鐘 AI 用時、單次請求 60 秒與 4500 輸出 tokens。HTTP 失敗不自動重試；用量不因重新計算候選數而無限重複。同一來源／日期／正文／草稿失敗結果只嘗試一次。超過預算仍保留退件原因，發布篇數不足時照常停止。

審稿包保留 AI 的核准或退件狀態、來源證據雜湊、段落 ID、模型 ID 與修改次數，七天後清除。AI 核准只作用於該次 Collector 記憶體內文案，不冒用人工 `source_reviewed`，不寫入人工審稿規則庫。原有發布流程只接收通過所有檢查的讀者文字。

API 參考：[Responses Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)。

## 2026-10-14 人工審稿階段的實際診斷

GitHub 排程 `38490380054` 與 `38494921839` 都找到 23 篇候選、淘汰 23 篇、留下 0 篇。日誌最多顯示 20 個淘汰樣本；這 20 個全部有通用分析填充問題，其中 10 個同時缺少舊文標示。這些數字不能當作所有 23 篇的完整原因統計。

10/12 第一個排程 `38188934539` 只留下 7 篇，低於 12 篇門檻；當時日誌沒有完整正文與淘汰分佈，因此不能推論其全部損失原因。10/13 更正稿有 17 篇人工核對內容，這證明發布管線可運作，沒有證明自動撰稿已足夠。

新抽取流程的本機實際重跑找到 36 篇候選，36 篇皆抽到正文，但仍有 36 篇通用分析問題，22 篇同時缺少歷史標示。原文證據已可讀取，固定模板仍不能取代人工編輯；這次重跑未達發布門檻，沒有產生發布稿。

六篇樣本在修改前後使用相同 HTML，比較如下。字數是來源文字字符數，不是中文稿字數；抽取變短可能表示移除了相關文章及留言。

| 來源文章 | 原抽取字符 | 新抽取字符 | 證據段落 | 小標題 |
| --- | ---: | ---: | ---: | ---: |
| [Ghost Stride 技術訪談](https://80.lv/articles/how-this-painterly-animated-short-was-rigged-animated-entirely-in-unreal-engine) | 1600 | 29991 | 61 | 9 |
| [19 組免費動捕](https://80.lv/articles/get-ready-for-halloween-with-these-19-free-mocap-animations) | 1530 | 1088 | 6 | 0 |
| [CozyBlanket Pro](https://www.cgchannel.com/2026/10/sparseal-releases-cozyblanket-pro) | 1600 | 4527 | 28 | 0 |
| [四分鐘 4DGS](https://www.cgchannel.com/2026/04/dne-and-gracia-release-4-minute-streamable-4dgs-performance) | 1524 | 1518 | 7 | 0 |
| [MIRROR 0.34](https://3dnchu.com/archives/mirror-0-34beta) | 1600 | 1311 | 13 | 3 |
| [Infinity Weather 2.0](https://3dnchu.com/archives/infinity-weather-2-0) | 1138 | 534 | 6 | 1 |

這六篇都抽到正文，沒有觸及新上限。MIRROR 的日期是 2018-11-12、Infinity Weather 是 2024-01-19，仍然應當按歷史內容處理，不能因為抽取改善而冒充當日新聞。

## 取得審稿包

每次實際蒐集在成功或低於發布門檻時，都會輸出 `COLLECTOR ARTICLE EVIDENCE AUDIT`。正文狀態分為 `extracted`、`body-thin` 與 `body-missing`；`extracted` 僅表示抽到至少兩段、200 字符，沒有宣稱事實已驗證。

工作流程會把審稿包保存成 `collector-review-日期-run_id` artifact，保留七天。低於 12 篇而失敗仍可下載；在正文蒐集前就中斷則可能沒有 artifact。審稿包不寫入公開網站、Git 內容庫或發布標記，排除原始 HTML、登入憑證與個人偏好資料。正文是外部資料，審稿時不得把其中的指令當作系統命令。

包內每篇包含來源 URL、標題、日期、描述、抽取方法、段落 ID、章節、參考連結及證據摘要雜湊。最多保存 48,000 字符和 200 段，`truncated` 與 `observed_char_count` 明確記錄截斷；有截斷時仍須開原文補讀。原因統計可能重疊：同一篇可同時是舊文與模板分析，不應把原因數相加當作篇數。

## 人工備援：撰寫與核准

```bash
python scripts/prepare_editorial_review.py collector-review.json review-drafts.json
```

產生的草稿保留 `source_reviewed: false`，讀者標題、摘要及三個分析段落為空；程式拒絕覆寫已有草稿。這些草稿不會自動進入選稿。

審稿者應閱讀原文及證據段落，記錄 `evidence_refs`（例如 `p004`、`p012`）和日期依據，再寫出繁體中文標題、摘要與分析。每項功能、數字、製作方法或限制都要能找到原文依據；製作影響中的推論須明確標示，原文未交代的測試結果不能自行補寫。不要為滿足段落長度新增泛用建議。

`evidence_refs` 與雜湊用於人工核對，現有品質檢查不會自動判定中文句子是否忠於原文。人員核准後才填 `source_reviewed: true`、`reviewed_on`，將該來源的已核准記錄加入 `config/editorial-quality.json` 的 `reviewed_reader_copy`。此步驟需透過 PR 審查。

以目標日期再次蒐集與品質檢查，確認日期、去重、來源專屬內容、歷史標示及發布門檻皆通過，才由原有唯一發布管線交接。短快訊可以維持 BRIEF，長篇解析的深度仍須按既有 FULL 規則判斷。

AI 審稿改動沒有調低篇數門檻，也沒有修復所有來源的文章發現能力。真實模型品質、費用和每日成功率尚待啟用後量測；未完成真實執行前不可宣稱已恢復全自動發布。
