# Source and topic administration, first version

The AI/3D homepage keeps its existing publication contract. `/admin/` manages public collection settings; `/topics/` links to separate topic pages. Authentication reuses the existing Supabase owner account. This feature does not introduce a second Collector, Publisher, schedule, model API or browser-held GitHub credential.

## Operations

- Add/edit/pause/resume a source and bind it to one or more topics. Configure up to five HTTPS article indexes or RSS/Atom feeds on that domain or its subdomains.
- Add a topic with a stable URL identifier, inclusion/exclusion keywords, a 1–12 calendar month source window and a per-edition target of 1–30. New sources/topics default to paused. AI/3D remains enabled and keeps its existing target and release floor.
- Preview connectivity, source date, extracted body length and a short excerpt. Preview is not editorial approval or formal discovery.
- Review the last ten settings commits and restore a previous version. Restore creates a new commit using the current file SHA. Concurrent edits fail with a reload instruction; the service never retries a conflicting write.
- Pausing does not delete any published article. Changes affect the next existing Collector run and do not launch a run from the browser.

`config/collection-admin.json` is public and contains no credentials, preferences or source bodies. The service can write only this file. Its source and topic policy is also enforced in Python before collection. The legacy hybrid policy still controls bounded crawling, ranking, dedupe and release minimums. The selected configuration is copied into the canonical edition as an immutable validation snapshot, so subsequent source edits cannot invalidate an in-flight handoff or an old archive.

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
