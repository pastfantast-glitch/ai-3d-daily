# Collector pre-handoff CI

Use a full clone of current `main`, with the locked dependencies from
`requirements-pipeline.txt` installed. Run:

```sh
python scripts/check_main_ci.py
```

The gate reads GitHub Actions directly. A successful PR run is not evidence of a
successful `main` push. Do not use the connector's `fetch_commit_workflow_runs`
helper for this gate: it filters to PR runs.

`Daily source contract QA` has a push path filter. Resolve its required SHA from
the latest commit touching those configured paths. `Historical regression matrix`
runs on every main push, so require the current main SHA. For both workflows,
require the newest matching main/push run to be completed/success. Never fall back
to an earlier success after a later failure or pending run. API errors, missing
runs, shallow history, dirty source inputs and moving main all fail closed.

The script is read-only. It uses `GITHUB_TOKEN` or `GH_TOKEN` if supplied, otherwise
the public API. It prints the main SHA and supporting run IDs/URLs on success.
Network access to GitHub and a trusted TLS certificate store are required; never
disable TLS verification. On Windows, Git may need `-c http.sslBackend=schannel`
when obtaining the clone.

The finalizer automatically runs this gate before any Collector mutation when
`--write-request` is requested. Validation-only mode remains offline-capable.
The separate external queued/in-progress writer check and
`--writer-idle-confirmed` requirement remain in force. CI success does not replace
real collection evidence or authorize fabricated canonical/session data.

After genuine discovery and collection, validate and hand off using:

```sh
python scripts/finalize_collection_handoff.py YYYY-MM-DD
# Only after checking that the canonical writer is idle:
python scripts/finalize_collection_handoff.py YYYY-MM-DD --write-request --writer-idle-confirmed
```

Only the canonical writer creates `.ready`, publishes, verifies Pages and writes
DONE. This change does not itself collect or publish the missing September 17
report. Existing ChatGPT Collector task prompts are external to this repository;
they should invoke this gate rather than stop on an empty PR-only helper result.

Regression tests: `python scripts/test_main_ci.py`.
