# 分類與分頁管理（2026-11-27）

「新增分類」管理首頁 TOP5 旁的導覽分頁。既有 AI 生成、3D 製作、3D 動作、遊戲引擎、新技術 / Case、Blender / DCC 均為可編輯分類節點。TOP5 是固定跨分類精選節點，不能接入來源或改成第二個收集流程。

生效設定仍位於 `config/collection-admin.json`；新增可選 `navigation`，舊版 `topics` 與歷史 canonical 快照保留相容。首次遷移維持全部六分類的既有名稱、來源可用範圍與顯示狀態，不改文章 ID 或收藏。已套用的 pending 快照同步遷移；真正尚未套用的草稿不得覆蓋。

- 畫布與列表共用同一草稿，可改名稱、說明、排序、啟用、導覽顯示、空分類隱藏、收錄／排除關鍵字。新分類預設隱藏空白分頁。
- 來源可連到多個分類；移除最後一條連線會暫停來源，原文與收藏保留。連線只限制候選範圍，仍須製作相關性、12 個月日期、正文證據、去重與審稿檢查。
- 既有分類留白時使用原本分類器；自訂分類需要至少一組關鍵字。Collector 保留 `navigation_category_ids`，避免原文翻譯後關鍵字不見而漏列。交接驗證檢查歸屬是否在當次設定及來源連線中。
- 人工加入／排除使用原文網址，每分類各最多 200 筆；同網址不能同時加入與排除。這只修正已發布文章的呈現，不核准未審稿、不寫 canonical。
- 預覽使用最新已發布 canonical 與表單規則，右側顯示匹配數及文章；一篇可出現在多分類，總篇數仍按唯一 ID 計算。舊文既有分類歸屬保留，若需移除請使用人工排除。
- 儲存 → 既有 GitHub 設定 CI → 套用，保留版本衝突、三方合併、復原／重做；未通過不得生效。生效後導覽呈現使用新設定，下一次 Collector 使用新供稿規則。
- 最新分類網址沿用 `/?view=分類代號`，圖片卡片保留來源日期、分析與收藏，提供搜尋及每次十篇展開。舊日期 `YYYY-MM-DD/分類/` 與既有 `/topics/` 歷史網址保留，不重寫歷史頁。

驗證包括分類／去重／人工覆寫、連線與遠端合併、Collector 相關性及期限、交接歸屬、既有設定存取權限及正式發布隔離重播。圖形介面測試使用不連線正式後端的本機 fixture；正式登入、庫存及分類節點另於部署後查核。

## 舊版收集主題契約（相容層）

以下保留供既有資料與工具相容使用；使用者入口已改為上述分類管理。

# Source and topic administration, first version

The AI/3D homepage keeps its existing publication contract. `/admin/` manages public collection settings; `/topics/` links to separate topic pages. Authentication reuses the existing Supabase owner account. This feature does not introduce a second Collector, Publisher, schedule, model API or browser-held GitHub credential.

## Operations

- Add/edit/pause/resume a source and bind it to one or more topics. Configure up to five HTTPS article indexes or RSS/Atom feeds on that domain or its subdomains.
- Add a topic with a stable URL identifier, inclusion/exclusion keywords, a 1–12 calendar month source window and a per-edition target of 1–30. New sources/topics default to paused. AI/3D remains enabled and keeps its existing target and release floor.
- Preview connectivity, source date, extracted body length and a short excerpt. Preview is not editorial approval or formal discovery.
- Review settings commits and preview a previous version as a local draft. Restoring uses the same save, exact-main validation and activation gates. Concurrent writes fail without retry; the workspace can compare and rebase disjoint local changes before a new explicit save.
- Pausing does not delete any published article. Changes affect the next existing Collector run and do not launch a run from the browser.

`config/collection-admin.json` is public and contains no credentials, preferences or source bodies. Settings changes are staged in `config/collection-pending.json`; only validated activation writes `config/collection-admin.json`. Editorial holds retain their separate fixed path. Its source and topic policy is also enforced in Python before collection. The legacy hybrid policy still controls bounded crawling, ranking, dedupe and release minimums. The selected configuration is copied into the canonical edition as an immutable validation snapshot, so subsequent source edits cannot invalidate an in-flight handoff or an old archive.

## Collection and publication

The Collector matches original source evidence against topic keywords and source bindings, applies the source-date window, then runs the existing review and reader-quality checks. Unreviewed articles remain in the existing review artifact. Topic keywords never approve reader copy. The review artifact includes topic IDs for editorial context.

`items` remains the AI/3D edition. `topic_items` contains additional approved articles; `topic_ids` records their selected topic memberships. The same article is stored only once per edition, even if it belongs to several topics. Both sets participate in the Published Registry, source identity checks and review gate. Surplus approved articles remain in the existing reserve and are rechecked before later use.

