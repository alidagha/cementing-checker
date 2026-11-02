---
name: streamlit-browser-testing
description: Reproduce and verify real Streamlit UI behavior of the Cementing Checker (editors, commit/blur/Enter sync, row add/edit/delete, typed payload delivery, stale-report invalidation, session isolation) with headless Playwright using the existing Chromium installation. Use only when the observed behavior depends on actual browser interaction; do not use for pure parsing, extraction, comparison, correction or report logic.
---

# Streamlit Browser Testing — Cementing Checker

This skill supplements the Checker's governance. It never replaces it and grants no authority.

Before doing anything, read and follow, in this order of precedence (more restrictive prevails; unresolved conflict is a STOP):

1. `AGENTS.md` and `zero_regression_contract.md`
2. the active owner-approved Batch prompt (STOP and permission map)
3. `docs/codex_operative_card_v5_4_rev1.md` (derived summary, no independent authority)

If a governing file is missing, report that before any production change.

## When to use

Use a real browser only when the disputed behavior depends on browser interaction:

- Checker editor behavior: Additive, Hardware, Base Cement selection and similar editors
- row add / edit / delete, row identity
- commit, blur and Enter synchronization; numeric typing
- typed payload delivery (`draft -> inputs -> receipt/source`) as seen from the UI
- stale-report invalidation after an edit
- session isolation between browser sessions
- enabled/disabled controls, visible warnings, errors or recovery controls
- browser-visible runtime errors

Do not use it merely because the repository contains Streamlit code.

## When NOT to use

- DOCX claim extraction, source binding, comparison records, discrepancy reports
- safe-copy correction (C10) logic, golden admission logic
- pure parsing, calculation, or validation helpers
- anything already fully shown by a direct test with no browser/state boundary
- static review, dependency or workflow work

## Environment

Use the existing environment.

- Chromium: `/usr/bin/chromium`, headless.
- Python Playwright is available; the Playwright-downloaded browser may be absent.

```python
browser = p.chromium.launch(headless=True, executable_path="/usr/bin/chromium")
```

Do not run `playwright install`, download or install a browser, add Selenium/Puppeteer/drivers, add a dependency, or touch `requirements.txt` for this purpose.

If local socket/process permissions block access, use the environment's normal permission mechanism. Never change repository code or application security to get around it.

## Runtime isolation (mandatory)

- Run the app from the private runtime provisioned outside this repository and every Git worktree (see `README.md`: `tools/provision.py`, then `--seed`).
- Keep caches, temp files, logs, screenshots, generated fixtures and the upstream snapshot in that private runtime. Never commit them.
- Never commit the upstream App, Word template, libraries, original fixtures, DOCX files or recovery archives.
- Original DOCX and operator input bytes must be unchanged after the session; verify hashes before and after.

## Launching the app

Prefer an already-running instance. Otherwise determine the established launch command from the current `README.md` and live `main` first; the expected UI module is `checker_ui.py`. Do not guess ports or flags, and do not assume `main.py`. If the launch command cannot be established from the repository, report `NOT_VERIFIABLE` and stop at that boundary.

Run headless, with usage statistics disabled, on an unused local port. Stop any process you started when finished.

## Core rule: reproduce the user's path

Reproduce through the same interaction boundary that matters: fill the visible input, select the visible option, edit the visible table, commit with the real Enter/blur, trigger the real rerun, upload through the real uploader.

Do not mutate `st.session_state` directly to prove a browser bug. Seed a prerequisite only when the setup would otherwise be impractically long, and report exactly what was seeded versus tested.

Verify options from the pinned source catalog, never from guessed indices, and never relax source eligibility to make a control reachable.

## Workflow

1. **Baseline:** confirm the intended revision and clean working tree, the entry point and URL, the exact scenario, expected versus observed behavior. Do not modify production code yet.
2. **Locators:** prefer role + visible name, then label, then narrowly scoped visible text, then stable existing attributes. Avoid generated CSS classes, deep ancestry, element order alone and XPath chains. Scope duplicates to the relevant container or editor.
3. **Reruns:** after any action that can rerun, reacquire locators and wait for a deterministic observable condition (`expect(...)`), not `time.sleep()`.
4. **Commit and readback:** record the commit acknowledgment (Enter/blur, rerun) before reading the value back. A visible cell, a keyboard event or a saved draft does not prove source admission.
5. **Backend correlation:** correlate the UI action with the backend typed snapshot and the admission/rejection result. Source processing happens only for complete, valid inputs.
6. **Evidence:** visible values, enabled/disabled state, warnings/errors, table cells, console errors, page exceptions; screenshots only when they materially help.
7. **Console/runtime errors** are evidence, not automatically the root cause. Trace the real flow before choosing a fix.

## Retries (Card §1)

Up to three substantial, evidence-driven correction attempts per unresolved failure cluster; this is not a three-browser-call or three-selector limit. Each retry must be different and hypothesis-driven, use supported accessibility locators with explicit commit/readback correlation, and never repeat an identical failed interaction without a new hypothesis. All attempts count against the single non-resetting 20-minute local budget. After the third failed substantive attempt, run one cheap dependency check and STOP.

## Checker editor acceptance

For an editor cluster, evidence must cover, as applicable:

- real row add / edit / delete
- independent Additive dosage and density values
- Hardware Description / MD and other required fields
- commit acknowledgment before readback
- correct backend snapshot and admission/rejection
- source processing only for complete valid inputs
- stale-report invalidation
- source and Word bytes unchanged
- session isolation

Unreached controls are `NOT_VERIFIABLE`. Never click blindly or fabricate a browser action or receipt. Results remain partial findings; no overall engineering PASS.

## Fix only when authorized

- Audit/reproduction-only task: modify nothing; report evidence and stop.
- Authorized fix: smallest root-cause change, reuse existing patterns, no parallel validation or comparison system, no weakened validation or tests, no new field, button, table, caption or surrogate workflow, no silent expansion to other modules.
- A harness/selector/environment cause proven: fix only the authorized local harness and leave production bytes untouched; finish as `HARNESS ONLY / PRODUCT UNCHANGED`.

## Verification

After an authorized fix, repeat the same browser path, confirm the failure is gone, the value/state survives the same rerun boundary, and check relevant sibling modules if shared code changed.

Browser testing never replaces the repository's regression gates: native collection, the three whole-module A/B/C shards and the `regression` aggregate (`tools/ci.py`, run per `README.md`). Hosted CI follows the active Batch prompt's pipeline mode. If the browser path passes but a required gate fails, or the reverse, the task is not accepted.

`AppTest` is not a real browser, DOM observation is not authenticated backend admission, and local browser execution is not hosted verification.

## Reporting

Use exact vocabulary: `FRESH PASS`, `PREVIOUSLY PASSED — evidence`, `FAIL`, `NOT RUN`, `NOT_VERIFIABLE`. Never fabricate a SHA, time, cost or result.

```text
Browser scenario:
Repository revision:
Local app URL / launch command:
Chromium:
Reproduction:
Observed before:
Root cause:
Files changed:
Observed after:
Browser/console result:
Regression commands:
Regression results:
Input/source/DOCX hashes before and after:
Evidence:
Working tree:
Cumulative wall time (vs 20 min):
```

If no production edit was authorized, report `Files changed: None`.
