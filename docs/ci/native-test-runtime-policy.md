# Cementing Checker — Permanent Hosted Native Test Runtime Policy

**Approved by the Project Owner:** 2026-11-03. Applies to all subsequent Cementing Checker pull-request native A/B/C regression runs, including R0 security and R1 standalone-engine work.

## Standard time budget

- **Native pytest watchdog:** 3600 seconds (60 minutes), per shard A/B/C. Runs stop immediately if the tests finish earlier.
- **Native shard GitHub Actions step timeout:** 65 minutes, allowing the 60-minute watchdog and its termination/cleanup.
- **Focused matrix job timeout:** 75 minutes, allowing provisioning, seeding, collection, native execution, sealing, and artifact upload.
- Existing provisioning, seeding, and discovery phase limits remain unchanged unless separately justified and approved.

## Integrity conditions

This policy changes **only time capacity**, not test content or certification standards. Keep all existing whole-module tests and shard membership, complete setup/call/teardown reports, strict original-source and accepted identities, schedule hashes, sealed current-run artifacts and mandatory aggregate `regression` gate. Skips, xfails, warnings, gaps, timeouts, missing evidence, partial results and source drift remain FAIL / UNVERIFIED. An elapsed timeout alone does not prove test correctness or an infrastructure issue.

Every new change to CI workflow settings still requires appropriate authorization and exact-head Hosted CI certification before merge. Never rerun a failed SHA to manufacture green. Do not merge an unverified PR, bypass branch protection or treat the fast-only main push as full regression.

## Operational note

Changing limits to 60/65/75 minutes does not make an individual passing test longer, nor does it prove the full engineering program, true Golden UAT, secure external deployment, or complete independent offline distribution. If tests genuinely hang beyond the 60-minute watchdog, stop and investigate that evidence. The policy applies to the Checker repository only.
