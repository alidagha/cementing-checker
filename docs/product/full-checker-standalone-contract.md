# Cementing Checker — Full Product & Standalone Delivery Contract (Owner-approved target)

**Decision date:** 2026-11-03. **Status:** Target specification and execution plan, **not** evidence that the current implementation is complete.  
**Repository:** `alidagha/cementing-checker`. **Owner objective:** fully check and correct a completed cementing-program DOCX produced in the Cementing App master-template format **without relying on the Cementing App repository or a running Cementing App**.

## 1. Non-negotiable engineer workflow

1. The engineer uploads one complete, original master-template-format DOCX. Retain its byte-identical SHA256 original. Reject invalid, ambiguous or unsupported input without a false PASS.
2. The Checker obtains **independent operator/reference inputs** through a conditional job-aware interface; it never trusts the uploaded Word values as its own computational references. Reuse the original verified engineering algorithms, constants, units, rounding and applicability; do not invent a parallel calculator.
3. Check **every applicable in-scope numeric, structured, fluid, Lab, equipment, and narrative claim** for the selected job, across all 15 canonical job types. Identify missing, invalid, ambiguous, excluded, not-applicable and not-yet-verifiable claims separately. No silent omitted check may count as verified.
4. Return a traceable finding for every applicable claim: stable ID, job/section, fluid or stage, exact Word locator and raw value, independent reference and provenance, unit, comparison/tolerance, status, explanation and correction eligibility.
5. Allow the engineer to select safe proposed edits individually and approve them explicitly. A correction engine must **recompute actual dependencies**, safely locate each selected Word element, write only a new private DOCX, reparse/recheck, and leave all unselected findings (including discrepancies) visible. If an edit, formula, dependency, narrative or Word locator cannot be proven safe, mark **MANUAL_CORRECTION_REQUIRED** and explain it; never silently "fix" it.
6. Produce a complete English-language audit report: before findings, selected actions, skipped/manual actions, exact change ledger, after recheck, remaining discrepancies, evidence of original preservation and source/review metadata. Provide downloadable **corrected DOCX and audit report**. No PDF is required by this contract.
7. Secure downloads by session and current run/selection/consent; HTTP delivery authorization and all native revocations must pass real cross-session browser tests. Local success is not hosted certification or deployment.
8. The Checker is independently installable/runnable. Required App computations, template and non-optional data must be **packaged within the Checker distribution**; at runtime there is no fetch/import from `alidagha/cementing-test`, dependency on its GitHub availability, or requirement to launch the Cementing App. External Python libraries may be packaged into the offline distribution during release work.

**Product acceptance:** 15/15 authenticated job Goldens, all 22 cross-case families with supported applicability and real negative controls, complete in-scope claim coverage and corrected-document recheck, secure delivery, exact-head hosted regression, native Word and isolated offline-install verification. **No release claim until evidence exists.**

## 2. Source / scope authority and truthfulness

- Live Checker `main` at planning: `c2a7f6a762120e03f63cab7766ecdceb9accd021`. Security delivery PR #22 is separate and **unmerged**; it must achieve green A/B/C + aggregate `regression` and independent exact-head acceptance.
- Existing Checker App source pin: `60dffefb8c941ad90cb7caba0992126a35803717`; 143 locked source/template file identities, 11 accepted ancestors, 51 package pins. The App `main` was `cd11661fbde7f13865a7eaf12c8c0376127e7e54` when this plan was established. Neither SHA is a floating import. Refresh both before each execution batch.
- Historical `PARTIAL_FINDINGS_ONLY` remains true for today's code. It **is not** the final product target. Preserve provenance, original DOCX, negative controls and accepted comparison behavior until a precisely scoped change is verified.
- Historical exclusions (Cover/Document Control, Survey, Centralizer, Pore/Frac, IOD, figures/charts/schematics) are explicit separate owner decisions, **not checks completed**. Inventory them visibly. Expanding the checking scope requires real source mappings and test evidence; do not manufacture PASS counts or silently revoke an exclusion.
- Original measured Lab observations and independent approvals must be genuine; never generate or auto-confirm them from formula results. Synthetic source-rendered fixtures are useful component tests but never substitute for genuine production Goldens.

## 3. Standalone engine migration (highest architectural priority)

**S1 — inventory / freeze:** Compare the current App tree to the pinned 143-file source/template manifest. Identify all import-time and runtime transitive dependencies of C02/C03/C05/C06/C07/C08/C09/C10, the original Word render/export pipeline, any protected resource, and UI/Streamlit coupling. Document the exact frozen source commit, file hashes, data files and supported environments; classify divergence from live App `main` as a separate compatibility decision.

**S2 — package:** Add the required *verified source engine and template files* inside a versioned Checker-owned runtime package or build input (for example `checker_engine/vendor/`, final location decided after import graph inspection). Preserve original source bytes where appropriate. Adapt the thin source bridge and private runtime provisioner to the local verified bundle. Fail closed on missing/tampered files; do not create alternate formulas or silently substitute a newer App revision. Original pinned hashes remain regression oracles.

**S3 — remove remote dependency:** Replace `tools/provision.py`'s mandatory upstream network retrieval with local bundle verification/copy. Validate from a **fresh Git-free installation with network disabled**, including source/template load, automatic engine references, protected identities, test seeding, real DOCX analysis and safe-copy recheck. No App checkout/path/repo/SSH/remote URL at runtime. A clean build may still acquire package wheels during build, but the delivered offline distribution must run without network.

