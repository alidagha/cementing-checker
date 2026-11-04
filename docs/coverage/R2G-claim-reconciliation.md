# R2-G claim reconciliation — bounded inventory

Baseline: `9d074eb5fbc3a9d38a27fe39111464ad3867afee` (merged R2-F). This increment changes inventory metadata and its test validator only. Production adapters, UI, receipt and secure-delivery bytes are unchanged.

## Impact and authority

Reads: C08/C09 whole-paragraph and ordered NOTE evidence, G07 grouped findings and current source/receipt routes, R2-A–F notes, canonical job/cross-case manifests. Writes: this note, six current-reconciliation labels in the existing ledger, and stronger checks in the registered ledger test module. No engineering, schema, source, template, UI, correction or transport mutation.

Pinned source: `60dffefb8c941ad90cb7caba0992126a35803717`; 143 resources; accepted identities 11; dependencies 51. Template SHA256: `a1128b0e9352e1dd7c8768eecc9335c50858356cee80ed33c0ec275e26c4d08b`.

## Inventory accounting

406 candidate patterns remain unchanged: 119 manually traced entries, 244 template slots and 43 static candidates. The 119 include 109 semantic patterns plus dependency/exclusion entries. All original IDs, source references, historical baseline facts, maturity and credit are retained. Component-mapped patterns remain 89; verified claim instances, proved production physical instances and authentic Golden jobs remain zero. Actual rendered-claim inventory completeness remains UNVERIFIED.

Each job retains all 406 candidate patterns for inventory visibility. This does not assert every pattern applies to every job. The 330 applicability cells remain 270 UNKNOWN_WITH_REASON/BLOCKED, 45 APPLICABLE/PARTIAL and 15 EXCLUDED/NOT_RUN. None is authentic acceptance.

| Job | Canonical source job | Authentic A–H / Golden |
|---|---|---|
| J01 | CSG 30" | NOT_RUN |
| J02 | CSG 24" | NOT_RUN |
| J03 | CSG 20" | NOT_RUN |
| J04 | CSG 18 5/8" | NOT_RUN |
| J05 | CSG 13 3/8" | NOT_RUN |
| J06 | CSG 9 5/8" | NOT_RUN |
| J07 | CSG 7" | NOT_RUN |
| J08 | LNR 7" | NOT_RUN |
| J09 | LNR 5" | NOT_RUN |
| J10 | LNR 4 1/2" | NOT_RUN |
| J11 | CMT PLUG | NOT_RUN |
| J12 | CMT PLUG WITH CT | NOT_RUN |
| J13 | CMT SQUEEZE | NOT_RUN |
| J14 | TIE BACK LNR 7" | NOT_RUN |
| J15 | TIE BACK LNR 5" | NOT_RUN |

| Case | Concern | Current component maturity | Authentic acceptance |
|---|---|---|---|
| X01 | 1/2/3 placed slurries | PARTIAL | NOT_RUN |
| X02 | Distinct tanks per slurry | PARTIAL | NOT_RUN |
| X03 | Dead Volume inverse | PARTIAL | NOT_RUN |
| X04 | Dead Volume correction | PARTIAL | NOT_RUN |
| X05 | Spacer mixed stock | PARTIAL | NOT_RUN |
| X06 | Spacer other modes | PARTIAL | NOT_RUN |
| X07 | Conditional fluid families | PARTIAL | NOT_RUN |
| X08 | Scavenger | PARTIAL | NOT_RUN |
| X09 | Client volume/excess | PARTIAL | NOT_RUN |
| X10 | Rates/times | PARTIAL | NOT_RUN |
| X11 | Lab grams tolerances | PARTIAL | NOT_RUN |
| X12 | Rheology datasets | PARTIAL | NOT_RUN |
| X13 | Other lab branches | PARTIAL | NOT_RUN |
| X14 | Narrative completeness | PARTIAL | NOT_RUN |
| X15 | Malformed/missing numeric | PARTIAL | NOT_RUN |
| X16 | DOCX safe edit | PARTIAL | NOT_RUN |
| X17 | Input correction cascade | PARTIAL | NOT_RUN |
| X18 | CT stage edges | PARTIAL | NOT_RUN |
| X19 | Report and copy | PARTIAL | NOT_RUN |
| X20 | Exclusions | PARTIAL | NOT_RUN |
| X21 | Template minor revision | PARTIAL | NOT_RUN |
| X22 | Fault isolation | PARTIAL | NOT_RUN |