The first version publishes topics in the same successful daily transaction as AI/3D. Other topics cannot fill the AI/3D minimum. It does not promise an independent daily release for each topic. Existing scheduled review eligibility is unchanged: a successful main edition does not automatically authorize review of its remaining unreviewed topic candidates. Expanding that eligibility requires an explicit follow-up to the editorial handoff contract; do not silently treat pending candidates as approved.

Only the Canonical Publisher renders `/topics/<id>/`, its catalog and `data/ops/source-metrics.json`. Topic pages reuse `home_card`, `analysis_html` and `make_preview`, retain source and collection dates, and support search and ten-card expansion. Failed image/analysis rendering prevents publication. Pages verification checks topic/date identity and current canonical IDs before the receipt records topic IDs/counts.

Source metrics aggregate the last 30 days of verified editions, plus the candidate edition in the atomic publish. They show discovered candidates, rejected candidates, admissions to reserve and published articles. Failed Collector attempts are **not** in this aggregate, and reserve admissions are not current reserve stock. The UI states that scope.

## Deployment prerequisite (not satisfied by merging this PR)

Project: `epumcdxfkcujulqrcjrw`. Deploy `supabase/functions/collection-admin/index.ts` and `policy.mjs` to the existing project's `collection-admin` Edge Function. `verify_jwt=false` is intentional: the handler verifies the bearer token with Supabase Auth and compares its user ID to the sole `app_owner` row on every request. Anonymous and non-owner requests receive 403.

Set `COLLECTION_GITHUB_TOKEN` as an Edge Function secret: use a dedicated fine-grained GitHub token restricted to this repository with Contents read/write permission. It does not need Actions, administration or workflow modification permission. Never reuse or upload the desktop's existing broad Git credential, commit the token, place it in browser JavaScript, or send it in chat. Creating the credential and authorizing persistent server access must be completed by the owner through the service's secure UI. Supabase supplies its own server-side URL/service-role environment variables.

Before merging, verify anonymous rejection, invalid-session rejection, non-owner rejection and an owner `version` read using the reviewed PR's exact commit SHA. On the first deployment the settings file does not exist on main yet, so an owner `load` or `save` cannot be a pre-merge prerequisite. Keep the PR in draft until server credentials and owner access are verified. After all PR checks pass, merge the reviewed change, verify an owner load from main, and test a reversible settings edit through the real backend, confirming the expected GitHub file SHA/commit and no Collector dispatch. Restore the prior settings using the current SHA. Then run the existing controlled Publisher validation. Local fixture tests are not evidence of production backend access.

### Deployment checkpoint: 2026-11-18

The `collection-admin` function was deployed to the existing project from commit `42eeaf778b01c582d101f36e5fa451df17120031`; both editor files were compared with their tested repository sources before deployment. The function's custom Supabase Auth plus `app_owner` verification is enabled (`verify_jwt=false`). Live checks returned 403 `owner_required` for anonymous and invalid-session calls, 403 `origin_not_allowed` for a foreign origin, and 200 for the site's CORS preflight. A real authenticated non-owner test, owner read/write, the dedicated GitHub secret, PR merge and full publication verification remain pending; these basic rejection checks do not establish completion.

