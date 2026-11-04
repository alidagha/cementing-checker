# R2-C: optional Standalone Spacer inputs and printed dosage

R2-C checks source-supported Spacer claims only. Results remain `PARTIAL_FINDINGS_ONLY`; this is not R2 completion, authentic Golden acceptance, engineering approval, correction authority, or a release. Hosted CI is **PENDING — NOT YET VERIFIED**. The Owner's publish-PR-and-stop exception requires stopping immediately after PR/remote-head confirmation.

## Authority and impact

The starting Checker main is `41c1c8a6395e978d453be4972f0d69a47a35b417`. The engine remains pinned to `60dffefb8c941ad90cb7caba0992126a35803717`: 143 source/template resources, 11 accepted identities and 51 installed dependency pins. Template SHA256 is `a1128b0e9352e1dd7c8768eecc9335c50858356cee80ed33c0ec275e26c4d08b`; Git blob is `1d77ebb7140e1bf0fa3d7cbd092f215290a187c0`. No engine, template, accepted ancestor, dependency, security-delivery adapter, CI implementation, workflow or schedule is changed.

Reads: existing G07 input/session/receipt paths, C05 structural binding, the unchanged `engineering_source.fluid_reference` wrapper, pinned `materials_db`, `project_state`, `standalone_spacer`, and `phase_10_procedure`; existing parser/comparison helpers and C02/C03/C04/G06/C10 consumers. Writes: `checker_ui.py`, `g07_report.py`, `c05_fluids.py`, existing `tests/test_c05.py` and `tests/test_g07.py`, this note, and directly affected producer references in the R2-A ledger. No new module or dependency is introduced.

## Source → independent input → receipt → physical claim

| Input or claim | Authority and binding | Evidence/status |
| --- | --- | --- |
| Optional configuration | Existing Spacer expander; affirmative checkbox, initially false; active, source-eligible exact `Spacer` role only | PROVED by AppTest and Chromium; no mandatory fluid |
| `mode` | Pinned `standalone_spacer.MODES`, returned by the existing isolated catalog | PROVED: Limestone, Barite, Ferro Bar, Limestone + Barite; no default mode |
| `dead_vol` | Independent typed finite number; original source validation; blank remains missing and zero is explicit | PROVED: zero admission, blank/incomplete and changed-value invalidation |
| `tank_name` | `materials_db.get_available_tanks(job)`; original formulation validates it | PROVED: no default tank, invalid choice refusal and printed-tank discrepancy |
| `limestone_available_lb`, `barite_available_lb` | Shown only for Limestone + Barite; independent inventories required by original source | PROVED: missing stock incomplete; insufficient stock source-rejected; no inferred inventory |
| Existing volume/density/pump rate | Existing independent fluid controls and `project_state.refresh_fluids` | PROVED retained; configuration does not replace general fluid inputs |
| Frozen source operator | `standalone_spacer_input` validates schema/choices, not the calculation. `PrivateSession.check` checks exact typed draft/config/fluid identities before transport; original C05 source admits or rejects | PROVED by receipt and mutation-negative tests; `0` and `0.0` are not interchangeable identity hashes |
| Printed dose | `standalone_spacer.field_rows` and original `phase_10_procedure.build_master_context`, already projected by unchanged wrapper | PROVED on synthetic physical cells; no production-instance credit |

An explicitly selected incomplete formulation is `INPUT_INCOMPLETE`; its configuration is omitted from the C05 operator, so independently complete general fluid checks remain available. Complete values still require original source admission on explicit Run Check. Rejected density/inventory produces a rejected formulation, never a successful zero-discrepancy assertion. C02/C03 independent cement operators are unchanged.

The original Word builder prints powder dosage as a bare source-rounded number under the exact dosage header; liquid dosage retains `gal/bbl`. C05 consumes that existing source projection and full-precision `material['dose']`, with canonical units `lb/bbl` or `gal/bbl`. It neither calculates nor reverse-solves a dose. The existing comparison helper retains raw text, physical locator, material, original document/source hashes, source display/full precision, delta and zero display-comparison tolerance. Original source rounding is unchanged.