Candidate patterns by section (not rendered or verified instances):

- cement: 50
- excluded: 25
- fluids: 21
- geothermal: 10
- hardware: 22
- lab: 222
- preflush: 41
- procedure: 9
- summary: 6

## Narrative granularity and report boundaries

`c08_summary.compare_document` uses the original independent source summary and one uniquely associated literal physical paragraph. `equivalent` preserves meaningful line breaks, case, units and punctuation; `literal_paragraph` rejects numbering/field/hidden-text ambiguity. A whole generated string provides no independent source-expression-to-character-span map. No subparagraph atomization is implemented or credited. Repeated, split, merged or ambiguous text remains unverified.

`c09_procedure.sequence_findings` retains every individual physical paragraph, ordering and NOTE association; aggregate MATCH requires every required individual finding to be MATCH. Source placeholders or unproved role/stage associations prevent sequence completion. `stage_availability` distinguishes original source stage authority from current adapter admission. CT does not borrow casing geometry or ordinary C09 prerequisites. No new CT or special-fluid source path is admitted.

`g07_report.findings_table` retains original judgments, groups overlapping physical locators and exposes status/reason/raw and expected values. Full source-function, full-precision and dependency data may remain in the underlying judgments/adapter receipt rather than dedicated visible columns. This is a documented reporting boundary, not newly implemented UI coverage. No visible workflow changes or global program PASS are introduced.

## Historical/current reconciliation

Only X04/X14/X16/X17/X18/X19 current-reconciliation text changes. Historical remaining-gap statements stay intact. G06 previews remain non-mutating; current C10 copies only individually selected ordinary Yield/Sacks with recheck. R0 session-bound POST delivery and revocation are component evidence. They do not establish full correction cascades, full audit delivery or authentic job acceptance. PR #23 planning snapshots are not live R0/R1 blockers or release certificates.

## Independent negative controls

Baseline validator RED: five adversarial mutations were accepted (each test failed with DID NOT RAISE): another cross-case claim family, omitted family, COMPONENT_VERIFIED on unknown applicability, COMPONENT_VERIFIED on excluded applicability, and X20 reclassified as applicable. The strengthened validator requires the original family link and explicit blocked/excluded maturity. This repairs inventory validation only; it is not a claimed engineering-product RED→GREEN. A sixth baseline RED showed that an unchanged source file hash could still carry a crossed source field (Yield mapped to Sacks). Source/checker field and origin identities are now required to agree. Additional negatives reject obsolete source hashes, shifted producer lines and crossed job cells. Existing assertions remain unchanged.

## Evidence and remaining gates

The separately authorized local-gate recovery ran on the identical ledger/test and unchanged product bytes in the preserved Git-free runtime. Local Python is 3.12.14 with all 51 locked dependencies (including Streamlit 1.64.0); the unchanged Hosted workflow specifies Python 3.12.15. No environment equivalence to Hosted execution is claimed.

| Final-byte local gate | Roots | Setup/call/teardown phases | Process elapsed | Result |
|---|---:|---:|---:|---|
| Complete `tests/test_c08.py` | 32 | 96 | 255.23 s | FRESH PASS, exit 0 |
| Complete `tests/test_c09.py` | 57 | 171 | 419.91 s | FRESH PASS, exit 0 |
| Complete `tests/test_r2a_coverage.py` + all `tests/test_migration.py` guards | 27 + 13 | 120 | 41.45 s | FRESH PASS, exit 0 |
| Prior security/source sibling selection, freshly repeated | 25 | 75 | 306.77 s | FRESH PASS, exit 0 |