Official references: [Supabase deployment](https://supabase.com/docs/guides/functions/deploy), [Edge Function secrets](https://supabase.com/docs/guides/functions/secrets).

### Deployment checkpoint: 2026-11-19

The owner authorized a dedicated fine-grained credential restricted to this repository (Contents read/write and required Metadata read-only), expiring 2026-12-18. It was created and stored as `COLLECTION_GITHUB_TOKEN` in the existing project's encrypted Edge Function secrets. No credential is stored in the repository or frontend. Authenticated owner verification and production read/write remain required before this deployment is complete.

The 2026-11-19 Publisher exposed an additional validation mismatch: its intelligence contract checked heading keywords even when reviewed blocks supplied explicit `angle` fields. The Publisher now calls the same semantic validator as reader review, including fail-closed checks for invalid or missing angles and compatibility for archived blocks without explicit fields. Regression coverage passes reviewed copy through both review and publication depth checks; the actual 15 candidate articles pass both checks without changing their text.

## Verification

`python scripts/test_collection_admin.py` covers settings validity, source/topic pausing, keyword/date exclusions, calendar boundaries, RSS-only custom topics, combined main/topic/reserve persistence, source evidence review, image-card rendering and private-address rejection. `node --test supabase/functions/collection-admin/policy.test.mjs` exercises the actual handler with mocked external services: owner checks, fixed-path writes, file-SHA conflict handling and rejected dispatches.

The existing source contract CI runs those checks along with the existing publication and historical regression suite. Local browser tests use an isolated in-memory backend fixture; no fixture topic or source is committed to production settings.


## Operations and account recovery

- `/admin/` opens the owner-only overview, editorial queue, reserve library, sources, topics and settings history. Public navigation links to it; visibility never grants permission.
- `operations` reads one pinned main commit. DONE requires matching dated canonical data, IDs/count, committed data, Pages pass, exact site/daily URLs and latest-success. Missing Actions evidence is UNKNOWN. Dashboard counts are observed values, not promises of publication.
- `selection` only writes `config/editorial-selection.json` using the supplied blob SHA. Holds skip candidate admission and reserve fetching. Release removes the hold; it does not approve content. All normal source, twelve-month, provenance, review and dedupe checks still apply. Eligible held rolling reserves remain stored within existing expiry/capacity limits.
- Queue/reserve search, state filters and ten-row pagination are available. Before a monitor snapshot exists, the queue falls back to today's decision ledger and explicitly labels missing title/date detail. Rolling reserve counts exclude published, held and date-ineligible entries; every remaining entry still needs a fresh source check.
- The existing Collector writes bounded metadata to `data/ops/collection-monitor.json`, including on failure when an evidence packet exists. This same concurrency-controlled job stages only that path, guards current main, and never overwrites concurrent changes. Monitoring failure cannot turn a failed Collector into success or block a successful handoff. The snapshot contains no evidence paragraphs, HTML, preferences or credentials.
- `/reset-password/` uses Supabase Auth recovery email and a fixed HTTPS callback. Expired links show a request form; verified recovery sessions show password confirmation. Passwords are submitted directly to Supabase by the user. Existing accounts, collections and preferences are retained. No account is created by recovery.
- Supabase Site URL and exact allowed redirect URL are `https://pastfantast-glitch.github.io/ai-3d-daily/reset-password/`. No wildcard callback is needed. Deploy `index.ts`, `policy.mjs`, and `operations.mjs` together; preserve existing owner authorization and token scope.
- The currently provisioned repository token expires 2026-12-18. Update the displayed expiry when rotating the existing server credential.

Verification: owner/nonowner authorization and fixed-path/conflict tests; strict DONE and unknown-state tests; twelve-month bounds; hold retention/admission; monitor allowlist and CI trust scope; recovery parameter and password confirmation tests; full historical rebuild/regression and browser QA. Actual email delivery and changing the owner's password require the owner's participation.


## 2026-11-25: validate settings before activation

Saving and restoring now stage a version in `config/collection-pending.json`, bound to the active settings blob SHA. They do not change the Collector configuration. Concurrent pending edits are rejected by blob SHA. The UI labels the draft separately from active source/topic counts.

The existing daily contract CI validates code and active settings. A separate, read-only `collection-settings-check.yml` CI validates the proposal and samples new/enabled/changed source endpoints with the Collector's existing public HTTP, publication-date and body extractors. It reads at most five configured indexes and three article samples per changed source; it does not discover a daily edition, approve copy, write canonical/private/public data, or dispatch Collector/Publisher. A failing proposal never makes the active contract CI fail. No schedule is added.

Activation requires successful latest main runs of **both** workflows on the exact current main SHA. Pending, failed, missing, API-unknown and stale results cannot activate. The owner selects “套用已驗證設定”; the server rechecks source/pending versions and checks, then uses one fixed-path GraphQL commit with `expectedHeadOid`. A race is rejected without retry. If other work has moved main before validation/activation, reload and re-save the proposal to validate against the new main. Existing settings remain usable meanwhile. Restores use the same gate.

The new source test must find at least one untruncated readable sample with a verified publication date within twelve calendar months. A blocked/undated site can be saved paused while its endpoint is corrected. This checks read capability, not editorial approval or guaranteed daily supply. Browser preview also follows up to three sample links and shows their dates/body excerpts; CI is authoritative and uses the actual Collector extractor.

Source cards display the latest Collector monitor's discovered candidates, extracted bodies, recorded approvals, awaiting-review count and status/reason, including failed runs. That snapshot is dated and kept distinct from the 30-day **published editions only** aggregate and reserve admissions. Missing measurements display an em dash. Collector already persists this metadata; this UI does not invent counts or run collection.

Regression fixtures are independent of owner-managed live source configuration. An additional test validates current settings plus a newly added source against the actual probe plan. Deploy `index.ts`, `settings-flow.mjs`, `policy.mjs` and `operations.mjs` together before the new UI is used. Preserve owner authorization, existing credential scope, schedules and the sole canonical writer.


## 2026-11-25: source/topic node canvas

The 2026-11-26 workspace below supersedes this initial layout and interaction description.

The admin “節點畫布” view shares the same in-memory settings as the source and topic lists. Drag a source output to a topic input, click the two ports in order, or use the inspector checkboxes. The graph writes only existing `source.topic_ids` membership through the unchanged owner-only pending settings API. It cannot create executable routes, bypass review, trigger collection/publication or alter pipeline policy. Sources must retain a topic; AI/3D must retain an enabled source. The optional expanded view, search, zoom, pointer dragging and Alt+arrow node movement affect presentation only; layout resets on reload and source layout resets when filtering.

The right inspector reuses the existing source/topic form and article preview. “加入畫布草稿” edits locally; “儲存畫布並驗證” stages the same settings document used by list editing. No draft becomes active until the existing exact-main CI gate permits “套用已驗證設定”. Unstored changes suppress activation and warn before refresh/logout/navigation away. “捨棄未儲存變更” restores the last loaded version, including an existing pending version, without mutating GitHub. Existing pending owner edits are preserved. Name/endpoint/keyword editing and list editing continue to use the established policy validator and version checks.

Purple solid source-topic links are present in active settings, gold dashed links are additions, and red dashed links are pending removals. Paused nodes are dimmed; links describe membership rather than a guarantee of current collection. Fixed date/filter, evidence/dedupe, review, reserve and sole Publisher nodes expose dated operational snapshots and links to existing detailed views. Missing counts stay unknown, approvals are not published counts, and reserves require rechecking. These nodes can be repositioned but their routes cannot be edited. The regular list views remain available, and narrow layouts place the inspector beneath the canvas.

Validation: graph model tests cover immutable edits, duplicate links, removals, invalid endpoints/stages, orphan prevention, the final AI/3D source and unknown/non-DONE status. Browser QA covers actual pointer cables and node movement, keyboard movement, inline topic/source edits, staged save/activation/failure, last-link rejection, zoom, expanded view and narrow viewport. Local mutation tests use a fake owner service; production verification must preserve owner-managed active and pending settings.

Proposal CI always runs its unit tests. Pull requests that only change UI/docs do not re-probe an unrelated owner proposal; configuration, Python pipeline or settings-policy changes still probe it. Main proposal validation always runs the live check, and backend activation still requires both successful checks on the exact main SHA. A blocked owner proposal remains blocked while unrelated interface fixes can be deployed.

## 2026-11-26: unified graph workspace

The graph is the main workspace. Overview, source/topic lists, queue, reserve, history and validation open in a resizable side drawer. Article details return to the same filtered list and scroll position. Forms stay in the graph inspector; leaving an unsaved form prompts before discarding it. Account recovery remains a separate account action.

The persistent state bar distinguishes local drafts, saved proposals, validation, failures, ready-to-activate and active settings. Impact preview lists configuration changes and enabled source counts per topic, warns about topics with no enabled supply, and explains that activation affects the next Collector. Batch source pause/resume and topic membership edits only change the same undoable local draft. Removing the final topic pauses its source. Incomplete drafts are allowed; saving still enforces all existing server and AI/3D supply constraints.

Remote versions are checked on focus, manual refresh and same-origin tab notifications. A changed active or pending blob never overwrites local edits. Three-way comparison applies disjoint fields only; same-field edits and delete/edit conflicts remain blocked. History includes the Git commit account and date, links to the complete diff, and restores only to a draft. A service commit account is not represented as proof of the actual human operator.

The optional graph navigation contains node lookup, eight named camera views, position locks and twenty selection groups. The minimap moves the camera; free panning, cursor-centered wheel zoom, wiring, unlinking and undo remain available. Views, locks and groups are browser-local presentation settings, never executable pipeline configuration. Locked positions cannot be dragged, keyboard-moved or rearranged.

Source health derives the last observed readable body, a bounded consecutive failure count and extraction/approval rates from actual monitor observations. Missing evidence remains unknown; observation batches can overlap and are not unique article totals. Reserve summaries distinguish total stored rows, state breakdown and the eligible next-run recheck count. The daily target is 30 and the planning reserve target is two editions (60); neither changes the release minimum or asserts that a stored article is publishable. Batch holds use the existing selection blob SHA and fixed-path API, preserving unselected holds and all review/date/dedupe gates.

Validation covers immutable batch drafts, disjoint/conflicting merges, unknown source statistics, inventory eligibility and hold preservation, plus existing settings, editorial, handoff and strict DONE regressions. Browser verification covers the drawer/list return, filters, impact/undo, navigation, locks, conflicts and authenticated production access. The only backend change adds the history actor field; deploy the reviewed `index.ts` to the existing function without changing secrets or permissions.