**S4 — source/engine parity:** Compare the newly packaged engine to the exact original pinned engine on canonical fixtures and metastable edge cases. Identify new App changes deliberately; do not auto-repin or mix versions. CI must certify the bundled source itself and the final release artifact without asking GitHub for App code.

## 4. Full comparison and correction coverage

**Canonical jobs (all mandatory):** J01 CSG 30", J02 CSG 24", J03 CSG 20", J04 CSG 18 5/8", J05 CSG 13 3/8", J06 CSG 9 5/8", J07 CSG 7", J08 LNR 7", J09 LNR 5", J10 LNR 4 1/2", J11 CMT PLUG, J12 CMT PLUG WITH CT, J13 CMT SQUEEZE, J14 TIE BACK LNR 7", J15 TIE BACK LNR 5".

**Cross-case acceptance families (all mandatory):** X01 1/2/3 placed slurries; X02 distinct tanks; X03 inverse DV; X04 DV correction cascade; X05 Spacer mixed stock; X06 remaining Spacer modes; X07 conditional fluids; X08 Scavenger; X09 client volume/excess; X10 rate/time; X11 Lab grams tolerances; X12 rheology datasets; X13 other measured Lab branches; X14 narrative semantics/order; X15 missing/malformed input; X16 safe-copy edits; X17 complete input-to-dependent-field correction cascade; X18 CT stages; X19 audit report + editable message + download; X20 explicitly excluded scope with zero PASS contribution; X21 template changes; X22 failure isolation.

Build a **claim-coverage ledger** for each Jxx + Xxx: applicability; required independent inputs; source function/template anchor; Checker adapter; extraction/association evidence; positive and negative fixtures; UI path; correction class and exact dependency cascade; report; authentic Golden state. A mapped module/test alone cannot close a case. Distinguish FULLY_VERIFIED, PARTIAL, NOT_RUN, BLOCKED and EXCLUDED. No conditional applicable claim may disappear silently.

Specific known engineering gaps to close include operational Spacer/Pre Flush/Diesel/Scavenger contexts, CT stages, special-job Procedure/NOTES, comprehensive Lab branches, safe Word locations and all source-dependent water/DV/additive/narrative cascades. Use source-produced values only. Do not promise automatic edits for fundamentally unproven/unsafe cells: controlled manual correction + explicit subsequent recheck is acceptable; unexplained omission is not.

## 5. Execution order and completion gates

| Wave | Delivery | Completion evidence |
|---|---|---|
| R0 — Stabilize | Close A7 secure download **as a separate PR**, complete hosted A/B/C + aggregate certificate, no unapproved merge | Exact-head hosted green, real-browser cross-session/revocation proof, verified post-merge main |
| R1 — Decouple | Bundle all required App engine/template/data locally and remove mandatory App fetch from runtime | Clean isolated offline network-denied launch, engine parity, entire preserved test union, source hashes |
| R2 — Coverage | Finish missing C01R–C09 maps/independent inputs/UI for all 15 jobs and X01–X22 | Every applicable claim accounted for; source-backed positive/negative and real DOCX tests |
| R3 — Corrections | Extend C10 beyond Yield/Sacks using proved safe edits and full dependent cascades; add manual correction/re-upload/recheck path | Original hash unchanged; selected edits rechecked; unselected gaps remain; fail-closed malformed DOCX |
| R4 — Audit | Full before/after change ledger and downloadable report; controlled original and corrected DOCX deliveries | End-to-end browser UAT, independent findings traceability, no cross-session data leak |
| R5 — Authentic UAT | Obtain all 15 real App-template production DOCXs with genuinely observed/reviewed Lab facts and run X01–X22 mutations | J01–J15 A–H plus X01–X22 evidence, native Word, exact input/source/output hashes |
| R6 — Release | Installable self-contained Checker, environment/packaging/security checks, current CI and release manifest | No runtime App dependency/network, verified install/rollback, signed-off scope and tested release artifact |

**Cadence:** Small source-bound batches, one real gap and its shared callers per batch; final-byte regression and exact SHA before publication. No fixes without demonstrated gap. No unnecessary loop of security/performance diagnostics. A7 and the new architecture work are not mixed in one PR. Later waves may run in parallel *only when their dependency gates are satisfied*. Never change the protected main/rulesets/workflow without an exact Owner-approved change scope.

## 6. Immediate technical backlog and decisions

1. Finish evidence and disposition of PR #22 independently. Its current red hosted CI blocks merge; do not substitute local PASS. Existing `main` C10 media download retains a documented privacy defect until the secure route is merged and verified.
2. **Next code Batch:** R1-S1 inventory + minimal import/dependency tests and an explicit vendoring manifest; then R1-S2/S3 local-bundle source migration with negative network-denial tests. This is the first necessary production change for true independence.
3. Build a machine-readable, dated J01–J15 and X01–X22 evidence ledger; reconcile stale historical matrix entries (for example X16/X19 show `NOT_RUN` even though later C10/G07 component functions were added). Update evidence only when tests prove each new status.
4. Implement and prove full correction taxonomy: AUTO_SAFE; MANUAL_CORRECTION_REQUIRED; NOT_APPLICABLE; NOT_VERIFIABLE; REJECTED. Each selected action has before/after bytes and source dependency proof, never broad string replacement.
5. Do not declare full release or rename `PARTIAL_FINDINGS_ONLY` until every mandatory release gate has real, independently checked evidence.

## 7. Boundary of this planning change

This file is an approved **target and backlog**, not a modification to any engine, accepted lock, workflow, private evidence, or user data. It grants no synthetic Lab sign-off and no authority to merge a red PR. Existing scoped behavioral contracts and fail-closed tests remain binding until deliberately replaced by individually verified implementations. 