Physical eligibility requires one labeled Spacer table, one intact six-column header, a unique explicit material name/type row, unmerged grid and scalar cell, and the dosage header at physical column 4. Duplicate/split/merged/incorrectly associated cells and unproved unit/display grammar remain `NOT_VERIFIABLE`. The independently bound dosage column does not authenticate a missing or ambiguous adjacent mixing NOTE: preparation-water/tank findings remain separately unverified. Wrong tanks remain discrepancies. Existing base/gross and NOTE comparisons are retained.

Every new context field participates in the existing submission revision. Configuration, job, role, upload or numeric changes invalidate the current report, message and preview/copy authority. Source pins, frozen operator digest and current report/session receipt remain required; another session cannot adopt the receipt. C10 remains selected ordinary Yield/Sacks only; no R2-C DOCX correction or download-transport change occurs.

## Evidence and limitations

All new Word controls are **source-rendered synthetic controls**, not authentic App production exports. Original browser fixture SHA256 before/after: `cd4b443bd33bb0f71b79f396c42612f2794327fbf07eceb2d64ac0f71cb76fc4`. Private logs, documents, operator payloads, screenshots and receipt captures remain outside Git.

The pre-extension dosage test found zero dosage findings where the existing source-rendered table contained five eligible materials. This is a demonstrated coverage gap, not a claimed historical calculation regression. Final C05 tests cover all four source modes, dosage/raw-unit/header/material/grid mutations, missing/duplicate NOTE, tank discrepancy, inactive role, original bytes, optional non-Spacer fluid order and source validation/write/network boundaries.

Actual Chromium 154.0.8037.57 used the documented `c10_delivery.py` entrypoint, existing Playwright and loopback private runtime. Campaign 1 timed out before the Job control became available; no product defect was proved. The distinct second campaign required an actual connected Streamlit page and unique accessible controls, committed numeric entry with Enter/blur, and authenticated backend revision/receipt readback. It **FRESH PASSED** in 53.81 seconds: missing configuration retained general checks; missing Mix stock was not defaulted; explicit zero DV admitted with six physically located dosage findings; changed DV revoked the old result and required a new admitted run; insufficient stock was source-rejected; blank DV returned to general-only/incomplete configuration; a separate context had no upload, receipt or copy authority. Original DOCX stayed unchanged. Independent supervisor: 59.32 seconds total, no watchdog expiry, bounded 5.08-second cleanup. A new native stolen-download-URL experiment was not performed: this Spacer-only case had no cement copy authority; the existing R0 delivery/revocation regression suite is the affected-path safeguard.

### Verification commands and accounting

Commands run in the provisioned, Git-free private runtime with pinned dependencies and private cache/temp directories; no import/PYTHONPATH bypass or new package:

