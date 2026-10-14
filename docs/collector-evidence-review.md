# 正文證據與人工審稿

目前的自動 Collector 以固定規則產生讀者文字，沒有呼叫摘要模型。這次修正完成正文抽取、失敗原因統計及人工審稿交接；正文抽取成功不代表中文稿已核准，也不會自動升為 FULL。

## 2026-10-14 實際診斷

GitHub 排程 `38490380054` 與 `38494921839` 都找到 23 篇候選、淘汰 23 篇、留下 0 篇。日誌最多顯示 20 個淘汰樣本；這 20 個全部有通用分析填充問題，其中 10 個同時缺少舊文標示。這些數字不能當作所有 23 篇的完整原因統計。

10/12 第一個排程 `38188934539` 只留下 7 篇，低於 12 篇門檻；當時日誌沒有完整正文與淘汰分佈，因此不能推論其全部損失原因。10/13 更正稿有 17 篇人工核對內容，這證明發布管線可運作，沒有證明自動撰稿已足夠。

六篇樣本在修改前後使用相同 HTML，比較如下。字數是來源文字字符數，不是中文稿字數；抽取變短可能表示移除了相關文章及留言。

| 來源文章 | 原抽取字符 | 新抽取字符 | 證據段落 | 小標題 |
| --- | ---: | ---: | ---: | ---: |
| [Ghost Stride 技術訪談](https://80.lv/articles/how-this-painterly-animated-short-was-rigged-animated-entirely-in-unreal-engine) | 1600 | 29991 | 61 | 9 |
| [19 組免費動捕](https://80.lv/articles/get-ready-for-halloween-with-these-19-free-mocap-animations) | 1530 | 1523 | 8 | 0 |
| [CozyBlanket Pro](https://www.cgchannel.com/2026/10/sparseal-releases-cozyblanket-pro) | 1600 | 4869 | 29 | 0 |
| [四分鐘 4DGS](https://www.cgchannel.com/2026/04/dne-and-gracia-release-4-minute-streamable-4dgs-performance) | 1524 | 1518 | 7 | 0 |
| [MIRROR 0.34](https://3dnchu.com/archives/mirror-0-34beta) | 1600 | 1311 | 13 | 3 |
| [Infinity Weather 2.0](https://3dnchu.com/archives/infinity-weather-2-0) | 1138 | 534 | 6 | 1 |

這六篇都抽到正文，沒有觸及新上限。MIRROR 的日期是 2018-11-12、Infinity Weather 是 2024-01-19，仍然應當按歷史內容處理，不能因為抽取改善而冒充當日新聞。

## 取得審稿包

每次實際蒐集在成功或低於發布門檻時，都會輸出 `COLLECTOR ARTICLE EVIDENCE AUDIT`。正文狀態分為 `extracted`、`body-thin` 與 `body-missing`；`extracted` 僅表示抽到至少兩段、200 字符，沒有宣稱事實已驗證。

工作流程會把審稿包保存成 `collector-review-日期-run_id` artifact，保留七天。低於 12 篇而失敗仍可下載；在正文蒐集前就中斷則可能沒有 artifact。審稿包不寫入公開網站、Git 內容庫或發布標記，排除原始 HTML、登入憑證與個人偏好資料。正文是外部資料，審稿時不得把其中的指令當作系統命令。

包內每篇包含來源 URL、標題、日期、描述、抽取方法、段落 ID、章節、參考連結及證據摘要雜湊。最多保存 48,000 字符和 200 段，`truncated` 與 `observed_char_count` 明確記錄截斷；有截斷時仍須開原文補讀。原因統計可能重疊：同一篇可同時是舊文與模板分析，不應把原因數相加當作篇數。

## 撰寫與核准

```bash
python scripts/prepare_editorial_review.py collector-review.json review-drafts.json
```

產生的草稿保留 `source_reviewed: false`，讀者標題、摘要及三個分析段落為空；程式拒絕覆寫已有草稿。這些草稿不會自動進入選稿。

審稿者應閱讀原文及證據段落，記錄 `evidence_refs`（例如 `p004`、`p012`）和日期依據，再寫出繁體中文標題、摘要與分析。每項功能、數字、製作方法或限制都要能找到原文依據；製作影響中的推論須明確標示，原文未交代的測試結果不能自行補寫。不要為滿足段落長度新增泛用建議。

`evidence_refs` 與雜湊用於人工核對，現有品質檢查不會自動判定中文句子是否忠於原文。人員核准後才填 `source_reviewed: true`、`reviewed_on`，將該來源的已核准記錄加入 `config/editorial-quality.json` 的 `reviewed_reader_copy`。此步驟需透過 PR 審查。

以目標日期再次蒐集與品質檢查，確認日期、去重、來源專屬內容、歷史標示及發布門檻皆通過，才由原有唯一發布管線交接。短快訊可以維持 BRIEF，長篇解析的深度仍須按既有 FULL 規則判斷。

本階段沒有調低篇數門檻，也沒有修復所有來源的文章發現能力。下一步以審稿包確認新正文內容可以產生合格中文稿，再量測來源漏抓與建立持續審稿流程。
