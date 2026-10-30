# CI01 — PR full regression / main fast gate

Owner scope: [Issue #9](https://github.com/alidagha/cementing-checker/issues/9).
Baseline: protected main `1f4ed5222cd1e771eb2f03db14b680a103a4e838`, tree
`35611372fa13d2c84894cdb58eeafe630c0fae53`. Official run
[41108578906](https://github.com/alidagha/cementing-checker/actions/runs/41108578906),
attempt 1, was independently artifact-verified: 427 tests A177/B159/C91,
1281 complete phases. This prior result does not certify this CI change.

| Event | Fast gate | Native A/B/C | Required `regression` |
|---|---|---|---|
| Feature push | No workflow | No workflow | No workflow |
| PR targeting main | Required | All three after fast success | Dependency validation, then unchanged full artifact certification |
| Main push | Required | Intentionally skipped | Fast-only dependency validation; no certificate |
| Unsupported event/ref or invalid dependency state | Rejected | No artificial pass | Fails closed |

Every executing job checks out the exact PR head (or main push SHA), full history,
and verifies a clean exact-root checkout. `tools/ci.py checkout` checks final
schedule-byte SHA256 and accepted file identities using only the standard library.
The fast job installs no requirements, provisions no source, collects no tests and
generates no full-regression artifact. Main runs only fast-gate and regression.

`tools/ci.py gate` accepts only PR-to-main `refs/pull/<positive-id>/merge` events
or push-to-`refs/heads/main` with empty base ref. PR dependencies must contain
exactly fast-gate=success and focused=success; main requires fast-gate=success and
focused=skipped. Unknown/missing/failed/cancelled or otherwise unexpected states
fail. The matrix result admits PR certification; it never replaces verification
of all A/B/C sealed artifacts. The gate always reports
`full_regression_certified=false`. Only the existing PR certification path can
produce a full native certificate. `regression` retains `always()` and both needs.

## Impact and two-stage preflight

First pass traced event → checkout → locks → native matrix → aggregate evidence.
Second pass rechecked unknown-event/ref, failed-fast/skipped-PR-matrix, artifact
allowlist/checksum/run/attempt/head/phase, isolation, native routing and costs.
This executor review is not independent architect acceptance.

| Surface | Approved change / protected consumers |
|---|---|
| `.github/workflows/checker-regression.yml:2–6,13–114` | Triggers, fast admission, PR-only matrix, always aggregate and PR-only artifacts. Existing shard commands and identities retained. |
| `tools/ci.py:48–64,193–208` | Stdlib event/dependency discriminator and checkout admission. Existing checkout proof, source/environment, collection/run/seal/certify semantics retained. |
| `conftest.py` / `tools/ci.py` discovery and certification | Read only; native root/phase identity and error/skip/xfail/warning enforcement unchanged. |
| `tests/test_migration.py` | Append three CI01 controls; all ten pre-existing tests/assertions retained. Already owned exclusively by A. |
| Engineering, accepted/source locks, template, all other tests, schedule/digest, recovery and App | Read only; no branch-protection, dependency, token or environment change. |

## Local evidence and routing

Commands run from a separate private Git-free runtime with Python `-B`, bytecode
disabled, scratch TMP/cache and pytest `-p no:cacheprovider`:

```sh
python -B -m pytest -p no:cacheprovider tests/test_migration.py -q -x -k ci01_workflow_event_and_dependency_structure
python -B -m pytest -p no:cacheprovider tests/test_migration.py -q
python -B tools/ci.py collect
```

Genuine RED: the static event-policy control failed on the unchanged baseline's
feature-push triggers (0.05s pytest). GREEN: 13 migration tests passed in 2.54s.
After explicitly adding accepted-lock corruption to the negative controls, the
final module passed all 13 in 2.89s, with 39 complete phases and no warnings/skips/
xfails. Total timed local RED/GREEN/collection subprocess wall time: 8.35s.
Existing executor PyYAML 6.0.3 independently parsed/validated the final workflow;
it is diagnostic tooling only, not a new Checker/test dependency.

New identities (all in A): `test_ci01_workflow_event_and_dependency_structure`,
`test_ci01_event_and_dependency_gate_is_fail_closed`, and
`test_ci01_checkout_and_gate_cli_real_git_mutations`. Controls include unknown
event/ref/base; missing/failed/skipped PR dependencies; bad SHA; clean committed
accepted-source/lock and schedule mutations; missing shard evidence; actual CLI
JSON and deliberate main skip. No assertions were weakened.

Ordinary collection: 430 unique tests A180/B159/C91; all 427 baseline roots remain.
Schedule and digest unchanged. Reproducible command: `sha256sum -- tools/test-schedule.json`:

```text
88e71f41b5e58b29876bb8a7dd85dee79e1ba12064544dba34ca74bc5e883ec6  tools/test-schedule.json
```

## Hosted boundary and costs

CI01 hosted execution: NOT RUN. Codex may commit/push only
`ci/checker-pr-full-main-fast`; it must not create a PR or merge. No G06-B.
After independent review, the architect needs separate consolidated CI01 time
approval before opening the PR. Latest baseline job execution totaled about
23.7 runner-minutes; a single new full PR is estimated at 24–28 runner-minutes
and 11–13 wall minutes, with variable provisioning/queue costs. Main fast-only
execution is estimated below one minute per job, subject to runner/setup latency.
G06-A's budget does not apply. Future PR certification and post-merge main-fast
observation remain NOT RUN; merge requires Owner authority and exact merged-tree
compatibility. No engineering, whole-program or Golden certification is claimed.