- Focused new C05/G07 controls: `python -B -m pytest -p no:cacheprovider -q ... -k r2c` — **28 PASS**, 139 deselected, 158.60 seconds at that intermediate test set; not full regression.
- `python -B -m pytest -p no:cacheprovider -q tests/test_c05.py` — **48 PASS**, 293.99 seconds on final production bytes, including 13 new cases and existing all-mode/source controls.
- A broader final G07/sibling invocation stopped after a partial progress log without a completed audit: **INCOMPLETE / NOT COUNTED AS PASS**. The subsequent bounded, complete targeted command and final audits are recorded below; there was no recorded assertion failure in that partial log.
- Final targeted G07/R2-B/R2-C, R2-A validator, R0 delivery, 13 migration guards and selected C02/C03/C04 water/source sentinels — **87 PASS**, 80 deselected, 370.30 seconds. The command selected `r2c`, `r2b`, all tests in `tests/test_r2a_coverage.py`, `tests/test_g08a7_delivery.py` and `tests/test_migration.py`, the existing G07 exact-empty-additives/source-receipt, Main-only/incomplete-Lead, complete-Main+Lead and stale/tampered-receipt cases, and these source sentinels: `c02/test_c02.py::test_independently_pinned_neat_reference_and_source_calls`, `c03/test_c03.py::test_two_different_tanks_and_no_first_slurry_borrow`, `c04/test_c04.py::test_powder_liquid_salt_dry_blend_and_unaffected_lab`. Every selected test has all three passing phases; no warnings/skips/xfails.
- `python -B -m pytest -p no:cacheprovider -q tests/test_g08a4_preview.py::test_volume_preview_noop_and_proposal_lifecycle_preserve_baseline tests/test_g08a5_dv_preview.py::test_dv_lifecycle_no_resurrection_cross_session_or_G06A_interference tests/test_g08a6_c10_ui.py::test_choice_consent_run_and_foreign_session_invalidate_copies` — **3 PASS**, 115.42 seconds; no warnings/skips/xfails.
- `python -B tools/ci.py collect` — **685 unique native roots**, A247/B223/C215; all 651 baseline roots preserved, 34 additions confined to the already owned C05/G07 modules. Collection is not execution or certification. No schedule assignment changed.

Root-directory command and raw output:

```text
sha256sum -- tools/test-schedule.json
a3e1689ff764c4ae46798fe0b590f335c5c8e7b79b5ca8b3db73531114d10ba9  tools/test-schedule.json
```

Schedule original → final is the same digest; schedule/digest diff is empty. Existing whole-module ownership remains C05 in B and G07 in C. Full local A/B/C execution is NOT RUN; hosted full regression is PENDING and will not be awaited by this executor.

The R2-A ledger receives only 131 directly affected Checker producer hash alignments, 115 line-reference alignments and 16 scope qualifications pointing to this note. Old producer hashes became obsolete because this approved batch changes those producers; actual symbols/AST anchors were rechecked. Source authority, claim patterns, status/maturity, physical-proof assertions and accounting are unchanged. Before/after alignment audit is private; all 18 existing positive/mutation-negative validator cases passed against the final ledger. Verified production claim instances remain zero; authentic J01–J15 and A–H/X01–X22 full acceptance remain `NOT_RUN`.

Final integrity/privacy audit: all 143 source SHA256/Git-blob identities, template, 11 accepted identities, 51 installed dependency pins, local bundle, unchanged schedule/digest and append-only existing tests passed. A private candidate export passed the publication scanner; only the seven declared paths differ. No runtime, operator payload, document, transfer URL, credential, screenshot or private evidence is added. Local Python is 3.12.14 with the exact 51 pinned packages; the unchanged hosted workflow specifies Python 3.12.15 and the 3600-second native watchdog / 65-minute step / 75-minute job. Local results are not hosted certification. Local cumulative accounting starts at 20:43:56.849 UTC on 3 November 2026; final evidence preparation completed within 48 minutes of the 60-minute cap, including the interrupted command and both browser campaigns. The final publication handoff records the actual elapsed total.

## Remaining scope

Pre Flush chemistry, operational Spacer Ahead/Behind recipe, unproved CT/well-specific stage claims, measured/reviewed Lab data and unavailable physical Word instances remain unsupported or `NOT_VERIFIABLE`, with zero verified credit. The seven Owner exclusions remain excluded: cover/document control, Survey, Centralizer, pore/fracture pressure, IOD, figures/schematics, appendices/TOC. Client Requested Volume remains independent; pure Mix Water, Solution and DV/preparation-water semantics remain distinct. R2-D–G, R3 editing, R4 audit delivery, authentic 15-job Goldens and R6 release/offline installation remain separate work.

**R2-C SCOPED COVERAGE ONLY — NOT R2 COMPLETE / NOT GOLDEN CERTIFIED / NOT RELEASED.**