These are 154 distinct executed roots and 462 passing phases, with no errors, failures, warnings, skips or xfails. Each module/process has its own private completion/audit record. Commands use the preserved pinned Python from the private runtime, standard `python -B -m pytest -p no:cacheprovider`, `-vv` (or `-q` for ledger/guards), and a private `--audit-file`.

The 25-root selection is the complete `tests/test_g08a7_delivery.py` and `tests/test_g08a6_c10_ui.py`, plus `c02/test_c02.py::test_independently_pinned_neat_reference_and_source_calls`, `tests/test_c05.py::test_source_child_network_and_write_guards`, `tests/test_c06.py::test_source_matrix_has_all_fifteen_jobs_without_golden_claim`, `tests/test_c07.py::test_non_measurements_cannot_become_zero` and `tests/test_g08a4_preview.py::test_volume_preview_without_current_run_is_not_available`. It covers request-time refusal, stale authority, selective copy/source recheck, input non-measurements, source isolation and unavailable preview boundaries. The old 65-root/195-phase bundle remains PREVIOUSLY PASSED evidence; recovery repeats all 65 roots freshly, rather than relabeling the old run.

The unchanged schedule digest is `a3e1689ff764c4ae46798fe0b590f335c5c8e7b79b5ca8b3db73531114d10ba9`. Native collection has 772 roots (A264/B247/C261), retaining all 763 baseline roots; nine added parameterized controls stay in the existing whole-module B owner. Collection is not full-suite execution or Hosted certification.

R2-F Chromium is PREVIOUSLY PASSED only: product, source, environment, browser-result and original synthetic DOCX identities were re-attested. The preserved fixture SHA256 is `70a6e79dbc6cdac9017701b4208d0f45502cbac89b63763059d73c89f7d3f5c2`. Historical authorized HTTP 200, foreign-context 403 and stale-authority 403 remain prior browser evidence; no fresh Chromium, native Microsoft Word or production-Golden result is claimed. Final source/template/accepted/dependency and publication-privacy attestations remain separate from later exact-head Hosted certification.

Atomization remains blocked on a source-owned expression-to-unique-physical-span mapping. Broad special-job NOTE admission, full audit presentation, native Word parity and genuine production exports remain unproved. Metadata cross-cases are not executed engineering/Word acceptance. R3/R4/R5/R6 are not started.

Seven exclusions retain zero credit: cover/document control; Survey; Centralizer; pore/fracture pressure; IOD; figures/schematics; attachments/TOC. Hardware remains in scope. Independent requested volume, pure Mix Water, Solution, preparation water, explicit DV and measured Lab retain separate authorities.

All J01–J15 and X01–X22 authentic Golden acceptance remains NOT_RUN. R2-G inventory reconciliation is not R2 completion, Golden certification or release.

## Clock history

First recorded R2-G action: 2026-11-04 13:33:21 UTC. An unexplained clock gap was retained as elapsed; a STOP was reported at 14:27:04, then the Owner instructed continuation. The original attempt ended at 15:02:57 after 89m36s with STOP / UNVERIFIED — NO PR. Its mandatory combined C08/C09 gate was incomplete and terminated; partial log output was never promoted to PASS. The old clock and incomplete evidence remain unchanged; the original Batch was not certified.

The Owner separately authorized one nonresetting 60-minute local-gate recovery. Its first operation was 2026-11-04 15:14:39 UTC. This is a separate allowance, not a reset or exclusion of the original interval. Recovery process records retain exact start/end times; total continuation time through publication or STOP is reported in the final handoff. Two cheap preflight script assumptions were corrected privately: the provisioner deliberately excludes the archive from its runtime, so the local locked archive is checked separately; dependency metadata must be queried with the pinned interpreter rather than ambient shell Python. Neither required a product/test change or a repeated failing module campaign.

HOSTED CI PENDING — NOT YET VERIFIED. Codex publishes only after final local identity/privacy/routing checks, then stops immediately. Full exact-head Hosted A/B/C + aggregate regression, independent Architect acceptance and separate Owner merge approval remain required. `whole_program_certification=false`.
